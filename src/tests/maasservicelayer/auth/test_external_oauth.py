#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import urllib.parse

from authlib.jose import JWTClaims, KeySet
from authlib.jose.errors import BadSignatureError
from httpx import HTTPStatusError, Request, Response
import pytest

from maasservicelayer.auth.external_oauth import (
    OAuth2Client,
    OAuthCallbackData,
    OAuthTokenData,
    OAuthUserData,
)
from maasservicelayer.auth.oidc_jwt import OAuthAccessToken, OAuthIDToken
from maasservicelayer.exceptions.catalog import (
    BadGatewayException,
    UnauthorizedException,
)
from maasservicelayer.exceptions.constants import (
    PROVIDER_COMMUNICATION_FAILED_VIOLATION_TYPE,
)
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
        authorization_endpoint="https://issuer.com/authorize",
        token_endpoint="https://issuer.com/token",
        jwks_uri="https://issuer.com/jwks",
    ),
)


class TestOauth2Client:
    def test_generate_authorization_url(self) -> None:
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

    @patch("maasservicelayer.auth.oidc_jwt.OAuthIDToken.from_token")
    async def test__validate_id_token_success(
        self, mock_from_token: MagicMock
    ):
        client = OAuth2Client(TEST_PROVIDER)
        client._get_provider_jwks = AsyncMock(return_value="fake_jwks")

        mock_token_instance = Mock()
        mock_token_instance.validate = Mock(return_value=None)
        mock_from_token.return_value = mock_token_instance

        await client._validate_id_token("valid_token", nonce="testnonce")

        mock_from_token.assert_called_once_with(
            provider=TEST_PROVIDER,
            encoded="valid_token",
            jwks="fake_jwks",
            nonce="testnonce",
        )

    @patch("maasservicelayer.auth.oidc_jwt.OAuthIDToken.from_token")
    async def test__validate_id_token_retries_with_new_jwks(
        self, mock_from_token: MagicMock
    ):
        client = OAuth2Client(TEST_PROVIDER)
        client._get_provider_jwks = AsyncMock(
            side_effect=["stale_jwks", "fresh_jwks"]
        )

        mock_token_instance = Mock()
        mock_token_instance.validate = Mock(return_value=None)
        mock_from_token.side_effect = [
            BadSignatureError("Invalid signature"),
            mock_token_instance,
        ]

        await client._validate_id_token("valid_token", nonce="testnonce")

        assert mock_from_token.call_count == 2
        mock_from_token.assert_any_call(
            provider=TEST_PROVIDER,
            encoded="valid_token",
            jwks="stale_jwks",
            nonce="testnonce",
        )
        mock_from_token.assert_any_call(
            provider=TEST_PROVIDER,
            encoded="valid_token",
            jwks="fresh_jwks",
            nonce="testnonce",
        )

    @patch("maasservicelayer.auth.oidc_jwt.OAuthAccessToken.from_token")
    async def test_validate_access_token_jwt(
        self, mock_from_token: MagicMock
    ) -> None:
        client = OAuth2Client(TEST_PROVIDER)
        client._get_provider_jwks = AsyncMock(return_value="fake_jwks")

        mock_token_instance = Mock()

        mock_from_token.return_value = (
            mock_token_instance  # async will await this
        )

        await client.validate_access_token("abc.def.ghi")

        mock_from_token.assert_called_once_with(
            provider=TEST_PROVIDER,
            encoded="abc.def.ghi",
            jwks="fake_jwks",
        )

    async def test_validate_access_token_fallback_to_introspection(
        self,
    ) -> None:
        TEST_PROVIDER.metadata.introspection_endpoint = (
            "https://issuer.com/introspect"
        )
        client = OAuth2Client(TEST_PROVIDER)
        client._introspect_token = AsyncMock(return_value={"active": True})

        await client.validate_access_token("some_opaque_token")

        client._introspect_token.assert_awaited_once_with(
            url=TEST_PROVIDER.metadata.introspection_endpoint,
            access_token="some_opaque_token",
        )

    async def test_callback(self) -> None:
        client = OAuth2Client(TEST_PROVIDER)
        client._fetch_and_validate_tokens = AsyncMock(
            return_value=OAuthTokenData(
                access_token=OAuthAccessToken(
                    claims=Mock(),
                    encoded="access_token_value",
                    provider=TEST_PROVIDER,
                ),
                id_token=OAuthIDToken(
                    claims=Mock(),
                    encoded="id_token_value",
                    provider=TEST_PROVIDER,
                ),
                refresh_token="refresh_token_value",
            )
        )
        client.get_userinfo = AsyncMock(
            return_value=OAuthUserData(
                sub="user123",
                email="john.doe@example.com",
                given_name="John",
                family_name="Doe",
                name="John Doe",
            )
        )

        response = await client.callback(
            code="auth_code_value", nonce="testnonce"
        )

        assert isinstance(response, OAuthCallbackData)
        assert isinstance(response.tokens, OAuthTokenData)
        assert isinstance(response.user_info, OAuthUserData)
        assert response.tokens.access_token.encoded == "access_token_value"  # type: ignore
        assert response.tokens.id_token.encoded == "id_token_value"
        assert response.tokens.refresh_token == "refresh_token_value"
        assert response.user_info.sub == "user123"

    async def get_userinfo_has_endpoint(self) -> None:
        client = OAuth2Client(TEST_PROVIDER)
        client._request = AsyncMock(
            return_value={
                "sub": "user123",
                "email": "john.doe@example.com",
                "given_name": "John",
                "family_name": "Doe",
                "name": "John Doe",
                "locale": "en-US",
            }
        )
        response = await client.get_userinfo(
            access_token="access_token_value",
            id_token_claims=Mock(),
        )

        assert isinstance(response, OAuthUserData)
        assert response.sub == "user123"
        assert response.email == "john.doe@example.com"
        assert response.given_name == "John"
        assert response.family_name == "Doe"
        assert response.name == "John Doe"
        assert not hasattr(response, "locale")

    async def test_get_userinfo_fallback_to_claims(self) -> None:
        TEST_PROVIDER.metadata.userinfo_endpoint = None
        client = OAuth2Client(TEST_PROVIDER)
        client._request = AsyncMock()

        mock_claims = {
            "sub": "user123",
            "email": "john.doe@example.com",
            "given_name": "John",
            "family_name": "Doe",
            "name": "John Doe",
        }

        response = await client.get_userinfo(
            access_token="access_token_value",
            id_token_claims=JWTClaims(header={}, payload=mock_claims),
        )

        assert isinstance(response, OAuthUserData)
        assert response.sub == "user123"
        assert response.email == "john.doe@example.com"
        assert response.given_name == "John"
        assert response.family_name == "Doe"
        assert response.name == "John Doe"

    async def test_get_userinfo_sub_mismatch_raises_exception(self) -> None:
        TEST_PROVIDER.metadata.userinfo_endpoint = (
            "https://issuer.com/userinfo"
        )
        client = OAuth2Client(TEST_PROVIDER)
        client._request = AsyncMock(
            return_value={
                "sub": "different_user",
            }
        )
        mock_claims = JWTClaims(
            header={},
            payload={
                "sub": "user123",
            },
        )
        with pytest.raises(UnauthorizedException):
            await client.get_userinfo(
                access_token="access_token_value",
                id_token_claims=mock_claims,
            )

    async def test__fetch_and_validate_tokens_success(self) -> None:
        client = OAuth2Client(TEST_PROVIDER)
        client.client.fetch_token = AsyncMock(
            return_value={
                "access_token": "access_token_value",
                "id_token": "id_token_value",
                "refresh_token": "refresh_token_value",
            }
        )
        client._validate_id_token = AsyncMock(
            return_value=OAuthIDToken(
                claims=Mock(),
                encoded="id_token_value",
                provider=TEST_PROVIDER,
            )
        )
        client.validate_access_token = AsyncMock(
            return_value=OAuthAccessToken(
                claims=Mock(),
                encoded="access_token_value",
                provider=TEST_PROVIDER,
            )
        )

        response = await client._fetch_and_validate_tokens(
            code="auth_code_value", nonce="testnonce"
        )

        assert isinstance(response, OAuthTokenData)
        assert response.access_token.encoded == "access_token_value"  # type: ignore
        assert response.id_token.encoded == "id_token_value"
        assert response.refresh_token == "refresh_token_value"

    async def test__fetch_and_validate_tokens_http_status_error(self) -> None:
        client = OAuth2Client(TEST_PROVIDER)
        client.client.fetch_token = AsyncMock(
            side_effect=HTTPStatusError(
                "Error fetching tokens",
                request=Request("POST", url="https://issuer.com/token"),
                response=Response(status_code=400),
            )
        )

        with pytest.raises(BadGatewayException) as exc_info:
            await client._fetch_and_validate_tokens(
                code="auth_code_value", nonce="testnonce"
            )
        assert (
            exc_info.value.details[0].type  # type: ignore
            == PROVIDER_COMMUNICATION_FAILED_VIOLATION_TYPE
        )
        assert (
            exc_info.value.details[0].message  # type: ignore
            == "Failed to fetch tokens from OIDC server."
        )

    async def test__fetch_and_validate_tokens_missing_tokens(self) -> None:
        client = OAuth2Client(TEST_PROVIDER)
        client.client.fetch_token = AsyncMock(
            return_value={
                "access_token": "access_token_value",
                "id_token": "id_token_value",
            }
        )
        with pytest.raises(BadGatewayException) as exc_info:
            await client._fetch_and_validate_tokens(
                code="auth_code_value", nonce="testnonce"
            )
        assert (
            exc_info.value.details[0].type  # type: ignore
            == PROVIDER_COMMUNICATION_FAILED_VIOLATION_TYPE
        )
        assert (
            exc_info.value.details[0].message  # type: ignore
            == "Invalid token response from OIDC server. Please ensure the provider is configured correctly."
        )

    async def test__get_provider_jwks_no_cache(self) -> None:
        client = OAuth2Client(TEST_PROVIDER)
        test_jwks_text = json.dumps(
            {
                "keys": [
                    {
                        "kty": "RSA",
                        "kid": "test-key",
                        "use": "sig",
                        "alg": "RS256",
                        "n": "sXch-9X6c7v9k1k5-Yh0u7iDQoL1jN1kG4V5aSgZkGZfiOuV0OWq5mLzEJ-6uH1AxlXW2g0QkOz6K_XfG4Mkzjh2wDzg50u8bW2ULa0_HpRmVJjQykzq3GzqL6T2VZ7Y1rHzQ9mC8zv3Xc-8Kj1eGkLdKEMIh_EW4nWz6GBaIqPYbV-o",
                        "e": "AQAB",
                    }
                ]
            }
        )
        client._request = AsyncMock(return_value=test_jwks_text)

        response = await client._get_provider_jwks()

        client._request.assert_awaited_once_with(
            url="https://issuer.com/jwks",
        )
        assert isinstance(response, KeySet)

    async def test__get_provider_jwks_cached(self) -> None:
        client = OAuth2Client(TEST_PROVIDER)
        client._jwks_cache_time = utcnow().timestamp()
        fake_jwks = KeySet(
            keys=[
                {
                    "kty": "RSA",
                    "kid": "test-key",
                    "use": "sig",
                    "alg": "RS256",
                    "n": "sXch-9X6c7v9k1k5-Yh0u7iDQoL1jN1kG4V5aSgZkGZfiOuV0OWq5mLzEJ-6uH1AxlXW2g0QkOz6K_XfG4Mkzjh2wDzg50u8bW2ULa0_HpRmVJjQykzq3GzqL6T2VZ7Y1rHzQ9mC8zv3Xc-8Kj1eGkLdKEMIh_EW4nWz6GBaIqPYbV-o",
                    "e": "AQAB",
                }
            ]
        )
        client._jwks_cache = fake_jwks
        client._request = AsyncMock()

        response = await client._get_provider_jwks()

        client._request.assert_not_awaited()
        assert response == fake_jwks

    async def test__get_provider_jwks_raises_exception(self) -> None:
        client = OAuth2Client(TEST_PROVIDER)
        client._request = AsyncMock(
            side_effect=HTTPStatusError(
                "Error fetching JWKS",
                request=Request("GET", url="https://issuer.com/jwks"),
                response=Response(status_code=500),
            )
        )

        with pytest.raises(BadGatewayException) as exc_info:
            await client._get_provider_jwks()
        assert (
            exc_info.value.details[0].type  # type: ignore
            == PROVIDER_COMMUNICATION_FAILED_VIOLATION_TYPE
        )
        assert (
            exc_info.value.details[0].message  # type: ignore
            == "Failed to retrieve JWKS from OIDC server."
        )

    async def test__client_request_success(self) -> None:
        client = OAuth2Client(TEST_PROVIDER)
        test_response = Response(
            status_code=200,
            content='{"key": "value"}',
            request=Request("GET", url="https://issuer.com/some_endpoint"),
        )

        client.client.get = AsyncMock(return_value=test_response)

        response = await client._request(
            url="https://issuer.com/some_endpoint",
        )
        client.client.get.assert_awaited_once()
        assert response == {"key": "value"}

    async def test__client_request_failure(self) -> None:
        client = OAuth2Client(TEST_PROVIDER)
        test_response = Response(
            status_code=500,
            content="Internal Server Error",
            request=Request("GET", url="https://issuer.com/some_endpoint"),
        )

        client.client.get = AsyncMock(return_value=test_response)

        with pytest.raises(HTTPStatusError):
            await client._request(
                url="https://issuer.com/some_endpoint",
            )
        client.client.get.assert_awaited_once()
