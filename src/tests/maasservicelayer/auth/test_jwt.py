# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta

import pytest

from maasservicelayer.auth.jwt import InvalidToken, JWT
from maasservicelayer.utils.date import utcnow


class TestJWT:
    @pytest.mark.parametrize(
        "key, subject, user_id",
        [
            ("123", "aa", 0),
            ("mykey", "myusername", 0),
            ("abcdfig", "test", 1),
            ("", "", 3),
        ],
    )
    def test_create_and_decode(
        self, key: str, subject: str, user_id: int
    ) -> None:
        now = utcnow()
        token = JWT.create(key, subject, user_id)
        assert token.subject == subject
        assert token.user_id == user_id
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
