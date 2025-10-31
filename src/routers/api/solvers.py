from typing import Annotated
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict, Field
import asyncio
import re
import requests
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


class SolversResponse(BaseModel):
    solvers: list[str] = Field(..., description="List of available solver names")


class SolverResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    solver_images_id: int
    image_path: str

    @staticmethod
    def from_solver_with_image(solver: Solver) -> "SolverResponse":
        """Create response from Solver with joined SolverImage"""
        return SolverResponse(
            id=solver.id,
            name=solver.name,
            solver_images_id=solver.solver_images_id,
            image_path=solver.solver_image.image_path,
        )


@router.get("/solvers", response_model=SolversResponse, summary="Get available solvers")
def get_solvers():
    """Get list of available solvers from Harbor registry"""
    try:
        username, password = get_harbor_credentials()
        url = "http://harbor-core.harbor.svc.cluster.local/api/v2.0/projects/psp-solvers/repositories"

        response = requests.get(url, auth=(username, password), timeout=10)
        response.raise_for_status()

        repositories = response.json()

        # Strip "psp-solvers/" prefix from repository names
        solvers = [repo["name"].replace("psp-solvers/", "") for repo in repositories]

        return SolversResponse(solvers=solvers)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to fetch solvers from Harbor: {str(e)}",
        )


@router.post(
    "/solvers", response_model=SolverResponse, status_code=status.HTTP_201_CREATED
)
async def upload_solver(
    name: Annotated[str, Form()],
    file: Annotated[UploadFile, File(description="Docker image tarball (.tar file)")],
    db: Annotated[Session, Depends(get_db)],
):
    """Upload a Docker image tarball and push to Harbor

    Args:
        name: Solver name (e.g., "gecode")
        file: Docker image tarball (.tar file)

    Returns:
        SolverResponse with solver metadata including Harbor image path
    """
    # Validate name
    normalized_name = name.strip().lower()
    if not normalized_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Solver name cannot be empty",
        )

    if not VALID_IMAGE_NAME.match(normalized_name):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Solver name must be lowercase alphanumeric, may contain dots, hyphens, or underscores, and must start with a letter or digit",
        )

    # Check for duplicate solver name
    existing = db.query(Solver).filter(Solver.name == normalized_name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Solver with name '{normalized_name}' already exists",
        )

    # Validate file
    if not file:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="File is required"
        )

    # Read file data to check if empty
    file_data = await file.read()
    if not file_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="File cannot be empty",
        )

    # Save tarball to temporary file
    tarball_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tar") as tmp:
            tmp.write(file_data)
            tarball_path = tmp.name

        # Get Harbor credentials
        username, password = get_harbor_credentials()

        # Push to Harbor using skopeo
        # Use REGISTRY_URL for internal cluster communication
        registry_image_name = f"{Config.Harbor.REGISTRY_URL}/{Config.Harbor.PROJECT}/{normalized_name}:latest"
        # Use URL for storing in database (external reference)
        external_image_name = (
            f"{Config.Harbor.URL}/{Config.Harbor.PROJECT}/{normalized_name}:latest"
        )

        skopeo_args = [
            "skopeo",
            "copy",
            f"docker-archive:{tarball_path}",
            f"docker://{registry_image_name}",
            "--dest-creds",
            f"{username}:{password}",
        ]

        # Add TLS verification flag
        if not Config.Harbor.TLS_VERIFY:
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

        # Create SolverImage record with external image path
        solver_image = SolverImage(image_path=external_image_name)
        db.add(solver_image)
        db.flush()  # Get the ID without committing

        # Create Solver record
        solver = Solver(name=normalized_name, solver_images_id=solver_image.id)
        db.add(solver)
        db.commit()
        db.refresh(solver)

        # Return solver response
        return SolverResponse.from_solver_with_image(solver)

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
        # Clean up temporary file
        if tarball_path and os.path.exists(tarball_path):
            try:
                os.unlink(tarball_path)
            except Exception:
                # Log cleanup failure to Prometheus
                temp_file_cleanup_failures.labels(operation="solver_upload").inc()
