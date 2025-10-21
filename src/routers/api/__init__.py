from fastapi import APIRouter
from . import routes, groups, problems

router = APIRouter()

router.include_router(routes.router)
router.include_router(groups.router)
router.include_router(problems.router)
