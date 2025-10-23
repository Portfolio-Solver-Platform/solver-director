from typing import Literal
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok"]


@router.get(
    "/healthz",
    response_model=HealthResponse,
    summary="Get the health of the service",
    include_in_schema=False,
)
def healthz():
    """
    Get the health of the service.
    """
    return HealthResponse(status="ok")


class ReadyResponse(BaseModel):
    status: Literal["ready"]


@router.get(
    "/readyz",
    response_model=ReadyResponse,
    summary="Get whether the service is ready",
    include_in_schema=False,
)
def readyz():
    """
    Get whether the service is ready to serve requests
    """
    return ReadyResponse(status="ready")
    # if is_keycloak_ready():
    #     status = "ready"
    # else:
    #     status = "not ready"
    # return jsonify(status=status)


# def is_keycloak_ready() -> bool:
#     response = try_get_keycloak_ready_response()
#     if response is None:
#         return False

#     data = response.json()
#     return data["status"] == "UP"


# def try_get_keycloak_ready_response() -> requests.Response | None:
#     url = f"http://{Config.Keycloak.HOST}/health/ready"
#     try:
#         return requests.get(url, timeout=Config.Keycloak.Timeout.READINESS)
#     except ConnectionError:
#         return None
