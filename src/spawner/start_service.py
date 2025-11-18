from fastapi import HTTPException

from kubernetes import client, config
from kubernetes.client.rest import ApiException
from src.spawner.status_service import is_user_limit_reached

from src.config import Config


def start_project_services(id, user_id):
    users_solver_controller_limit_reached = is_user_limit_reached(user_id)
    if users_solver_controller_limit_reached:
        raise HTTPException(
            status_code=429,
            detail="user has reached it's limit for concurrent solver controllers spawned",
        )
    config.load_incluster_config()
    kube_client = client.CoreV1Api()

    namespace_manifest = {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {"name": id},
    }
    try:
        kube_client.create_namespace(body=namespace_manifest)
    except ApiException as e:
        if e.status == 409:
            pass  # already exists
        else:
            raise

    template_secret = kube_client.read_namespaced_secret(
        name="harbor-creds-pull", namespace="psp"
    )

    new_secret = client.V1Secret(
        metadata=client.V1ObjectMeta(name="harbor-creds", namespace=id),
        type=template_secret.type,
        data=template_secret.data,
    )

    kube_client.create_namespaced_secret(namespace=id, body=new_secret)

    _ = kube_client.create_namespaced_pod(
        namespace=id, body=create_solver_controller_pod_manifest(id)
    )
    _ = kube_client.create_namespaced_service(
        namespace=id,
        body=create_solver_controller_service_manifest(),
    )

    _ = kube_client.create_namespaced_pod(
        namespace=id, body=create_data_gatherer_pod_manifest()
    )
    _ = kube_client.create_namespaced_service(
        namespace=id,
        body=create_data_gatherer_service_manifest(),
    )


def create_solver_controller_pod_manifest(project_id):
    # Construct the solver-director base URL
    solver_director_url = "http://solver-director.solver-director.svc.cluster.local"
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": "solver-controller",
            "labels": {"solver_controller_id": "solver-controller"},
        },
        "spec": {
            "imagePullSecrets": [{"name": "harbor-creds"}],
            "containers": [
                {
                    "name": "solver-controller",
                    "image": f"{Config.ArtifactRegistry.EXTERNAL_URL}{Config.SolverController.ARTIFACT_REGISTRY_PATH}",
                    "imagePullPolicy": "IfNotPresent",
                    "ports": [
                        {"containerPort": Config.SolverController.CONTAINER_PORT}
                    ],
                    "env": [
                        {"name": "PROJECT_ID", "value": str(project_id)},
                        {"name": "SOLVER_DIRECTOR_URL", "value": solver_director_url},
                    ],
                }
            ],
        },
    }


def create_solver_controller_service_manifest():
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": "solver-controller",
            "labels": {"solver_controller_id": "solver-controller"},
        },
        "spec": {
            "type": "ClusterIP",
            "selector": {"solver_controller_id": "solver-controller"},
            "ports": [
                {
                    "port": Config.SolverController.SERVICE_PORT,
                    "targetPort": Config.SolverController.CONTAINER_PORT,
                }
            ],
        },
    }


def create_data_gatherer_pod_manifest():
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": "data-gatherer",
            "labels": {"data_gatherer_id": "data-gatherer"},
        },
        "spec": {
            "imagePullSecrets": [{"name": "harbor-creds"}],
            "containers": [
                {
                    "name": "data-gatherer",
                    "image": f"{Config.ArtifactRegistry.EXTERNAL_URL}{Config.DataGatherer.ARTIFACT_REGISTRY_PATH}",
                    "imagePullPolicy": "IfNotPresent",
                    "ports": [{"containerPort": Config.DataGatherer.CONTAINER_PORT}],
                }
            ],
        },
    }


def create_data_gatherer_service_manifest():
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": "data-gatherer",
            "labels": {"data_gatherer_id": "data-gatherer"},
        },
        "spec": {
            "type": "ClusterIP",
            "selector": {"data_gatherer_id": "data-gatherer"},
            "ports": [
                {
                    "port": Config.DataGatherer.SERVICE_PORT,
                    "targetPort": Config.DataGatherer.CONTAINER_PORT,
                }
            ],
        },
    }
