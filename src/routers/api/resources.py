from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from sqlalchemy import func
from src.database import get_db
from src.models import ResourceDefaults, UserResourceConfig, Project
from src.config import Config
from src.auth import auth
from psp_auth import User, Token

router = APIRouter()

SCOPES = {
    "read": "resources:read",
    "write": "resources:write",
}

_READ_SCOPES = [SCOPES["read"]]
_WRITE_SCOPES = [SCOPES["write"]]


class ResourceDefaultsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    per_user_cpu_cores: float
    per_user_memory_gib: float
    global_max_cpu_cores: float
    global_max_memory_gib: float


class ResourceDefaultsRequest(BaseModel):
    per_user_cpu_cores: float = Field(..., gt=0)
    per_user_memory_gib: float = Field(..., gt=0)
    global_max_cpu_cores: float = Field(..., gt=0)
    global_max_memory_gib: float = Field(..., gt=0)


def _get_defaults(db: Session) -> ResourceDefaultsResponse:
    """Return DB row if it exists, otherwise the hardcoded Config fallbacks."""
    row = db.query(ResourceDefaults).filter_by(id=1).first()
    if row is None:
        return ResourceDefaultsResponse(
            per_user_cpu_cores=Config.ResourceLimitDefaults.PER_USER_CPU_CORES,
            per_user_memory_gib=Config.ResourceLimitDefaults.PER_USER_MEMORY_GIB,
            global_max_cpu_cores=Config.ResourceLimitDefaults.GLOBAL_MAX_CPU_CORES,
            global_max_memory_gib=Config.ResourceLimitDefaults.GLOBAL_MAX_MEMORY_GIB,
        )
    return ResourceDefaultsResponse.model_validate(row)


@router.get(
    "/resources/defaults",
    response_model=ResourceDefaultsResponse,
    dependencies=[auth.require_scopes(_WRITE_SCOPES)],
    openapi_extra=auth.scope_docs(_WRITE_SCOPES),
)
def get_resource_defaults(db: Annotated[Session, Depends(get_db)]):
    """Get the current global and per-user resource limits.

    Returns hardcoded fallback values if an admin has not yet configured them.
    """
    return _get_defaults(db)


@router.put(
    "/resources/defaults",
    response_model=ResourceDefaultsResponse,
    dependencies=[auth.require_scopes(_WRITE_SCOPES)],
    openapi_extra=auth.scope_docs(_WRITE_SCOPES),
)
def update_resource_defaults(
    request: ResourceDefaultsRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """Set the global and per-user resource limits.

    Creates the configuration if it does not exist yet (first-time setup).
    """
    if request.global_max_cpu_cores < request.per_user_cpu_cores:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="global_max_cpu_cores must be >= per_user_cpu_cores",
        )
    if request.global_max_memory_gib < request.per_user_memory_gib:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="global_max_memory_gib must be >= per_user_memory_gib",
        )

    row = db.query(ResourceDefaults).filter_by(id=1).first()
    if row is None:
        row = ResourceDefaults(
            id=1,
            per_user_cpu_cores=request.per_user_cpu_cores,
            per_user_memory_gib=request.per_user_memory_gib,
            global_max_cpu_cores=request.global_max_cpu_cores,
            global_max_memory_gib=request.global_max_memory_gib,
        )
        db.add(row)
    else:
        row.per_user_cpu_cores = request.per_user_cpu_cores
        row.per_user_memory_gib = request.per_user_memory_gib
        row.global_max_cpu_cores = request.global_max_cpu_cores
        row.global_max_memory_gib = request.global_max_memory_gib

    db.commit()
    db.refresh(row)
    return row


# ── Per-user resource config ──────────────────────────────────────────────────


class UserResourceConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    vcpus: int | None
    memory_gib: float | None


class UserResourceConfigRequest(BaseModel):
    vcpus: int = Field(..., gt=0)
    memory_gib: float = Field(..., gt=0)


class UserResourceUsageResponse(BaseModel):
    user_id: str
    vcpus_override: int | None
    memory_gib_override: float | None
    effective_cpu_cores: float
    effective_memory_gib: float
    in_use_cpu_cores: float
    in_use_memory_gib: float
    available_cpu_cores: float
    available_memory_gib: float


def _get_user_usage(user_id: str, db: Session) -> UserResourceUsageResponse:
    """Compute effective limits and in-use resources for a user."""
    defaults = _get_defaults(db)
    user_config = db.query(UserResourceConfig).filter_by(user_id=user_id).first()
    cpu_override = user_config.vcpus if user_config else None
    mem_override = user_config.memory_gib if user_config else None
    effective_cpu = cpu_override if cpu_override is not None else defaults.per_user_cpu_cores
    effective_mem = mem_override if mem_override is not None else defaults.per_user_memory_gib

    row = (
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
    in_use_cpu = float(row.cpu)
    in_use_mem = float(row.memory)

    return UserResourceUsageResponse(
        user_id=user_id,
        vcpus_override=cpu_override,
        memory_gib_override=mem_override,
        effective_cpu_cores=effective_cpu,
        effective_memory_gib=effective_mem,
        in_use_cpu_cores=in_use_cpu,
        in_use_memory_gib=in_use_mem,
        available_cpu_cores=effective_cpu - in_use_cpu,
        available_memory_gib=effective_mem - in_use_mem,
    )


@router.get(
    "/resources/users/{user_id}",
    response_model=UserResourceUsageResponse,
    dependencies=[auth.require_scopes(_READ_SCOPES)],
    openapi_extra=auth.scope_docs(_READ_SCOPES),
)
def get_user_resource_usage(
    user_id: str,
    db: Annotated[Session, Depends(get_db)],
    token: Annotated[Token, Depends(auth.token())],
    user: Annotated[User, Depends(auth.user())],
):
    """Get effective resource limits and current usage for a user.

    Users can read their own data with resources:read. Admins with
    resources:write can read any user's data.
    """
    if user_id != user.id and not token.has_scopes(_WRITE_SCOPES):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return _get_user_usage(user_id, db)


@router.put(
    "/resources/users/{user_id}",
    response_model=UserResourceConfigResponse,
    dependencies=[auth.require_scopes(_WRITE_SCOPES)],
    openapi_extra=auth.scope_docs(_WRITE_SCOPES),
)
def update_user_resource_config(
    user_id: str,
    request: UserResourceConfigRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """Set custom resource limits for a specific user.

    The values must not exceed the global max. Creates the config if it does
    not exist yet.
    """
    defaults = _get_defaults(db)

    if request.vcpus > defaults.global_max_cpu_cores:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"vcpus exceeds global_max_cpu_cores ({defaults.global_max_cpu_cores})",
        )
    if request.memory_gib > defaults.global_max_memory_gib:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"memory_gib exceeds global_max_memory_gib ({defaults.global_max_memory_gib})",
        )

    config = db.query(UserResourceConfig).filter_by(user_id=user_id).first()
    if config is None:
        config = UserResourceConfig(
            user_id=user_id,
            vcpus=request.vcpus,
            memory_gib=request.memory_gib,
        )
        db.add(config)
    else:
        config.vcpus = request.vcpus
        config.memory_gib = request.memory_gib

    db.commit()
    db.refresh(config)
    return config


@router.delete(
    "/resources/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[auth.require_scopes(_WRITE_SCOPES)],
    openapi_extra=auth.scope_docs(_WRITE_SCOPES),
)
def delete_user_resource_config(
    user_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    """Remove custom resource limits for a user, reverting them to global defaults."""
    config = db.query(UserResourceConfig).filter_by(user_id=user_id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No custom resource config for this user",
        )
    db.delete(config)
    db.commit()
    return None
