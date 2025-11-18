from kubernetes import client


def stop_solver_controller(namespace):
    kube_client = client.CoreV1Api()
    kube_client.delete_namespace(namespace)
