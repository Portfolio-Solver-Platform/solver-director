from dataclasses import asdict
import json
from fastapi import HTTPException

from kubernetes import client, config
from kubernetes.client.rest import ApiException
from src.spawner.stop_service import stop_solver_controller
from src.utils import solvers_namespace, control_queue_name, solver_director_result_queue_name, result_queue_name, project_director_queue_name
from src.spawner.status_service import is_user_limit_reached

from src.config import Config
import pika


def start_project_services(project_config, id, user_id):
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

    _solvers_namespace = solvers_namespace(id)
    solvers_namespace_manifest = {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {"name": _solvers_namespace},
    }
    try:
        kube_client.create_namespace(body=solvers_namespace_manifest)
    except ApiException as e:
        if e.status == 409:
            pass   # already exists 
        else:
            raise

    template_secret = kube_client.read_namespaced_secret(
        name="harbor-creds-pull", namespace="psp"
    )

    # create 2 namespaces. One for infrastructure for project and the Data Gatherer/AI. Another namepace for the solvers themselves.
    control_secret = client.V1Secret(
        metadata=client.V1ObjectMeta(name="harbor-creds", namespace=id),
        type=template_secret.type,
        data=template_secret.data,
    )
    kube_client.create_namespaced_secret(namespace=id, body=control_secret)

    solvers_secret = client.V1Secret(
        metadata=client.V1ObjectMeta(name="harbor-creds", namespace=_solvers_namespace),
        type=template_secret.type,
        data=template_secret.data,
    )
    kube_client.create_namespaced_secret(namespace=_solvers_namespace, body=solvers_secret)

    # Create Role in solvers namespace to allow creating deployments and scaledobjects
    role = client.V1Role(
        metadata=client.V1ObjectMeta(name="solver-creator", namespace=_solvers_namespace),
        rules=[
            client.V1PolicyRule(
                api_groups=["apps"],
                resources=["deployments"],
                verbs=["create"],
            ),
            client.V1PolicyRule(
                api_groups=["keda.sh"],
                resources=["scaledobjects"],
                verbs=["create"],
            ),
        ],
    )
    rbac_client = client.RbacAuthorizationV1Api()
    try:
        rbac_client.create_namespaced_role(namespace=_solvers_namespace, body=role)
    except ApiException as e:
        if e.status == 409:
            pass
        else:
            raise

    # Create RoleBinding in solvers namespace
    role_binding = client.V1RoleBinding(
        metadata=client.V1ObjectMeta(
            name="solver-creator-binding", namespace=_solvers_namespace
        ),
        subjects=[
            {
                "kind": "ServiceAccount",
                "name": "default",
                "namespace": id,
            }
        ],
        role_ref=client.V1RoleRef(
            kind="Role",
            name="solver-creator",
            api_group="rbac.authorization.k8s.io",
        ),
    )
    try:
        rbac_client.create_namespaced_role_binding(
            namespace=_solvers_namespace, body=role_binding
        )
    except ApiException as e:
        if e.status == 409:
            pass
        else:
            raise

    resource_quota = {
        "apiVersion": "v1",
        "kind": "ResourceQuota",
        "metadata": {"name": "solver-quota", "namespace": _solvers_namespace},
        "spec": {
            "hard": {
                "requests.cpu": str(int(Config.SolversNamespace.CPU_QUOTA)),
                "requests.memory": f"{int(Config.SolversNamespace.MEMORY_QUOTA)}Gi",
                "limits.cpu": str(int(Config.SolversNamespace.CPU_QUOTA)),
                "limits.memory": f"{int(Config.SolversNamespace.MEMORY_QUOTA)}Gi",
            }
        },
    }
    try:
        kube_client.create_namespaced_resource_quota(namespace=_solvers_namespace, body=resource_quota)
    except ApiException as e:
        if e.status == 409:
            pass
        else:
            raise
        
    control_queue = control_queue_name(id)
    solver_director_result_queue = solver_director_result_queue_name()
    result_queue = result_queue_name(id)
    director_queue = project_director_queue_name(id)
    

    _ = kube_client.create_namespaced_pod(
        namespace=id, body=create_solver_controller_pod_manifest(id, control_queue)
    )
    _ = kube_client.create_namespaced_service(
        namespace=id,
        body=create_solver_controller_service_manifest(),
    )



    _ = kube_client.create_namespaced_pod(
        namespace=id, body=create_data_gatherer_pod_manifest(id, control_queue, director_queue, result_queue, solver_director_result_queue)
    )
    _ = kube_client.create_namespaced_service(
        namespace=id,
        body=create_data_gatherer_service_manifest(),
    )
    
    credentials = pika.PlainCredentials(
        Config.RabbitMQ.USER,
        Config.RabbitMQ.PASSWORD
    )
    parameters = pika.ConnectionParameters(
        host=Config.RabbitMQ.HOST,
        port=Config.RabbitMQ.PORT,
        credentials=credentials
    )

    connection = pika.BlockingConnection(parameters)
    try:
        channel = connection.channel()
        channel.queue_declare(queue=director_queue, durable=True)
        body = json.dumps({"problem_groups": project_config.model_dump()['problem_groups']}).encode()

        channel.basic_publish(
            exchange='',  # Default exchange
            routing_key=director_queue,
            body=body,
            properties=pika.BasicProperties(
                delivery_mode=pika.DeliveryMode.Persistent
            )
        )
    except Exception as e:
        stop_solver_controller(id)
        raise e
    finally:
        connection.close() 

def create_solver_controller_pod_manifest(project_id, control_queue):
    solver_director_url = Config.SOLVER_DIRECTOR_URL
    _solvers_namespace = solvers_namespace(project_id)

    max_replicas = Config.SolversNamespace.CPU_QUOTA

    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": "solver-controller",
            "labels": {"solver_controller_id": "solver-controller"},
        },
        "spec": {
            "imagePullSecrets": [{"name": "harbor-creds"}],
            "securityContext": {
                "runAsNonRoot": True,
                "seccompProfile": {"type": "RuntimeDefault"},
            },
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
                        {"name": "SOLVERS_NAMESPACE", "value": _solvers_namespace},
                        {"name": "SOLVER_TYPES", "value": "chuffed"},
                        {"name": "CONTROL_QUEUE", "value": control_queue},
                        {"name": "MAX_TOTAL_SOLVER_REPLICAS", "value": str(max_replicas)},
                        {"name": "SOLVER_DIRECTOR_URL", "value": solver_director_url},
                    ],
                    "volumeMounts": [
                        {"name": "tmp", "mountPath": "/tmp"},
                    ],
                    "securityContext": {
                        "allowPrivilegeEscalation": False,
                        "readOnlyRootFilesystem": True,
                        "capabilities": {"drop": ["ALL"]},
                    },
                }
            ],
            "volumes": [
                {"name": "tmp", "emptyDir": {}},
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


def create_data_gatherer_pod_manifest(project_id, control_queue, director_queue, result_queue, solver_director_result_queue):

    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": "data-gatherer",
            "labels": {"data_gatherer_id": "data-gatherer"},
        },
        "spec": {
            "imagePullSecrets": [{"name": "harbor-creds"}],
            "securityContext": {
                "runAsNonRoot": True,
                "seccompProfile": {"type": "RuntimeDefault"},
            },
            "containers": [
                {
                    "name": "data-gatherer",
                    "image": f"{Config.ArtifactRegistry.EXTERNAL_URL}{Config.DataGatherer.ARTIFACT_REGISTRY_PATH}",
                    "imagePullPolicy": "IfNotPresent",
                    "ports": [{"containerPort": Config.DataGatherer.CONTAINER_PORT}],
                    "env": [
                        {"name": "DEBUG", "value": str(Config.App.DEBUG)},
                        {"name": "PROJECT_ID", "value": str(project_id)},
                        {"name": "CONTROL_QUEUE", "value": control_queue},
                        {"name": "DIRECTOR_QUEUE", "value": director_queue},
                        {"name": "PROJECT_SOLVER_RESULT_QUEUE", "value": result_queue},
                        {"name": "SOLVER_DIRECTOR_RESULT_QUEUE", "value": solver_director_result_queue},
                        {"name": "RABBITMQ_HOST", "value": Config.RabbitMQ.HOST},
                        {"name": "RABBITMQ_PORT", "value": str(Config.RabbitMQ.PORT)},
                        {"name": "RABBITMQ_USER", "value": Config.RabbitMQ.USER},
                        {"name": "RABBITMQ_PASSWORD", "value": Config.RabbitMQ.PASSWORD},
                    ],
                    "volumeMounts": [
                        {"name": "tmp", "mountPath": "/tmp"},
                    ],
                    "securityContext": {
                        "allowPrivilegeEscalation": False,
                        "readOnlyRootFilesystem": True,
                        "capabilities": {"drop": ["ALL"]},
                    },
                }
            ],
            "volumes": [
                {"name": "tmp", "emptyDir": {}},
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
