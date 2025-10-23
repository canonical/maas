# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
import typing

from pydantic import BaseModel

from maasapiserver.v3.api.public.models.responses.base import PaginatedResponse
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
    def from_model(cls, provider: OAuthProvider) -> typing.Self:
        return cls(
            provider_name=provider.name, auth_url=provider.build_auth_url()
        )


class OAuthProviderResponse(BaseModel):
    kind = "AuthProvider"
    issuer_url: str
    name: str
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: str
    enabled: bool
    id: int

    @classmethod
    def from_model(cls, provider: OAuthProvider) -> typing.Self:
        return cls(
            name=provider.name,
            client_id=provider.client_id,
            client_secret=provider.client_secret,
            issuer_url=provider.issuer_url,
            redirect_uri=provider.redirect_uri,
            scopes=provider.scopes,
            enabled=provider.enabled,
            id=provider.id,
        )


class OAuthProvidersListResponse(PaginatedResponse[OAuthProviderResponse]):
    kind = "AuthProvidersList"
