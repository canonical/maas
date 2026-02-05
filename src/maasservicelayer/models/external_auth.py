#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from enum import IntEnum

from pydantic import BaseModel

from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)


class RootKey(MaasTimestampedBaseModel):
    expiration: datetime


class ProviderMetadata(BaseModel):
    # These fields are based on the OpenID Connect Discovery specification (https://openid.net/specs/openid-connect-discovery-1_0.html#ProviderMetadata)
    # We only include the fields that are relevant for our use case, but additional fields can be added as needed.
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str | None = None
    introspection_endpoint: str | None = None
    revocation_endpoint: str | None = None
    jwks_uri: str


class AccessTokenType(IntEnum):
    JWT = 0
    OPAQUE = 1


@generate_builder()
class OAuthProvider(MaasTimestampedBaseModel):
    issuer_url: str
    name: str
    client_id: str
    client_secret: str
    redirect_uri: str
    token_type: AccessTokenType
    scopes: str
    enabled: bool
    metadata: ProviderMetadata
