import os


class Config:
    class App:
        NAME = "solver-director"
        VERSION = "0.1.0"
        DEBUG = os.getenv("DEBUG", "false").lower() == "true"

    class Api:
        TITLE = "Solver Director API"
        DESCRIPTION = "API to manage solvers runnining on Instance problems"
        VERSION = "v1"
        ROOT_PATH = "/api/solverdirector"

    class SolverController:
        IMAGE = os.getenv("SOLVER_CONTROLLER_IMAGE", "ghcr.io/portfolio-solver-platform/solver-controller:latest")
        SVC_NAME = "solver-controller"
        CONTAINER_PORT = 8080
        SERVICE_PORT = 80

    class DataGatherer:
        IMAGE = os.getenv("DATA_GATHERER_IMAGE", "ghcr.io/portfolio-solver-platform/data-gatherer:latest")
        SVC_NAME = "data-gatherer"
        CONTAINER_PORT = 8080
        SERVICE_PORT = 80

    class Database:
        HOST = os.getenv("DB_HOST", "solver-director-postgres")
        PORT = int(os.getenv("DB_PORT", "5432"))
        NAME = os.getenv("DB_NAME", "solver_director")
        USER = os.getenv("DB_USER", "appuser")
        PASSWORD = os.getenv("DB_PASSWORD", "devpassword123")

        @classmethod
        def get_url(cls):
            return f"postgresql://{cls.USER}:{cls.PASSWORD}@{cls.HOST}:{cls.PORT}/{cls.NAME}"

    class RabbitMQ:
        HOST = os.getenv("RABBITMQ_HOST", "rabbitmq.rabbit-mq.svc.cluster.local")
        PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
        MANAGEMENT_PORT = 15672
        USER = os.getenv("RABBITMQ_USER", "guest")
        PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")
        SOLVER_DIRECTOR_RESULT_QUEUE = "solver_director_result_queue"

    class ResourceLimitDefaults:
        PER_USER_CPU_CORES = float(os.getenv("DEFAULT_PER_USER_CPU_CORES", "5.0"))
        PER_USER_MEMORY_GIB = float(os.getenv("DEFAULT_PER_USER_MEMORY_GIB", "8.0"))
        GLOBAL_MAX_CPU_CORES = float(os.getenv("DEFAULT_GLOBAL_MAX_CPU_CORES", "6.0"))
        GLOBAL_MAX_MEMORY_GIB = float(os.getenv("DEFAULT_GLOBAL_MAX_MEMORY_GIB", "12.0"))

    class Keda:
        KEDA_QUEUE_LENGTH = os.getenv("KEDA_QUEUE_LENGTH", "1")

    SOLUTION_RETRIEVAL_CHUNK_SIZE = float(
        os.getenv("SOLUTION_RETRIEVAL_CHUNK_SIZE", "1000")
    )
    SOLVER_DIRECTOR_URL = "http://solver-director.solver-director.svc.cluster.local"

    class Keycloak:
        CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "solver-director")
        CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET")
