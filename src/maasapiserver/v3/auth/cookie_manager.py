# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from enum import StrEnum

from starlette.requests import Request
from starlette.responses import Response

from maasservicelayer.utils.encryptor import Encryptor

MAAS_STATE_COOKIE_NAME = "maas.auth_state_cookie"
MAAS_NONCE_COOKIE_NAME = "maas.auth_nonce_cookie"


class MAASOAuth2Cookie(StrEnum):
    AUTH_STATE = MAAS_STATE_COOKIE_NAME
    AUTH_NONCE = MAAS_NONCE_COOKIE_NAME


class EncryptedCookieManager:
    """
    Creates a class for working with encrypted cookies.
    """

    def __init__(
        self,
        request: Request,
        response: Response,
        encryptor: Encryptor,
        ttl_seconds=3600,
    ):
        self.ttl_seconds = ttl_seconds
        self.request = request
        self.response = response
        self.encryptor = encryptor

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
        self.response.set_cookie(key=key, value=encrypted_value, **opts)

    def get_cookie(self, key: str) -> str | None:
        encrypted_value = self.request.cookies.get(key)
        if encrypted_value is None:
            return None
        return self.encryptor.decrypt(encrypted_value)
