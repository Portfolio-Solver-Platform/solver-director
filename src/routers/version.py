from fastapi import APIRouter
from src.config import Config
from pydantic import BaseModel, Field

router = APIRouter()


class VersionResponse(BaseModel):
    service: str = Field(..., description="Name of the service")
    version: str = Field(
        ..., description="Semantic version of the service implementation"
    )
    api_version: str = Field(
        ..., description="API contract version exposed by the service"
    )


@router.get(
    "/version",
    response_model=VersionResponse,
    summary="Get information about the service",
)
def version():
    """
    Get information about the service.
    """
    return VersionResponse(
        service=Config.App.NAME,
        version=Config.App.VERSION,
        api_version=Config.Api.VERSION,
    )
