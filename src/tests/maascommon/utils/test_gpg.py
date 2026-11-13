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
            "whatever",
            SAMPLE_GPG_PUBLIC_KEY.replace("PUBLIC", "PRIVATE"),
            SAMPLE_GPG_PUBLIC_KEY.replace("-----END PGP PUBLIC", "-----END"),
            SAMPLE_GPG_PUBLIC_KEY.replace("mDMEav", "mDMEa!"),
            SAMPLE_GPG_PUBLIC_KEY.replace("mDMEav", "mDMEaw"),
            SAMPLE_GPG_PUBLIC_KEY.replace("=N/At", "=!!!!"),
            "-----BEGIN PGP PUBLIC KEY BLOCK-----\n\n"
            "aGVsbG8=\n"
            "-----END PGP PUBLIC KEY BLOCK-----",
        ],
    )
    def test_rejects_invalid_key(self, key: str) -> None:
        with pytest.raises(ValueError):
            validate_gpg_public_key(key)
