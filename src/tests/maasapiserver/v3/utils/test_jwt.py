from datetime import datetime, timedelta, timezone
from typing import Sequence

import pytest

from maasapiserver.v3.utils.jwt import InvalidToken, JWT, UserRole


class TestUserModel:
    @pytest.mark.parametrize(
        "key, subject, roles",
        [
            ("123", "aa", []),
            (
                "mykey",
                "myusername",
                [UserRole.USER],
            ),
            (
                "abcdfig",
                "test",
                [UserRole.USER, UserRole.ADMIN],
            ),
            (
                "",
                "",
                [UserRole.USER, UserRole.ADMIN],
            ),
        ],
    )
    def test_create_and_decode(
        self, key: str, subject: str, roles: Sequence[UserRole]
    ) -> None:
        now = datetime.now(timezone.utc)
        token = JWT.create(key, subject, roles)
        assert token.subject == subject
        assert token.roles == roles
        assert token.issued >= now
        assert token.expiration == token.issued + timedelta(minutes=10)
        assert token.issuer == "MAAS"
        assert token.audience == "api"

        decoded_token = JWT.decode(key, token.encoded)
        assert decoded_token == token

    @pytest.mark.parametrize(
        "key, invalid_token",
        [
            # empty payload
            (
                "123",
                "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.KkiNWdzcAgD_0PF169pvBausbptBe1mSQcTorMEqciA",
            ),
            # missing required claims
            (
                "123",
                "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhYSIsImlzcyI6ImFhIn0"
                ".3hIU3UbJTJkok9sJyl4z6X05_uqhKpy6ouRZ3EbJy3Y",
            ),
            # malformed
            ("123", "eyJhbGciOi"),
            # Expired
            (
                "123",
                "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhYSIsImlzcyI6Ik1BQVMiLCJpYXQiOjE3MDk3MjAzMTUsImV4cCI6MTcwOTcyMDkxNSwiYXVkIjoiYXBpIiwicm9sZXMiOltdfQ.DH7XiHnNokJ1dRJK8IZ0YItqZKihV7qzxfA8Mi0WpfI",
            ),
        ],
    )
    def test_decode_invalid(self, key: str, invalid_token: str):
        with pytest.raises(InvalidToken):
            JWT.decode(key, invalid_token)
