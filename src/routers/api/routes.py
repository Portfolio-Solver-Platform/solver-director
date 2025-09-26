from fastapi import APIRouter, HTTPException
from src.config import Config
from src.spawner.start_service import start_solver_controller
from pydantic import BaseModel, Field
import requests

from src.spawner.util.util_service import generate_solver_controller_id

router = APIRouter()


class StartResponse(BaseModel):
    project_id: str = Field(..., description="project id to start")


@router.get("/start", response_model=StartResponse, summary="Starts solving instances")
def start_route():
    """ """
    id = start_solver_controller("sofus")
    return StartResponse(project_id=id)


@router.get("/status")
def get_status():
    user_id = "sofus"
    namespace = generate_solver_controller_id(user_id)
    url = f"http://{Config.SolverController.SVC_NAME}.{namespace}.svc.cluster.local:5000/status"
    try:
        return requests.get(url, timeout=10)
    except Exception:
        raise HTTPException(status_code=403, detail="cant connect")
