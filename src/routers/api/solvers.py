from typing import Annotated
from fastapi import APIRouter, HTTPException, Depends, Form, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict, Field
import re

from src.database import get_db
from src.models import Solver, SolverImage
from src.auth import auth


router = APIRouter()
SCOPES = {
    "read": "solvers:read",
    "write": "solvers:write",
}

# Docker image name validation pattern
# Must start with lowercase letter or digit, followed by lowercase alphanumeric, dots, hyphens, or underscores
# Max length: 128 characters
VALID_IMAGE_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")


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


scopes = [SCOPES["read"]]


@router.get(
    "/solvers",
    response_model=SolversResponse,
    summary="Get all solvers",
    dependencies=[auth.require_scopes(scopes)],
    openapi_extra=auth.scope_docs(scopes),
)
def get_solvers(db: Annotated[Session, Depends(get_db)]):
    """Get list of all solvers with their IDs from database"""
    solvers = db.query(Solver).join(Solver.solver_image).all()
    solver_items = [SolverListItem.from_solver_with_image(solver) for solver in solvers]
    return SolversResponse(solvers=solver_items)


scopes = [SCOPES["read"]]


@router.get(
    "/solvers/{id}",
    response_model=SolverDetailResponse,
    summary="Get solver by ID",
    dependencies=[auth.require_scopes(scopes)],
    openapi_extra=auth.scope_docs(scopes),
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


scopes = [SCOPES["write"]]


@router.post(
    "/solvers",
    response_model=SolverUploadResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[auth.require_scopes(scopes)],
    openapi_extra=auth.scope_docs(scopes),
)
def register_solver(
    image_name: Annotated[
        str, Form(description="Short image name (e.g., 'minizinc-solvers')")
    ],
    image_url: Annotated[
        str, Form(description="Full image URL (e.g., 'ghcr.io/portfolio-solver-platform/minizinc-solvers:latest')")
    ],
    names: Annotated[
        str,
        Form(
            description="Comma-separated solver names (e.g., 'chuffed,gecode,ortools')"
        ),
    ],
    db: Annotated[Session, Depends(get_db)],
):
    """Register a solver image by its registry URL."""
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

    if not image_url.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Image URL cannot be empty",
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

    try:
        solver_image = SolverImage(
            image_name=normalized_image_name, image_path=image_url.strip()
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
            image_path=image_url.strip(),
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register solver: {str(e)}",
        )


@router.patch(
    "/solvers/images/{image_name}",
    response_model=SolverUploadResponse,
    dependencies=[auth.require_scopes([SCOPES["write"]])],
    openapi_extra=auth.scope_docs([SCOPES["write"]]),
)
def update_solver_image_url(
    image_name: str,
    image_url: Annotated[str, Form(description="New full image URL")],
    db: Annotated[Session, Depends(get_db)],
):
    """Update the image URL for an existing solver image by name."""
    solver_image = (
        db.query(SolverImage)
        .filter(SolverImage.image_name == image_name.strip().lower())
        .first()
    )
    if not solver_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Solver image '{image_name}' not found",
        )

    if not image_url.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Image URL cannot be empty",
        )

    solver_image.image_path = image_url.strip()
    db.commit()
    db.refresh(solver_image)

    return SolverUploadResponse(
        id=solver_image.id,
        names=[s.name for s in solver_image.solvers],
        solver_images_id=solver_image.id,
        image_path=solver_image.image_path,
    )
