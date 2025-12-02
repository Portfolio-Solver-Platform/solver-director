from typing import Annotated
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict, Field
import asyncio
import re
import json
import base64
import tempfile
import os
from kubernetes import client, config as k8s_config
from prometheus_client import Counter

from src.database import get_db
from src.models import Solver, SolverImage
from src.config import Config


router = APIRouter()

# Docker image name validation pattern
# Must start with lowercase letter or digit, followed by lowercase alphanumeric, dots, hyphens, or underscores
# Max length: 128 characters
VALID_IMAGE_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")

# Prometheus metrics
temp_file_cleanup_failures = Counter(
    "solver_director_temp_file_cleanup_failures_total",
    "Total number of temporary file cleanup failures",
    ["operation"],
)


def get_harbor_credentials(secret_name: str = "harbor-creds-push"):  # nosec B107
    """Reads Harbor credentials from a Kubernetes secret

    Args:
        secret_name: Name of the Harbor credentials secret (default: harbor-creds-push)

    Returns:
        Tuple of (username, password) for Harbor authentication

    Note:
        The default parameter is a Kubernetes secret name (resource identifier),
        not a hardcoded password. Actual credentials are retrieved from K8s at runtime.
    """
    try:
        k8s_config.load_incluster_config()
        kube_client = client.CoreV1Api()

        secret = kube_client.read_namespaced_secret(name=secret_name, namespace="psp")

        # Docker config secrets store credentials in .dockerconfigjson
        docker_config_json = base64.b64decode(secret.data[".dockerconfigjson"]).decode(
            "utf-8"
        )
        docker_config = json.loads(docker_config_json)

        # Extract credentials for harbor.local
        auth_config = docker_config.get("auths", {}).get("harbor.local", {})
        auth_string = auth_config.get("auth", "")

        username, password = base64.b64decode(auth_string).decode("utf-8").split(":", 1)

        return username, password
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Harbor credentials: {str(e)}",
        )


class StartResponse(BaseModel):
    project_id: str = Field(..., description="project id to start")


class SolverListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    image_name: str
    image_path: str

    @staticmethod
    def from_solver_with_image(solver: Solver) -> "SolverListItem":
        return SolverListItem(
            id=solver.id,
            name=solver.name,
            image_name=solver.solver_image.image_name,
            image_path=solver.solver_image.image_path,
        )


class SolversResponse(BaseModel):
    solvers: list[SolverListItem]


class SolverDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    image_name: str
    image_path: str

    @staticmethod
    def from_solver_with_image(solver: Solver) -> "SolverDetailResponse":
        return SolverDetailResponse(
            id=solver.id,
            name=solver.name,
            image_name=solver.solver_image.image_name,
            image_path=solver.solver_image.image_path,
        )


class SolverUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    names: list[str]
    solver_images_id: int
    image_path: str


@router.get("/solvers", response_model=SolversResponse, summary="Get all solvers")
def get_solvers(db: Annotated[Session, Depends(get_db)]):
    """Get list of all solvers with their IDs from database"""
    solvers = db.query(Solver).join(Solver.solver_image).all()
    solver_items = [SolverListItem.from_solver_with_image(solver) for solver in solvers]
    return SolversResponse(solvers=solver_items)


@router.get(
    "/solvers/{id}", response_model=SolverDetailResponse, summary="Get solver by ID"
)
def get_solver_by_id(id: int, db: Annotated[Session, Depends(get_db)]):
    """Get solver details by ID"""
    solver = db.query(Solver).join(Solver.solver_image).filter(Solver.id == id).first()
    if not solver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Solver with id {id} not found",
        )
    return SolverDetailResponse.from_solver_with_image(solver)


@router.post(
    "/solvers", response_model=SolverUploadResponse, status_code=status.HTTP_201_CREATED
)
async def upload_solver(
    image_name: Annotated[
        str, Form(description="Docker image name for Harbor (e.g., 'minizinc-solver')")
    ],
    names: Annotated[
        str,
        Form(
            description="Comma-separated solver names (e.g., 'chuffed,gecode,ortools')"
        ),
    ],
    file: Annotated[UploadFile, File(description="Docker image tarball (.tar file)")],
    db: Annotated[Session, Depends(get_db)],
):
    """Upload a Docker image tarball and push to Harbor

    Args:
        image_name: Docker image name for Harbor (e.g., "minizinc-solver")
        names: Comma-separated solver names that this image supports (e.g., "chuffed,gecode,ortools")
        file: Docker image tarball (.tar file)

    Returns:
        SolverResponse with solver metadata including Harbor image path
    """
    normalized_image_name = image_name.strip().lower()
    if not normalized_image_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Image name cannot be empty",
        )

    if not VALID_IMAGE_NAME.match(normalized_image_name):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Image name must be lowercase alphanumeric, may contain dots, hyphens, or underscores, and must start with a letter or digit",
        )

    name_list = [n.strip().lower() for n in names.split(",") if n.strip()]
    if not name_list:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one solver name is required",
        )

    for name in name_list:
        if not VALID_IMAGE_NAME.match(name):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Solver name '{name}' is invalid. Must be lowercase alphanumeric, may contain dots, hyphens, or underscores, and must start with a letter or digit",
            )

    existing_image = (
        db.query(SolverImage)
        .filter(SolverImage.image_name == normalized_image_name)
        .first()
    )
    if existing_image:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Solver image '{normalized_image_name}' already exists",
        )

    if not file:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="File is required"
        )

    file_data = await file.read()
    if not file_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="File cannot be empty",
        )

    tarball_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tar") as tmp:
            tmp.write(file_data)
            tarball_path = tmp.name

        username, password = get_harbor_credentials()

        registry_image_name = f"{Config.ArtifactRegistry.INTERNAL_URL}{Config.ArtifactRegistry.PROJECT}/{normalized_image_name}:latest"
        external_image_name = f"{Config.ArtifactRegistry.EXTERNAL_URL}{Config.ArtifactRegistry.PROJECT}/{normalized_image_name}:latest"

        skopeo_args = [
            "skopeo",
            "copy",
            f"docker-archive:{tarball_path}",
            f"docker://{registry_image_name}",
            "--dest-creds",
            f"{username}:{password}",
        ]

        if not Config.ArtifactRegistry.TLS_VERIFY:
            skopeo_args.append("--dest-tls-verify=false")

        # Safe: subprocess uses list args (no shell), Harbor RBAC restricts push to psp-solvers project only
        # nosec B603
        process = await asyncio.create_subprocess_exec(
            *skopeo_args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=300,  # 5 minute timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Image push timed out",
            )

        if process.returncode != 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to push image to Harbor: {stderr.decode('utf-8')}",
            )

        solver_image = SolverImage(
            image_name=normalized_image_name, image_path=external_image_name
        )
        db.add(solver_image)
        db.flush()

        for name in name_list:
            solver = Solver(name=name, solver_image_id=solver_image.id)
            db.add(solver)

        db.commit()
        db.refresh(solver_image)

        return SolverUploadResponse(
            id=solver_image.id,
            names=name_list,
            solver_images_id=solver_image.id,
            image_path=external_image_name,
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload solver: {str(e)}",
        )
    finally:
        if tarball_path and os.path.exists(tarball_path):
            try:
                os.unlink(tarball_path)
            except Exception:
                temp_file_cleanup_failures.labels(operation="solver_upload").inc()
