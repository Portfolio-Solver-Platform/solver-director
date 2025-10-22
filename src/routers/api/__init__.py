from fastapi import APIRouter
from . import routes, groups, problems, instances

router = APIRouter()

router.include_router(routes.router)
router.include_router(groups.router)
router.include_router(problems.router)
router.include_router(instances.router)
