import logging
from urllib.parse import quote

import requests
from kubernetes import client, config

from src.config import Config
from src.utils import solvers_namespace

logger = logging.getLogger(__name__)


def stop_solver_controller(namespace):
    config.load_incluster_config()
    kube_client = client.CoreV1Api()
    kube_client.delete_namespace(namespace)
    kube_client.delete_namespace(solvers_namespace(namespace))
    delete_project_queues(namespace)


def delete_project_queues(project_id):
    management_url = f"http://{Config.RabbitMQ.HOST}:{Config.RabbitMQ.MANAGEMENT_PORT}"
    auth = (Config.RabbitMQ.USER, Config.RabbitMQ.PASSWORD)

    queues = requests.get(f"{management_url}/api/queues/%2F", auth=auth, timeout=10).json()

    project_prefix = f"project-{project_id}-"
    for queue in queues:
        if queue["name"].startswith(project_prefix) or queue["name"] == project_id:
            response = requests.delete(
                f"{management_url}/api/queues/%2F/{quote(queue['name'], safe='')}",
                auth=auth,
                timeout=10,
            )
            if response.ok:
                logger.info(f"Deleted queue: {queue['name']}")
            else:
                logger.warning(f"Failed to delete queue {queue['name']}: {response.status_code}")
