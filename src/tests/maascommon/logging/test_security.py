# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import hashlib

from maascommon.logging.security import hash_token_for_logging


class TestHashTokenForLogging:
    def test_hash_basic_token(self):
        """Test hashing a basic token string."""
        token = "test-token-123"
        result = hash_token_for_logging(token)

        assert isinstance(result, str)
        assert len(result) == 64
        expected = hashlib.sha256(token.encode()).hexdigest()
        assert result == expected

    def test_hash_consistency(self):
        """Test that the same token always produces the same hash."""
        token = "consistent-token-abc123"
        hash1 = hash_token_for_logging(token)
        hash2 = hash_token_for_logging(token)
        hash3 = hash_token_for_logging(token)

        assert hash1 == hash2 == hash3

    def test_hash_different_tokens(self):
        """Test that different tokens produce different hashes."""
        token1 = "token-one"
        token2 = "token-two"

        hash1 = hash_token_for_logging(token1)
        hash2 = hash_token_for_logging(token2)

        assert hash1 != hash2

    def test_hash_jwt_format(self):
        """Test hashing a JWT-like token format."""
        token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        result = hash_token_for_logging(token)

        assert len(result) == 64
        assert isinstance(result, str)
        expected = hashlib.sha256(token.encode()).hexdigest()
        assert result == expected

    def test_hash_bootstrap_token_format(self):
        """Test hashing a bootstrap token format."""
        token = "bootstrap-secret-" + "x" * 32
        result = hash_token_for_logging(token)

        assert len(result) == 64
        assert isinstance(result, str)
        expected = hashlib.sha256(token.encode()).hexdigest()
        assert result == expected

    def test_hash_empty_string_returns_error_message(self):
        """Test that empty string returns error message."""
        result = hash_token_for_logging("")
        assert result == "<empty_token>"

    def test_hash_whitespace_only_returns_error_message(self):
        """Test that whitespace-only string returns error message."""
        result = hash_token_for_logging("   ")
        assert result == "<empty_token>"
