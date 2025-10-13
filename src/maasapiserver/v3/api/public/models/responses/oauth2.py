# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import BaseModel

from maasservicelayer.models.external_auth import OAuthProvider


class AccessTokenResponse(BaseModel):
    """Content for a response returning a JWT."""

    kind = "AccessToken"
    token_type: str
    access_token: str


class AuthProviderInfoResponse(BaseModel):
    """Content for a response returning info about a pre-configured OIDC provider"""

    kind = "AuthProviderInfo"
    auth_url: str
    provider_name: str

    @classmethod
    def from_model(cls, provider: OAuthProvider) -> "AuthProviderInfoResponse":
        return cls(
            provider_name=provider.name, auth_url=provider.build_auth_url()
        )
