

def generate_solver_controller_id(user_id):
    if not user_id:
        raise ValueError("Valid user_id required")
    return f"solver-controller-u{user_id}"


# def find_pod_by_label(v1, label):
#     pods = v1.list_namespaced_pod(namespace=namespace)
#     for pod in pods.items:
#         if pod.metadata.labels and pod.metadata.labels.get('ctf-id', None) == label:
#             return pod
#     return None


# def find_service_by_label(v1, label):
#     services = v1.list_namespaced_service(namespace=namespace)
#     for service in services.items:
#         if service.metadata.labels and service.metadata.labels.get('ctf-id', None) == label:
#             return service
#     return None

  
# def pod_belongs_to_user(pod, user_id: int) -> bool:
#     return pod.metadata.labels and f"u{user_id}-" in pod.metadata.labels.get('ctf-id', '')