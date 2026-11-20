#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import pytest

from maascommon.utils.gpg import validate_gpg_public_key
from maastesting.gpg import SAMPLE_GPG_PUBLIC_KEY


class TestValidateGpgPublicKey:
    def test_accepts_valid_key(self) -> None:
        validate_gpg_public_key(SAMPLE_GPG_PUBLIC_KEY)

    def test_accepts_valid_key_with_armor_headers(self) -> None:
        key = SAMPLE_GPG_PUBLIC_KEY.replace(
            "BLOCK-----\n", "BLOCK-----\nComment: test\n", 1
        )
        validate_gpg_public_key(key)

    def test_accepts_valid_key_without_checksum(self) -> None:
        key = SAMPLE_GPG_PUBLIC_KEY.replace("=N/At\n", "")
        validate_gpg_public_key(key)

    @pytest.mark.parametrize(
        "key",
        [
            SAMPLE_GPG_PUBLIC_KEY.replace("BLOCK-----\n\n", "BLOCK-----\n"),
            SAMPLE_GPG_PUBLIC_KEY.replace(
                "BLOCK-----\n\n", "BLOCK-----\nComment: test\n"
            ),
        ],
    )
    def test_rejects_missing_blank_line_after_header(self, key: str) -> None:
        with pytest.raises(ValueError, match="blank line"):
            validate_gpg_public_key(key)

    @pytest.mark.parametrize(
        "key",
        [
            "whatever",
            SAMPLE_GPG_PUBLIC_KEY.replace("PUBLIC", "PRIVATE"),
            SAMPLE_GPG_PUBLIC_KEY.replace("-----END PGP PUBLIC", "-----END"),
            SAMPLE_GPG_PUBLIC_KEY.replace("mDMEav", "mDMEa!"),
            "-----BEGIN PGP PUBLIC KEY BLOCK-----\n\n"
            "-----END PGP PUBLIC KEY BLOCK-----",
        ],
    )
    def test_rejects_invalid_key(self, key: str) -> None:
        with pytest.raises(ValueError):
            validate_gpg_public_key(key)
