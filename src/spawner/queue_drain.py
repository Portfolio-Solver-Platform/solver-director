import logging
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models import Project, ResourceDefaults, UserResourceConfig
from src.config import Config
from src.schemas import ProjectConfiguration
from src.spawner.start_service import start_project_services

logger = logging.getLogger(__name__)


def drain_queue(db: Session) -> None:
    """Start queued projects in FIFO order, respecting global and per-user limits.

    Walk the queue oldest-first and apply two rules:
    - BREAK when the head project would exceed the global cap.  There is no
      point trying later projects; nothing more will fit until resources are
      freed.
    - CONTINUE when the head project would only exceed the submitting user's
      per-user cap.  Another user's project later in the queue may still fit,
      so we keep looking.
    """
    defaults_row = db.query(ResourceDefaults).filter_by(id=1).first()
    if defaults_row is None:
        global_max_cpu = Config.ResourceLimitDefaults.GLOBAL_MAX_CPU_CORES
        global_max_mem = Config.ResourceLimitDefaults.GLOBAL_MAX_MEMORY_GIB
        per_user_default_cpu = Config.ResourceLimitDefaults.PER_USER_CPU_CORES
        per_user_default_mem = Config.ResourceLimitDefaults.PER_USER_MEMORY_GIB
    else:
        global_max_cpu = defaults_row.global_max_cpu_cores
        global_max_mem = defaults_row.global_max_memory_gib
        per_user_default_cpu = defaults_row.per_user_cpu_cores
        per_user_default_mem = defaults_row.per_user_memory_gib

    queued = (
        db.query(Project)
        .filter_by(is_queued=True)
        .order_by(Project.created_at)
        .with_for_update(skip_locked=True)
        .all()
    )

    for project in queued:
        # Re-query global in-use so earlier flushes in this loop are reflected.
        global_row = (
            db.query(
                func.coalesce(func.sum(Project.requested_cpu_cores), 0.0).label("cpu"),
                func.coalesce(func.sum(Project.requested_memory_gib), 0.0).label("memory"),
            )
            .filter(
                Project.is_complete == False,  # noqa: E712
                Project.is_queued == False,    # noqa: E712
            )
            .one()
        )
        if float(global_row.cpu) + project.requested_cpu_cores > global_max_cpu:
            break
        if float(global_row.memory) + project.requested_memory_gib > global_max_mem:
            break

        # Per-user limit for this project's owner.
        user_config = db.query(UserResourceConfig).filter_by(user_id=project.user_id).first()
        effective_cpu = (
            user_config.vcpus
            if user_config and user_config.vcpus is not None
            else per_user_default_cpu
        )
        effective_mem = (
            user_config.memory_gib
            if user_config and user_config.memory_gib is not None
            else per_user_default_mem
        )

        user_row = (
            db.query(
                func.coalesce(func.sum(Project.requested_cpu_cores), 0.0).label("cpu"),
                func.coalesce(func.sum(Project.requested_memory_gib), 0.0).label("memory"),
            )
            .filter(
                Project.user_id == project.user_id,
                Project.is_complete == False,  # noqa: E712
                Project.is_queued == False,    # noqa: E712
            )
            .one()
        )
        if float(user_row.cpu) + project.requested_cpu_cores > effective_cpu:
            continue
        if float(user_row.memory) + project.requested_memory_gib > effective_mem:
            continue

        # Un-queue and start.
        project.is_queued = False
        db.flush()  # make the resource change visible to subsequent iterations

        try:
            config = ProjectConfiguration(**project.configuration)
            start_project_services(config, str(project.id), project.user_id)
        except Exception as e:
            logger.error(f"Failed to start queued project {project.id}: {e}")
            project.is_queued = True  # revert this project
            db.flush()
            break  # stop draining — service is likely unavailable

    db.commit()
