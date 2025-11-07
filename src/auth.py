from psp_auth import Auth, AuthConfig, FastAPIAuth
from .config import Config

auth = FastAPIAuth(
    Auth(
        config=AuthConfig(
            client_id=Config.Auth.CLIENT_ID,
            client_secret=Config.Auth.CLIENT_SECRET,
        )
    ),
)
