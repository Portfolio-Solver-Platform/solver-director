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
        HARBOR_NAME = "http://harbor.local/psp/solver-controller"
        SVC_NAME = "solver-controller"
        CONTAINER_PORT = 5000
        SERVICE_PORT = 80  # 443
