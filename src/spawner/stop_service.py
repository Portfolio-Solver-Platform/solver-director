from kubernetes import client, config


def stop_solver_controller(namespace):
    config.load_incluster_config()  # Load k8s config to use mounted service account
    kube_client = client.CoreV1Api()
    kube_client.delete_namespace(namespace)
