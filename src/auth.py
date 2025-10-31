from psp_auth import Auth, AuthConfig, FastAPIAuth

auth_config = AuthConfig(client_id="solver-director")

auth = FastAPIAuth(
    Auth(
        config=auth_config,
    ),
)
