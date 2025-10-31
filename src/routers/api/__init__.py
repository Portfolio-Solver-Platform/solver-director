from fastapi import APIRouter
from . import groups, problems, instances, projects, solvers

router = APIRouter()

router.include_router(solvers.router, tags=["Solvers"])
router.include_router(groups.router, tags=["Groups"])
router.include_router(problems.router, tags=["Problems"])
router.include_router(instances.router, tags=["Instances"])
router.include_router(projects.router, tags=["Projects"])
