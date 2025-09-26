class User:
    def __init__(self, id, open_challenge_limit):
        self.id = id
        self.open_challenge_limit = open_challenge_limit

    @staticmethod
    def deserialize(json_dict: dict):
        return User(
            id=json_dict.get("id"),
            open_challenge_limit=json_dict.get("open_challenge_limit")
        )