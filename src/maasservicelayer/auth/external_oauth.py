# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass

from authlib.common.security import generate_token
from authlib.integrations.httpx_client import AsyncOAuth2Client

from maasservicelayer.models.external_auth import OAuthProvider


@dataclass
class OAuthInitiateData:
    authorization_url: str
    state: str
    nonce: str


class OAuth2Client:
    """
    Creates an OAuth2 Client that can interact with an external OIDC provider.
    """

    def __init__(self, provider: OAuthProvider):
        self.client = AsyncOAuth2Client(
            client_id=provider.client_id,
            client_secret=provider.client_secret,
            redirect_uri=provider.redirect_uri,
            scope=provider.scopes,
        )
        self.provider = provider

    def generate_authorization_url(self) -> OAuthInitiateData:
        nonce = generate_token()
        auth_url, state = self.client.create_authorization_url(
            url=f"{self.provider.issuer_url}/authorize", nonce=nonce
        )
        return OAuthInitiateData(
            authorization_url=auth_url,
            state=state,
            nonce=nonce,
        )

    def get_provider_name(self) -> str:
        return self.provider.name
