from psp_auth import Auth, AuthConfig, FastAPIAuth
from src.config import Config

auth_config = AuthConfig(
    client_id=Config.Keycloak.CLIENT_ID,
    client_secret=Config.Keycloak.CLIENT_SECRET,
    well_known_endpoint="http://user.psp.svc.cluster.local:8080/v1/internal/.well-known/openid-configuration",
)

auth = FastAPIAuth(
    Auth(
        config=auth_config,
    ),
)
