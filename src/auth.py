from psp_auth import Auth, AuthConfig, FastAPIAuth

auth_config = AuthConfig(
    client_id="solver-director",
    client_secret="Ycew6UMTHNsEtHuntIYj50oyxxdDuxWg",
    well_known_endpoint="http://user.psp.svc.cluster.local:8080/v1/internal/.well-known/openid-configuration",
)

auth_base = Auth(
    config=auth_config,
)

auth = FastAPIAuth(auth_base)
