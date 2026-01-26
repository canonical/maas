# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from enum import StrEnum

from starlette.requests import Request
from starlette.responses import Response

from maasservicelayer.utils.encryptor import Encryptor

MAAS_STATE_COOKIE_NAME = "maas.auth_state_cookie"
MAAS_NONCE_COOKIE_NAME = "maas.auth_nonce_cookie"

# Local token cookies
MAAS_LOCAL_JWT_TOKEN_COOKIE = "maas.local_jwt_token_cookie"
MAAS_LOCAL_REFRESH_TOKEN_COOKIE_NAME = "maas.local_refresh_token_cookie"

# OAuth2 token cookies
MAAS_OAUTH2_ACCESS_TOKEN_COOKIE_NAME = "maas.oauth2_access_token_cookie"
MAAS_OAUTH2_ID_TOKEN_COOKIE_NAME = "maas.oauth2_id_token_cookie"
MAAS_OAUTH2_REFRESH_TOKEN_COOKIE_NAME = "maas.oauth2_refresh_token_cookie"


class MAASLocalCookie(StrEnum):
    JWT_TOKEN = MAAS_LOCAL_JWT_TOKEN_COOKIE
    REFRESH_TOKEN = MAAS_LOCAL_REFRESH_TOKEN_COOKIE_NAME


class MAASOAuth2Cookie(StrEnum):
    AUTH_STATE = MAAS_STATE_COOKIE_NAME
    AUTH_NONCE = MAAS_NONCE_COOKIE_NAME
    OAUTH2_ACCESS_TOKEN = MAAS_OAUTH2_ACCESS_TOKEN_COOKIE_NAME
    OAUTH2_ID_TOKEN = MAAS_OAUTH2_ID_TOKEN_COOKIE_NAME
    OAUTH2_REFRESH_TOKEN = MAAS_OAUTH2_REFRESH_TOKEN_COOKIE_NAME


class EncryptedCookieManager:
    """
    Creates a class for working with encrypted cookies.
    """

    def __init__(
        self,
        request: Request,
        encryptor: Encryptor,
        response: Response | None = None,
        ttl_seconds=3600,
    ):
        self.ttl_seconds = ttl_seconds
        self.request = request
        self.response = response
        self.encryptor = encryptor
        self._pending: list[tuple[str, str, dict]] = []

    def set_auth_cookie(self, key: MAASOAuth2Cookie, value: str) -> None:
        self.set_cookie(
            key=key,
            value=value,
            max_age=self.ttl_seconds,
            httponly=True,
            secure=True,
        )

    def set_cookie(self, key: str, value: str, **opts) -> None:
        encrypted_value = self.encryptor.encrypt(value)
        self._apply_cookie(key, encrypted_value, **opts)

    def set_unsafe_cookie(self, key: str, value: str, **opts) -> None:
        """Sets a cookie without encryption. Use with caution."""
        self._apply_cookie(key, value, **opts)

    def get_unsafe_cookie(self, key: str) -> str | None:
        """Gets a cookie without decryption. Use with caution."""
        return self.request.cookies.get(key)

    def get_cookie(self, key: str) -> str | None:
        encrypted_value = self.request.cookies.get(key)
        if encrypted_value is None:
            return None
        return self.encryptor.decrypt(encrypted_value)

    def clear_cookie(self, key: str) -> None:
        self._apply_cookie(key, "", max_age=0, expires=0)

    def bind_response(self, response: Response) -> None:
        """Binds a response to the cookie manager and sets any pending cookies."""
        self.response = response
        for key, value, opts in self._pending:
            self.response.set_cookie(key=key, value=value, **opts)  # noqa: B026
        self._pending.clear()

    def _apply_cookie(self, key: str, value: str, **opts) -> None:
        """Helper to either set the cookie immediately or queue it."""
        if self.response:
            self.response.set_cookie(key=key, value=value, **opts)
        else:
            self._pending.append((key, value, opts))
