#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone

import pytest

from maasservicelayer.utils.api_tokens import (
    floor_to_throttle_window,
    generate_api_token,
    hash_secret,
    parse_api_token,
)


class TestApiTokens:
    def test_generated_token_can_be_parsed(self) -> None:
        generated = generate_api_token()

        parsed = parse_api_token(generated.raw_token)

        assert parsed is not None
        public_id, secret = parsed
        assert public_id == generated.public_id
        assert hash_secret(secret) == generated.secret_hash

    def test_generated_tokens_are_unique(self) -> None:
        assert generate_api_token().raw_token != generate_api_token().raw_token

    @pytest.mark.parametrize(
        "raw_token",
        [
            "",
            "maas_pat_",
            "github_pat_e623c3c3b9b63c3b_" + "a" * 43,
            "maas_pat_e623c3c3b9b63c3b",
            "maas_pat_E623C3C3B9B63C3B_" + "a" * 43,
            "maas_pat_e623c3c3b9b63c3b_" + "a" * 42,
            "maas_pat_e623c3c3b9b63c3b_" + "a" * 42 + "+",
            "maas_pat_e623c3c3b9b63c3b_" + "a" * 43 + "\n",
            "maas_pat_e623c3c3b9b63c3b_" + "a" * 43 + "\r\n",
        ],
    )
    def test_parse_rejects_malformed_tokens(self, raw_token: str) -> None:
        assert parse_api_token(raw_token) is None

    @pytest.mark.parametrize(
        "moment, expected_minute",
        [(35, 30), (30, 30), (9, 0), (59, 50)],
    )
    def test_floor_to_throttle_window(
        self, moment: int, expected_minute: int
    ) -> None:
        floored = floor_to_throttle_window(
            datetime(2026, 11, 3, 13, moment, 42, 5, tzinfo=timezone.utc)
        )
        assert floored == datetime(
            2026, 11, 3, 13, expected_minute, tzinfo=timezone.utc
        )
