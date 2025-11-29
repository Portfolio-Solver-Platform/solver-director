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

    class ArtifactRegistry:
        EXTERNAL_URL = os.getenv("EXTERNAL_ARTIFACT_REGISTRY_URL", "harbor.local/")
        # Internal registry URL for skopeo (defaults to harbor-core service)
        INTERNAL_URL = os.getenv(
            "INTERNAL_ARTIFACT_REGISTRY_URL", "harbor-core.harbor.svc.cluster.local/"
        )
        PROJECT = "psp-solvers"
        TLS_VERIFY = os.getenv("HARBOR_TLS_VERIFY", "false") == "true"

    class SolverController:
        ARTIFACT_REGISTRY_PATH = "psp/solver-controller:latest"
        SVC_NAME = "solver-controller"
        CONTAINER_PORT = 8080
        SERVICE_PORT = 80

    class DataGatherer:
        ARTIFACT_REGISTRY_PATH = "psp/data-gatherer:latest"
        SVC_NAME = "data-gatherer"
        CONTAINER_PORT = 8080
        SERVICE_PORT = 80

    class Database:
        HOST = os.getenv("DB_HOST", "postgres-postgresql")
        PORT = int(os.getenv("DB_PORT", "5432"))
        NAME = os.getenv("DB_NAME", "appdb")
        USER = os.getenv("DB_USER", "appuser")
        PASSWORD = os.getenv("DB_PASSWORD", "devpassword123")

        @classmethod
        def get_url(cls):
            return f"postgresql://{cls.USER}:{cls.PASSWORD}@{cls.HOST}:{cls.PORT}/{cls.NAME}"

    class RabbitMQ:
        HOST = os.getenv("RABBITMQ_HOST", "rabbitmq.rabbit-mq.svc.cluster.local")
        PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
        USER = os.getenv("RABBITMQ_USER", "guest")
        PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")
        SOLVER_DIRECTOR_RESULT_QUEUE = f"solver_director_result_queue"

    class SolversNamespace:
        CPU_QUOTA = float(os.getenv("SOLVERS_NAMESPACE_CPU_QUOTA", "1")) # In cores
        MEMORY_QUOTA = float(os.getenv("SOLVERS_NAMESPACE_MEMORY_QUOTA", "2")) # In GiB
        
    SOLUTION_RETRIEVAL_CHUNK_SIZE = float(os.getenv("SOLUTION_RETRIEVAL_CHUNK_SIZE", "1000"))
    SOLVER_DIRECTOR_URL = "http://solver-director.solver-director.svc.cluster.local"
   

    # class Keycloak:
    #     CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "solver-director")
    #     CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET")  # Required from secret
    #     WELL_KNOWN_URL = os.getenv(
    #         "KEYCLOAK_WELL_KNOWN_URL",
    #         "http://user.psp.svc.cluster.local:8080/v1/.well-known/openid-configuration/internal"
    #     )
