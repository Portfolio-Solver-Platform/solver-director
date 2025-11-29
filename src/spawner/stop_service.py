from kubernetes import client, config
from src.utils import solvers_namespace


def stop_solver_controller(namespace):
    config.load_incluster_config()  # Load k8s config to use mounted service account
    kube_client = client.CoreV1Api()
    kube_client.delete_namespace(namespace)
    kube_client.delete_namespace(solvers_namespace(namespace))
