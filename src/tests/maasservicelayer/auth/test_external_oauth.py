#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import urllib.parse

from maasservicelayer.auth.external_oauth import OAuth2Client
from maasservicelayer.models.external_auth import (
    OAuthProvider,
    ProviderMetadata,
)
from maasservicelayer.utils.date import utcnow

TEST_PROVIDER = OAuthProvider(
    id=1,
    name="Test provider",
    client_id="abc123",
    client_secret="2be32df",
    scopes="openid profile email",
    issuer_url="https://issuer.com",
    redirect_uri="https://example.com/callback",
    created=utcnow(),
    updated=utcnow(),
    enabled=True,
    metadata=ProviderMetadata(
        authorization_endpoint="",
        token_endpoint="",
        jwks_uri="",
    ),
)


class TestOauth2Client:
    def test_generate_authorization_url(self) -> None:
        TEST_PROVIDER.metadata = ProviderMetadata(
            authorization_endpoint="https://issuer.com/authorize",
            token_endpoint="https://issuer.com/token",
            jwks_uri="https://issuer.com/jwks",
        )
        client = OAuth2Client(TEST_PROVIDER)
        data = client.generate_authorization_url()
        expected_scope = "+".join(TEST_PROVIDER.scopes.split(" "))
        expected_url = (
            TEST_PROVIDER.issuer_url
            + "/authorize?response_type=code"
            + "&client_id="
            + TEST_PROVIDER.client_id
            + "&redirect_uri="
            + urllib.parse.quote_plus(TEST_PROVIDER.redirect_uri)
            + "&scope="
            + expected_scope
            + "&state="
            + data.state
            + "&nonce="
            + data.nonce
        )
        assert data.authorization_url == expected_url

    def test_get_provider_name(self) -> None:
        client = OAuth2Client(TEST_PROVIDER)
        assert client.get_provider_name() == TEST_PROVIDER.name
