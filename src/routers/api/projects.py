from typing import Annotated, Any
from fastapi import APIRouter, HTTPException, Depends, status
from src.project_utils.data_streamer import data_streamer
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID
import requests
from prometheus_client import Counter
import logging

from src.database import get_db
from src.models import Project
from src.spawner.start_service import start_project_services
from src.spawner.stop_service import stop_solver_controller
from src.config import Config
from src.schemas import ProjectConfiguration
from src.auth import auth
from psp_auth import User
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter()
SCOPES = {
    "read": "projects:read",
    "write": "projects:write",
    "read-all": "projects:read-all",
    "write-all": "projects:write-all",
}

# Prometheus metrics
namespace_cleanup_failures = Counter(
    "solver_director_namespace_cleanup_failures_total",
    "Total number of namespace cleanup failures during project deletion",
    ["operation"],
)


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: str
    name: str
    created_at: datetime


class ProjectWithStatusResponse(ProjectResponse):
    status: Any


scopes = [SCOPES["write"]]


@router.post(
    "/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[auth.require_scopes(scopes)],
    openapi_extra=auth.scope_docs(scopes),
)
def create_project(
    config: ProjectConfiguration,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(auth.user())],
):
    """Create a new project and start a solver controller"""

    project = Project(
        user_id=user.id,
        name=config.name,
        configuration=config.model_dump(),
    )

    db.add(project)
    try:
        db.flush()  # Get the project ID without committing
    except Exception as e:
        db.rollback()
        logger.error(f"Database flush failed for user {user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create project",
        )

    try:
        start_project_services(config, str(project.id), user.id)
    except Exception as e:
        db.rollback()
        logger.error(
            f"Failed to start services for project {project.id}, user {user.id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create project",
        )

    try:
        db.commit()
        db.refresh(project)
    except Exception as e:
        db.rollback()
        logger.error(
            f"Database commit failed for project {project.id}, user {user.id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create project",
        )

    return project


scopes = [SCOPES["read"]]


@router.get(
    "/projects",
    response_model=list[ProjectResponse],
    dependencies=[auth.require_scopes(scopes)],
    openapi_extra=auth.scope_docs(scopes),
)
def get_projects(
    db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(auth.user())]
):
    """Get all projects for the authenticated user"""
    projects = db.query(Project).filter(Project.user_id == user.id).all()
    return projects


scopes = [SCOPES["read"]]


@router.get(
    "/projects/{project_id}/status",
    response_model=ProjectWithStatusResponse,
    dependencies=[auth.require_scopes(scopes)],
    openapi_extra=auth.scope_docs(scopes),
)
def get_project_status(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(auth.user())],
):
    """Get project by id with solver controller status"""

    try:
        uuid_id = UUID(project_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid user or project"
        )

    project = db.query(Project).filter(Project.id == uuid_id).first()
    if (
        not project or project.user_id != user.id
    ):  # if project not found or does not belong to user
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid user or project"
        )

    # Build URL to solver controller's status endpoint
    url = f"http://{Config.SolverController.SVC_NAME}.{str(project.id)}.svc.cluster.local:{Config.SolverController.SERVICE_PORT}/v1/status?queue_name={str(project.id)}"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        status_data = response.json()
    except Exception as e:
        logger.warning(f"Failed to fetch status for project {project.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Project status temporarily unavailable",
        )

    return ProjectWithStatusResponse(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        created_at=project.created_at,
        status=status_data,
    )


scopes = [SCOPES["read"]]


@router.get(
    "/projects/{project_id}/config",
    response_model=ProjectConfiguration,
    dependencies=[auth.require_scopes(scopes)],
    openapi_extra=auth.scope_docs(scopes),
)
def get_project_config(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(auth.user())],
):
    """Get project configuration for solver controller"""
    try:
        uuid_id = UUID(project_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid user or project"
        )

    project = db.query(Project).filter(Project.id == uuid_id).first()
    if not project or project.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid user or project"
        )

    return project.configuration


scopes = [SCOPES["read"]]


@router.get(
    "/projects/{project_id}/solution",
    dependencies=[auth.require_scopes(scopes)],
    openapi_extra=auth.scope_docs(scopes),
)
async def get_project_solution(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(auth.user())],
):
    """Get project solution/results"""
    try:
        uuid_id = UUID(project_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid user or project"
        )

    project = db.query(Project).filter(Project.id == uuid_id).first()
    if not project or project.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid user or project"
        )

    from src.main import app

    return StreamingResponse(
        data_streamer(app.state.pool, uuid_id),
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=project_{project_id}.json"
        },
    )


scopes = [SCOPES["write"]]


@router.delete(
    "/projects/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[auth.require_scopes(scopes)],
    openapi_extra=auth.scope_docs(scopes),
)
def delete_project(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(auth.user())],
):
    """Delete a project and its solver controller namespace

    TODO: Also delete solver controller generated data when implemented
    """
    # TODO: verify with keycloak that the token is valid with require remote token validation
    try:
        uuid_id = UUID(project_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid user or project"
        )

    project = db.query(Project).filter(Project.id == uuid_id).first()
    if not project or project.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid user or project"
        )

    try:
        stop_solver_controller(str(project.id))
    except Exception as e:
        logger.error(f"Failed to cleanup namespace for project {project.id}: {e}")
        namespace_cleanup_failures.labels(operation="project_deletion").inc()
        pass

    db.delete(project)
    db.commit()
    return None
