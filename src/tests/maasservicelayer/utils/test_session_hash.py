# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.utils.session_hash import get_session_auth_hash


class TestSessionHash:
    SAMPLE_HASH = (
        "7d317d79cc1e6a087493e762830c08e126cb8df9e9c2b9ad939df5faeebd5e62"
    )

    def test_get_session_auth_hash(self):
        password = "hashed_password"
        assert get_session_auth_hash(password) == self.SAMPLE_HASH

    def test_str_and_bytes_produce_same_hash(self):
        assert get_session_auth_hash(
            "hashed_password"
        ) == get_session_auth_hash(b"hashed_password")
