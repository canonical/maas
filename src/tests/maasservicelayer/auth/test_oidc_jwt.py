#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import MagicMock, patch

from authlib.jose import JWTClaims, KeySet
from authlib.jose.errors import DecodeError, InvalidClaimError
import pytest

from maasservicelayer.auth.oidc_jwt import (
    BaseOAuthToken,
    JWTDecodeException,
    JWTValidationException,
    OAuthIDToken,
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

TEST_KEYSET = KeySet(keys=[])


class TestBaseOAuthToken:
    @patch("maasservicelayer.auth.oidc_jwt.jwt.decode")
    @patch("maasservicelayer.auth.oidc_jwt.BaseOAuthToken.validate")
    async def test_from_token_success(
        self,
        mock_validate: MagicMock,
        mock_decode: MagicMock,
    ):
        mock_decode.return_value = {
            "aud": "abc123",
            "iss": "https://issuer.com",
            "sub": "user1",
            "exp": 9999999999,
            "iat": 1111111111,
        }
        mock_validate.return_value = None

        token = BaseOAuthToken.from_token(
            provider=TEST_PROVIDER,
            encoded="fake_token",
            jwks=TEST_KEYSET,
        )

        assert token.encoded == "fake_token"
        assert token.claims["sub"] == "user1"
        assert token.provider == TEST_PROVIDER

    @patch("maasservicelayer.auth.oidc_jwt.jwt.decode")
    async def test_from_token_decode_error(self, mock_decode: MagicMock):
        mock_decode.side_effect = DecodeError(
            "Failed to decode token: missing required claims."
        )

        with pytest.raises(JWTDecodeException):
            BaseOAuthToken.from_token(
                provider=TEST_PROVIDER,
                encoded="fake_token",
                jwks=TEST_KEYSET,
            )

    @patch("maasservicelayer.auth.oidc_jwt.JWTClaims.validate")
    async def test_validate_success(self, mock_validate: MagicMock):
        mock_claims = JWTClaims(
            header={},
            payload={
                "aud": "abc123",
                "iss": "https://issuer.com",
                "sub": "user1",
                "exp": 9999999999,
                "iat": 1111111111,
            },
        )
        mock_claims.validate = mock_validate
        token = BaseOAuthToken(
            claims=mock_claims,
            encoded="fake_token",
            provider=TEST_PROVIDER,
        )
        token.validate()

        mock_validate.assert_called_once()

    @patch("maasservicelayer.auth.oidc_jwt.JWTClaims.validate")
    async def test_validate_failure(self, mock_validate: MagicMock):
        mock_validate.side_effect = InvalidClaimError("Invalid claim")
        mock_claims = JWTClaims(
            header={},
            payload={
                "aud": "abc123",
                "iss": "https://issuer.com",
                "sub": "user1",
                "alg": "RS256",
            },
        )
        mock_claims.validate = mock_validate
        token = BaseOAuthToken(
            claims=mock_claims,
            encoded="fake_token",
            provider=TEST_PROVIDER,
        )

        with pytest.raises(JWTValidationException):
            token.validate()


class TestOAuthIDToken:
    @patch("maasservicelayer.auth.oidc_jwt.BaseOAuthToken.validate")
    async def test_validate_success(self, mock_validate_super: MagicMock):
        mock_claims = JWTClaims(
            header={"alg": "RS256"},
            payload={
                "aud": "abc123",
                "iss": "https://issuer.com",
                "sub": "user1",
                "nonce": "test_nonce",
            },
        )
        mock_validate_super.return_value = None
        token = OAuthIDToken(
            claims=mock_claims,
            encoded="fake_token",
            provider=TEST_PROVIDER,
        )

        token.validate(nonce="test_nonce")
        mock_validate_super.assert_called_once()

    @patch("maasservicelayer.auth.oidc_jwt.BaseOAuthToken.validate")
    async def test_validate_invalid_claim(
        self, mock_validate_super: MagicMock
    ):
        mock_claims = JWTClaims(
            header={},
            payload={
                "aud": "abc123",
                "iss": "https://issuer.com",
                "sub": "user1",
                "nonce": "wrong_nonce",
            },
        )
        mock_validate_super.return_value = None
        token = OAuthIDToken(
            claims=mock_claims,
            encoded="fake_token",
            provider=TEST_PROVIDER,
        )

        with pytest.raises(JWTValidationException):
            token.validate(nonce="test_nonce")
