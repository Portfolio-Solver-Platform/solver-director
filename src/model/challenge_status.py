class SolverControllerStatus:
    def __init__(self, user_id: int, started: bool, error: str):
        self.user_id = user_id
        self.started = started
        self.error = error
    
    def to_dict(self):
        return {
            "user_id": self.user_id,
            "started": self.started,
            "error": self.error
        }