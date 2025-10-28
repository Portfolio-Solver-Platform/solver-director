from fastapi import APIRouter, HTTPException
from src.config import Config
from src.spawner.start_service import start_solver_controller
from pydantic import BaseModel, Field
import requests
import json
import base64
from kubernetes import client, config as k8s_config

from src.spawner.util.util_service import generate_solver_controller_id

router = APIRouter()


def get_harbor_credentials():
    """Reads Harbor credentials from the harbor-creds Kubernetes secret"""
    try:
        k8s_config.load_incluster_config()
        kube_client = client.CoreV1Api()

        secret = kube_client.read_namespaced_secret(
            name="harbor-creds", namespace="psp"
        )

        # Docker config secrets store credentials in .dockerconfigjson
        docker_config_json = base64.b64decode(secret.data[".dockerconfigjson"]).decode(
            "utf-8"
        )
        docker_config = json.loads(docker_config_json)

        # Extract credentials for harbor.local
        auth_config = docker_config.get("auths", {}).get("harbor.local", {})
        auth_string = auth_config.get("auth", "")

        # Decode base64 encoded "username:password"
        username, password = base64.b64decode(auth_string).decode("utf-8").split(":", 1)

        return username, password
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get Harbor credentials: {str(e)}"
        )


class StartResponse(BaseModel):
    project_id: str = Field(..., description="project id to start")


class SolversResponse(BaseModel):
    solvers: list[str] = Field(..., description="List of available solver names")



@router.get("/solvers", response_model=SolversResponse, summary="Get available solvers")
def get_solvers():
    """Get list of available solvers from Harbor registry"""
    try:
        username, password = get_harbor_credentials()
        url = "http://harbor-core.harbor.svc.cluster.local/api/v2.0/projects/psp-solvers/repositories"

        response = requests.get(url, auth=(username, password), timeout=10)
        response.raise_for_status()

        repositories = response.json()

        # Strip "psp-solvers/" prefix from repository names
        solvers = [repo["name"].replace("psp-solvers/", "") for repo in repositories]

        return SolversResponse(solvers=solvers)
    except Exception as e:
        raise HTTPException(
            status_code=503, detail=f"Failed to fetch solvers from Harbor: {str(e)}"
        )


@router.post("/solvers")
def post_solvers():
    """Upload new solvers"""
