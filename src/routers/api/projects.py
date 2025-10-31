from typing import Annotated, Any
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from datetime import datetime
import requests

from src.database import get_db
from src.models import Project
from src.spawner.start_service import start_solver_controller
from src.spawner.stop_service import stop_solver_controller
from src.config import Config
# from src.auth import auth
# from psp_auth import User


router = APIRouter()


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    solver_controller_id: str
    created_at: datetime


class ProjectWithStatusResponse(ProjectResponse):
    status: Any


@router.post(
    "/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED
)
def create_project(db: Annotated[Session, Depends(get_db)]):
    """Create a new project and start a solver controller"""
    # TODO: Get user_id from authentication when implemented. Also make sure to implement tests for user_id handling.
    user_id = "sofus"

    # Start solver controller
    try:
        solver_controller_id = start_solver_controller(user_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start solver controller: {str(e)}",
        )

    # Create project in database
    project = Project(
        user_id=user_id,
        solver_controller_id=solver_controller_id,
    )

    db.add(project)

    try:
        db.commit()
        db.refresh(project)
    except Exception as e:
        db.rollback()
        # Check if it's a unique constraint violation
        if "UNIQUE constraint failed" in str(e) or "duplicate key" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Project with this solver controller already exists",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create project: {str(e)}",
        )

    return project


@router.get("/projects", response_model=list[ProjectResponse])
def get_projects(db: Annotated[Session, Depends(get_db)], user_id: str | None = None):
    """Get all projects, optionally filtered by user_id"""
    query = db.query(Project)

    if user_id is not None:
        query = query.filter(Project.user_id == user_id)

    return query.all()


# @router.get("/projects", response_model=list[ProjectResponse], dependencies=[auth.require_scopes(["projects:read"])], openapi_extra=auth.scope_docs(["projects:read"]))
# def get_projects(db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(auth.user())]):
#     """Get all projects for the authenticated user"""
#     query = db.query(Project)

#     query = query.filter(Project.user_id == user.id)

#     return query.all()


@router.get("/projects/{project_id}", response_model=ProjectWithStatusResponse)
def get_project(project_id: int, db: Annotated[Session, Depends(get_db)]):
    """Get project by id with solver controller status"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    # Build URL to solver controller's status endpoint
    url = f"http://{Config.SolverController.SVC_NAME}.{project.solver_controller_id}.svc.cluster.local:{Config.SolverController.SERVICE_PORT}/v1/status"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        status_data = response.json()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to solver controller: {str(e)}",
        )

    return ProjectWithStatusResponse(
        id=project.id,
        user_id=project.user_id,
        solver_controller_id=project.solver_controller_id,
        created_at=project.created_at,
        status=status_data,
    )


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: Annotated[Session, Depends(get_db)]):
    """Delete a project and its solver controller namespace

    TODO: Also delete solver controller generated data when implemented
    """
    # Verify project exists
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    # Delete the namespace (which deletes all services)
    try:
        stop_solver_controller(project.solver_controller_id)
    except Exception as _:
        # Log error but continue with DB deletion
        # Namespace might already be deleted or not exist
        pass

    # Delete project from database
    db.delete(project)
    db.commit()
    return None
