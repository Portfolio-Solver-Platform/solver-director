# def check_ctf_started(user_id, challenge_id):
#     ctf_id = generate_ctf_id(user_id, challenge_id)
#     kube_client = client.CoreV1Api()
#     service = find_service_by_label(kube_client, ctf_id)
#     service_url = service.status.load_balancer.ingress[0].ip if service and service.status.load_balancer.ingress else None
#     challenge_url = f"{service_url}:{servicePort}" if service_url else None
#     started = service_url is not None
#     return SolverControllerStatus(user_id, challenge_id, challenge_url, started, None)


def is_user_limit_reached(user_id, namespace):
    return False
    # challenge_limit = fetch_challenge_limit(user_id)
    # challenge_limit = 1
    # kube_client = client.CoreV1Api()
    # services = kube_client.list_namespaced_service(namespace=namespace)
    # active_challenges_count = 0
    # for service in services.items:
    #     if service.metadata.labels and f"u{user_id}-" in service.metadata.labels.get('ctf-id', ''):
    #         active_challenges_count += 1
    # return active_challenges_count >= challenge_limit


# def fetch_challenge_limit(user_id):
#     token = auth.get_access_token()
#     headers = {"Authorization": f"Bearer {token}"}
#     url = f"http://user:5000/users/{user_id}"
#     response = requests.get(url=url, headers=headers)
#     json_dict = response.json()
#     return User.deserialize(json_dict).open_challenge_limit
