from psp_auth import Auth, AuthConfig, FastAPIAuth

auth_config = AuthConfig(client_id="solver-director", well_known_endpoint="http://user.psp.svc.cluster.local:8080/v1/internal/.well-known/openid-configuration")

auth = FastAPIAuth(
    Auth(
        config=auth_config,
        
    ),
)
