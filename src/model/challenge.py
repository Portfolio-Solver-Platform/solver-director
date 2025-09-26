class Challenge:
    def __init__(
        self,
        id: int,
        name: str,
        flag: str,
        docker_image: str,
        resource_limits: str,
        is_active: bool,
    ):
        self.id = id
        self.name = name
        self.flag = flag
        self.docker_image = docker_image
        self.resource_limits = resource_limits
        self.is_active = is_active

    @staticmethod
    def deserialize(json_dict: dict):
        return Challenge(
            id=json_dict.get("id"),
            name=json_dict.get("name"),
            flag=json_dict.get("flag"),
            docker_image=json_dict.get("docker_image"),
            resource_limits=json_dict.get("resource_limits"),
            is_active=json_dict.get("is_active"),
        )
