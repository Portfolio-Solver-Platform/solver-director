"""OAuth2 authentication for RabbitMQ using Keycloak tokens."""

import httpx
import logging
from datetime import datetime, timedelta
from typing import Optional
from src.config import Config
from psp_auth.endpoints import OidcEndpoints

logger = logging.getLogger(__name__)


class RabbitMQTokenCache:
    def __init__(self):
        self._token: Optional[str] = None
        self._expiry: Optional[datetime] = None

    def get_token(self) -> Optional[str]:
        if self._token and self._expiry:
            if datetime.now() < self._expiry - timedelta(seconds=30):
                return self._token
        return None

    def set_token(self, token: str, expires_in: int):
        self._token = token
        self._expiry = datetime.now() + timedelta(seconds=expires_in)


_token_cache = RabbitMQTokenCache()

# OIDC endpoints fetcher (uses well-known from user service, caches for 1 hour)
_oidc_endpoints = OidcEndpoints(
    well_known_url=Config.Keycloak.WELL_KNOWN_URL, request_timeout=(5, 10)
)


def get_rabbitmq_token() -> str:
    cached_token = _token_cache.get_token()
    if cached_token:
        logger.debug("Using cached RabbitMQ token")
        return cached_token

    logger.info("Fetching new RabbitMQ token from Keycloak")

    # Get token endpoint from well-known (cached by OidcEndpoints)
    well_known = _oidc_endpoints._well_known()
    token_url = well_known["token_endpoint"]

    client_id = Config.Keycloak.CLIENT_ID
    client_secret = Config.Keycloak.CLIENT_SECRET

    logger.debug(f"Using token endpoint from well-known: {token_url}")
    logger.debug(f"Client ID: {client_id}")
    logger.debug(
        f"Client secret present: {client_secret is not None and len(client_secret) > 0}"
    )

    if not client_secret:
        raise Exception("KEYCLOAK_CLIENT_SECRET is not set or empty")

    data = {
        "grant_type": "client_credentials",
    }

    timeout = httpx.Timeout(10.0, connect=5.0)

    try:
        response = httpx.post(
            token_url,
            data=data,
            auth=(client_id, client_secret),
            timeout=timeout,
        )
        response.raise_for_status()
        token_data = response.json()

        access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 1)  # defaults to expire immediately

        _token_cache.set_token(access_token, expires_in)

        logger.info(f"Successfully obtained RabbitMQ token (expires in {expires_in}s)")
        return access_token

    except httpx.HTTPError as e:
        logger.error(f"Failed to get RabbitMQ token from {token_url}: {e}")
        raise Exception(f"RabbitMQ authentication failed: {e}")
