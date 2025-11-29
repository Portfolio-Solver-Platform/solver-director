

from src.config import Config


def solvers_namespace(namespace: str):
    return f"{namespace}-solvers"

def control_queue_name(namespace):
    return f"project-{namespace}-controller"

def result_queue_name(namespace):
    return f"project-{namespace}-result"

def solver_director_result_queue_name():
    return Config.RabbitMQ.SOLVER_DIRECTOR_RESULT_QUEUE

def project_director_queue_name(namespace):
    return f"project-{namespace}-director"