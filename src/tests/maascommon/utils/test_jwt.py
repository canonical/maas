# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import base64
import json
import time

import pytest

from maascommon.utils.jwt import decode_unverified_jwt, JWTDecodeError


def create_test_jwt(payload: dict) -> str:
    """Create a simple JWT for testing (no signature verification)."""
    header = {"alg": "HS256", "typ": "JWT"}
    header_encoded = (
        base64.urlsafe_b64encode(json.dumps(header).encode())
        .rstrip(b"=")
        .decode()
    )
    payload_encoded = (
        base64.urlsafe_b64encode(json.dumps(payload).encode())
        .rstrip(b"=")
        .decode()
    )
    signature = "fake_signature"
    return f"{header_encoded}.{payload_encoded}.{signature}"


class TestDecodeUnverifiedJWT:
    def test_decode_valid_token(self):
        payload = {
            "sub": "user123",
            "iss": "test-issuer",
            "aud": "test-audience",
            "exp": int(time.time()) + 3600,
        }
        token = create_test_jwt(payload)
        decoded = decode_unverified_jwt(token, check_expiration=False)
        assert decoded["sub"] == "user123"
        assert decoded["iss"] == "test-issuer"
        assert decoded["aud"] == "test-audience"

    def test_decode_token_without_expiration_check(self):
        payload = {"sub": "user123", "exp": int(time.time()) - 3600}
        token = create_test_jwt(payload)
        decoded = decode_unverified_jwt(token, check_expiration=False)
        assert decoded["sub"] == "user123"

    def test_decode_expired_token_with_check(self):
        payload = {"sub": "user123", "exp": int(time.time()) - 3600}
        token = create_test_jwt(payload)
        with pytest.raises(JWTDecodeError, match="token is expired"):
            decode_unverified_jwt(token, check_expiration=True)

    def test_decode_token_without_exp_claim(self):
        payload = {"sub": "user123"}
        token = create_test_jwt(payload)
        decoded = decode_unverified_jwt(token, check_expiration=True)
        assert decoded["sub"] == "user123"

    @pytest.mark.parametrize(
        "payload_aud, expected_aud",
        [
            ("expected-audience", "expected-audience"),
            (["expected-audience"], "expected-audience"),
            (["expected-audience", "other-audience"], "expected-audience"),
        ],
    )
    def test_decode_token_with_valid_audience(self, payload_aud, expected_aud):
        payload = {"sub": "user123", "aud": payload_aud}
        token = create_test_jwt(payload)
        decoded = decode_unverified_jwt(token, expected_audience=expected_aud)
        assert decoded["sub"] == "user123"

    @pytest.mark.parametrize(
        "payload_aud, expected_aud",
        [
            ("expected-audience", "expected-aud"),
            (["expected-audience"], "expected-aud"),
            (["expected-audience", "other-audience"], "expected-aud"),
            ([], "expected-aud"),
        ],
    )
    def test_decode_token_with_invalid_audience(
        self, payload_aud, expected_aud
    ):
        payload = {"sub": "user123", "aud": payload_aud}
        token = create_test_jwt(payload)
        with pytest.raises(
            JWTDecodeError,
            match=f"invalid audience: expected {expected_aud}, got {payload_aud}",
        ):
            decode_unverified_jwt(token, expected_audience=expected_aud)

    def test_decode_token_missing_audience(self):
        payload = {"sub": "user123"}
        token = create_test_jwt(payload)
        with pytest.raises(
            JWTDecodeError,
            match="invalid audience: expected expected-audience, got None",
        ):
            decode_unverified_jwt(token, expected_audience="expected-audience")

    def test_decode_invalid_format_two_parts(self):
        token = "header.payload"
        with pytest.raises(JWTDecodeError, match="invalid JWT: decode_error"):
            decode_unverified_jwt(token)

    def test_decode_invalid_format_four_parts(self):
        token = "header.payload.signature.extra"
        with pytest.raises(JWTDecodeError, match="invalid JWT: decode_error"):
            decode_unverified_jwt(token)

    def test_decode_invalid_base64_payload(self):
        token = "header.invalid@@@base64.signature"
        with pytest.raises(JWTDecodeError, match="invalid JWT"):
            decode_unverified_jwt(token)

    def test_decode_invalid_json_payload(self):
        invalid_json = base64.urlsafe_b64encode(b"{invalid json}").decode()
        token = f"header.{invalid_json}.signature"
        with pytest.raises(JWTDecodeError, match="invalid JWT"):
            decode_unverified_jwt(token)

    def test_decode_token_with_padding(self):
        payload = {"sub": "user123"}
        header = {"alg": "HS256", "typ": "JWT"}
        header_encoded = base64.urlsafe_b64encode(
            json.dumps(header).encode()
        ).decode()
        payload_json = json.dumps(payload)
        payload_encoded = base64.urlsafe_b64encode(
            payload_json.encode()
        ).decode()
        token = f"{header_encoded}.{payload_encoded}.signature"
        decoded = decode_unverified_jwt(token, check_expiration=False)
        assert decoded["sub"] == "user123"

    def test_decode_token_without_padding(self):
        payload = {"sub": "user123"}
        header = {"alg": "HS256", "typ": "JWT"}
        header_encoded = (
            base64.urlsafe_b64encode(json.dumps(header).encode())
            .rstrip(b"=")
            .decode()
        )
        payload_json = json.dumps(payload)
        payload_encoded = (
            base64.urlsafe_b64encode(payload_json.encode())
            .rstrip(b"=")
            .decode()
        )
        token = f"{header_encoded}.{payload_encoded}.signature"
        decoded = decode_unverified_jwt(token, check_expiration=False)
        assert decoded["sub"] == "user123"

    def test_decode_combined_expiration_and_audience_check(self):
        payload = {
            "sub": "user123",
            "aud": "test-audience",
            "exp": int(time.time()) + 3600,
        }
        token = create_test_jwt(payload)
        decoded = decode_unverified_jwt(
            token,
            check_expiration=True,
            expected_audience="test-audience",
        )
        assert decoded["sub"] == "user123"

    def test_decode_expired_token_with_correct_audience(self):
        payload = {
            "sub": "user123",
            "aud": "test-audience",
            "exp": int(time.time()) - 3600,
        }
        token = create_test_jwt(payload)
        with pytest.raises(JWTDecodeError, match="token is expired"):
            decode_unverified_jwt(
                token,
                check_expiration=True,
                expected_audience="test-audience",
            )
