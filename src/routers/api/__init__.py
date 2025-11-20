from fastapi import APIRouter
from . import groups, problems, instances, projects, solvers
from src.auth import auth_config, auth_base
from joserfc import jwt
from joserfc.jwk import KeySet
import httpx

router = APIRouter()


@router.get("/test")
async def my_test():
    psp_token = await psp_login()

    key_set = KeySet.import_key_set(auth_base.token_certs())
    token = jwt.decode(psp_token, key_set)
    print(token.claims)

    secrets_token = await secrets_login(psp_token)

    return secrets_token


async def secrets_login(psp_token: str) -> str:
    timeout = httpx.Timeout(10.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        data = await client.post(
            "http://secrets-manager-openbao.secrets-manager.svc.cluster.local:8200/v1/auth/jwt/login",
            data={
                "role": "artifact-write",
                "jwt": psp_token,
            },
        )
    print(data)
    return data.json()
    return data.json()["auth"]["client_token"]


async def psp_login() -> str:
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
    return data.json()["access_token"]


router.include_router(solvers.router, tags=["Solvers"])
router.include_router(groups.router, tags=["Groups"])
router.include_router(problems.router, tags=["Problems"])
router.include_router(instances.router, tags=["Instances"])
router.include_router(projects.router, tags=["Projects"])
