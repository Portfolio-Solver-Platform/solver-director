from fastapi import HTTPException

from kubernetes import client, config
from kubernetes.client.rest import ApiException
from src.spawner.status_service import is_user_limit_reached
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
    config.load_incluster_config()  # This tells it to use the mounted service account
    kube_client = client.CoreV1Api()

    namespace_manifest = {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {"name": solver_controller_id},
    }
    try:
        kube_client.create_namespace(body=namespace_manifest)
    except ApiException as e:
        if e.status == 409:
            pass  # already exists
        else:
            raise

    template_secret = kube_client.read_namespaced_secret(
        name="harbor-creds", namespace="psp"
    )

    new_secret = client.V1Secret(
        metadata=client.V1ObjectMeta(
            name="harbor-creds", namespace=solver_controller_id
        ),
        type=template_secret.type,
        data=template_secret.data,
    )

    kube_client.create_namespaced_secret(
        namespace=solver_controller_id, body=new_secret
    )

    _ = kube_client.create_namespaced_pod(
        namespace=solver_controller_id, body=create_pod_manifest(solver_controller_id)
    )
    _ = kube_client.create_namespaced_service(
        namespace=solver_controller_id,
        body=create_service_manifest(solver_controller_id),
    )

    return solver_controller_id


def create_pod_manifest(solver_controller_id):
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
                    "image": Config.SolverController.HARBOR_NAME,
                    "ports": [
                        {"containerPort": Config.SolverController.CONTAINER_PORT}
                    ],
                }
            ],
        },
    }


def create_service_manifest(solver_controller_id):
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": "solver-controller",
            "labels": {"solver_controller_id": "solver-controller"},
        },
        "spec": {
            "type": "LoadBalancer",
            "selector": {"solver_controller_id": "solver-controller"},
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


def create_rbac_manifests(solver_controller_id):
    """Create service account and role binding for the specific namespace"""

    # Service Account
    service_account = {
        "apiVersion": "v1",
        "kind": "ServiceAccount",
        "metadata": {"name": "solver-controller", "namespace": solver_controller_id},
    }

    # Role (namespace-scoped permissions)
    role = {
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "kind": "Role",
        "metadata": {
            "name": "solver-controller-role",
            "namespace": solver_controller_id,
        },
        "rules": [
            {
                "apiGroups": [""],
                "resources": ["pods", "services"],
                "verbs": ["get", "list", "create", "delete", "watch"],
            }
        ],
    }

    # Role Binding
    role_binding = {
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "kind": "RoleBinding",
        "metadata": {
            "name": "solver-controller-binding",
            "namespace": solver_controller_id,
        },
        "roleRef": {
            "apiGroup": "rbac.authorization.k8s.io",
            "kind": "Role",
            "name": "solver-controller-role",
        },
        "subjects": [
            {
                "kind": "ServiceAccount",
                "name": "solver-controller",
                "namespace": solver_controller_id,
            }
        ],
    }

    return service_account, role, role_binding
