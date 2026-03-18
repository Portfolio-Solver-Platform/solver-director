from typing import Annotated, Any
from fastapi import APIRouter, HTTPException, Depends, status
from src.project_utils.data_streamer import data_streamer
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID
import requests
from prometheus_client import Counter
import logging

from src.database import get_db
from src.models import Project, ResourceDefaults, UserResourceConfig
from src.spawner.start_service import start_project_services
from src.spawner.stop_service import stop_solver_controller
from src.spawner.queue_drain import drain_queue
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
    is_queued: bool


def _should_queue(user_id: str, cpu_requested: float, mem_requested: float, db: Session) -> bool:
    """Return True if this project should join the queue instead of starting immediately.

    Rule 1: if any project is already queued, join the queue (prevents starvation of
    large requests that would otherwise be bypassed by smaller ones indefinitely).

    Rule 2: if adding this project would exceed the global hard cap, queue it.

    Rule 3: if the user's effective per-user limit would be exceeded, queue it.
    """
    # Rule 1: non-empty queue → always join
    if db.query(Project).filter_by(is_queued=True).first() is not None:
        return True

    # Resolve limits
    defaults_row = db.query(ResourceDefaults).filter_by(id=1).first()
    if defaults_row is None:
        global_max_cpu = Config.ResourceLimitDefaults.GLOBAL_MAX_CPU_CORES
        global_max_mem = Config.ResourceLimitDefaults.GLOBAL_MAX_MEMORY_GIB
        per_user_cpu = Config.ResourceLimitDefaults.PER_USER_CPU_CORES
        per_user_mem = Config.ResourceLimitDefaults.PER_USER_MEMORY_GIB
    else:
        global_max_cpu = defaults_row.global_max_cpu_cores
        global_max_mem = defaults_row.global_max_memory_gib
        per_user_cpu = defaults_row.per_user_cpu_cores
        per_user_mem = defaults_row.per_user_memory_gib

    user_config = db.query(UserResourceConfig).filter_by(user_id=user_id).first()
    effective_cpu = user_config.vcpus if user_config and user_config.vcpus is not None else per_user_cpu
    effective_mem = user_config.memory_gib if user_config and user_config.memory_gib is not None else per_user_mem

    # Rule 2: global capacity check
    global_row = (
        db.query(
            func.coalesce(func.sum(Project.requested_cpu_cores), 0.0).label("cpu"),
            func.coalesce(func.sum(Project.requested_memory_gib), 0.0).label("memory"),
        )
        .filter(Project.is_complete == False, Project.is_queued == False)  # noqa: E712
        .one()
    )
    if float(global_row.cpu) + cpu_requested > global_max_cpu:
        return True
    if float(global_row.memory) + mem_requested > global_max_mem:
        return True

    # Rule 3: per-user capacity check
    user_row = (
        db.query(
            func.coalesce(func.sum(Project.requested_cpu_cores), 0.0).label("cpu"),
            func.coalesce(func.sum(Project.requested_memory_gib), 0.0).label("memory"),
        )
        .filter(
            Project.user_id == user_id,
            Project.is_complete == False,  # noqa: E712
            Project.is_queued == False,    # noqa: E712
        )
        .one()
    )
    if float(user_row.cpu) + cpu_requested > effective_cpu:
        return True
    if float(user_row.memory) + mem_requested > effective_mem:
        return True

    return False


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
    """Create a new project. Starts immediately if resources are available and the
    queue is empty, otherwise joins the FIFO queue.
    """
    queued = _should_queue(user.id, config.vcpus, config.memory_gib, db)

    project = Project(
        user_id=user.id,
        name=config.name,
        configuration=config.model_dump(),
        requested_cpu_cores=config.vcpus,
        requested_memory_gib=config.memory_gib,
        is_queued=queued,
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

    if not queued:
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

    # If project is already complete, return immediately without contacting
    # the solver-controller (which has already been torn down)
    if project.is_complete:
        return ProjectWithStatusResponse(
            id=project.id,
            user_id=project.user_id,
            name=project.name,
            created_at=project.created_at,
            is_queued=project.is_queued,
            status={"isFinished": True},
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

    status_data["isFinished"] = project.is_complete

    return ProjectWithStatusResponse(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        created_at=project.created_at,
        is_queued=project.is_queued,
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

    try:
        drain_queue(db)
    except Exception as e:
        logger.error(f"Queue drain failed after project {project_id} deletion: {e}")

    return None
