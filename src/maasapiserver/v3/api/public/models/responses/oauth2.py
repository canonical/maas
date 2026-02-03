# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
import base64
import typing

from pydantic import BaseModel

from maasapiserver.v3.api.public.models.responses.base import PaginatedResponse
from maasservicelayer.models.external_auth import (
    OAuthProvider,
    ProviderMetadata,
)


class TokenResponse(BaseModel):
    """Content for a response returning a JWT and a refresh token."""

    kind = "Tokens"
    token_type: str
    access_token: str
    refresh_token: str | None = None


class PreLoginInfoResponse(BaseModel):
    """Content for a response returning pre-login information."""

    kind = "PreLoginInfo"
    is_authenticated: bool
    no_users: bool


class AuthInfoResponse(BaseModel):
    """Content for a response returning authentication flow information."""

    kind = "AuthInfo"
    auth_url: str | None = None
    provider_name: str | None = None
    is_oidc: bool


class CallbackTargetResponse(BaseModel):
    """Content for a response returning the callback target URL."""

    kind = "CallbackTarget"
    redirect_target: str

    @classmethod
    def from_state(cls, state: str) -> typing.Self:
        encoded_redirect, _ = state.split(".", 1)
        return cls(
            redirect_target=base64.urlsafe_b64decode(
                encoded_redirect.encode()
            ).decode()
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
    metadata: ProviderMetadata
    user_count: int | None

    @classmethod
    def from_model(
        cls, provider: OAuthProvider, user_count: int | None = None
    ) -> typing.Self:
        return cls(
            name=provider.name,
            client_id=provider.client_id,
            client_secret=provider.client_secret,
            issuer_url=provider.issuer_url,
            redirect_uri=provider.redirect_uri,
            scopes=provider.scopes,
            enabled=provider.enabled,
            metadata=provider.metadata,
            id=provider.id,
            user_count=user_count,
        )


class OAuthProvidersListResponse(PaginatedResponse[OAuthProviderResponse]):
    kind = "AuthProvidersList"
