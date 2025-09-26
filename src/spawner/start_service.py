from fastapi import HTTPException

from kubernetes import client

from src.spawner.status_service import is_user_limit_reached
from src.model.challenge_status import SolverControllerStatus
from src.spawner.util.util_service import generate_solver_controller_id

from src.config import Config


def start_solver_controller(user_id):
    solver_controller_id = generate_solver_controller_id(user_id)
    users_solver_controller_limit_reached = is_user_limit_reached(user_id)
    if users_solver_controller_limit_reached:
        raise HTTPException(
            status_code=429,
            detail="user has reached it's limit for concurrent solver controllers spawned",
        )

    kube_client = client.CoreV1Api()

    _ = kube_client.create_namespaced_(
        namespace=solver_controller_id, body=create_pod_manifest(solver_controller_id)
    )
    _ = kube_client.create_namespaced_service(
        namespace=solver_controller_id,
        body=create_service_manifest(solver_controller_id),
    )

    return SolverControllerStatus(user_id, True, None)


def create_pod_manifest(solver_controller_id):
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": solver_controller_id,
            "labels": {"solver_controller_id": solver_controller_id},
        },
        "spec": {
            "containers": [
                {
                    "name": solver_controller_id,
                    "image": Config.SolverController.HARBOR_NAME,
                    "ports": [
                        {"containerPort": Config.SolverController.CONTAINER_PORT}
                    ],
                }
            ]
        },
    }


def create_service_manifest(ctf_id):
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": ctf_id, "labels": {"ctf-id": ctf_id}},
        "spec": {
            "type": "LoadBalancer",
            "selector": {"ctf-id": ctf_id},
            "ports": [
                {
                    "port": Config.SolverController.SERVICE_PORT,
                    "targetPort": Config.SolverController.CONTAINER_PORT,
                }
            ],
        },
    }


# def get_service_ip(v1, ctf_id):
#     service_ip = None
#     timeout_seconds = 100
#     start_time = time.time()
#     while not service_ip and (time.time() - start_time) < timeout_seconds:
#         service_name = find_service_by_label(v1, ctf_id).metadata.name
#         service = v1.read_namespaced_service(name=service_name, namespace=namespace)
#         if service.status.load_balancer.ingress:
#             service_ip = service.status.load_balancer.ingress[0].ip
#         else:
#             time.sleep(5)
#     return service_ip
