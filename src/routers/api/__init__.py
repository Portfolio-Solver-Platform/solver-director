from fastapi import APIRouter
from . import groups, problems, instances, projects, solvers
from src.auth import auth_config
import httpx

router = APIRouter()


@router.get("/test")
async def my_test():
    print("Trying to log in to Keycloak")
    timeout = httpx.Timeout(10.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        data = await client.post(
            "http://keycloak-service.keycloak.svc.cluster.local:8080/realms/psp/protocol/openid-connect/token",
            data={
                "client_id": auth_config.client_id,
                "client_secret": auth_config.client_secret,
                "grant_type": "client_credentials",
            },
        )
        print(data)
        return data


router.include_router(solvers.router, tags=["Solvers"])
router.include_router(groups.router, tags=["Groups"])
router.include_router(problems.router, tags=["Problems"])
router.include_router(instances.router, tags=["Instances"])
router.include_router(projects.router, tags=["Projects"])
