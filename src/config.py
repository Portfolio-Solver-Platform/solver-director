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
        HARBOR_NAME = "harbor.local/psp/solver-controller:latest"
        SVC_NAME = "solver-controller"
        CONTAINER_PORT = 8080
        SERVICE_PORT = 80

    class Database:
        HOST = os.getenv("DB_HOST", "postgres-postgresql")
        PORT = os.getenv("DB_PORT", "5432")
        NAME = os.getenv("DB_NAME", "appdb")
        USER = os.getenv("DB_USER", "appuser")
        PASSWORD = os.getenv("DB_PASSWORD", "devpassword123")

        @classmethod
        def get_url(cls):
            return f"postgresql://{cls.USER}:{cls.PASSWORD}@{cls.HOST}:{cls.PORT}/{cls.NAME}"

    class Harbor:
        URL = os.getenv("HARBOR_URL", "harbor.local")
        # Internal registry URL for skopeo (defaults to harbor-core service)
        REGISTRY_URL = os.getenv("HARBOR_REGISTRY_URL", "harbor-core.harbor.svc.cluster.local")
        PROJECT = "psp-solvers"
        TLS_VERIFY = os.getenv("HARBOR_TLS_VERIFY", "false") == "true"
