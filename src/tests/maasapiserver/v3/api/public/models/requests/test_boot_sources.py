# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import ValidationError
import pytest

from maasapiserver.v3.api.public.models.requests.boot_sources import (
    BootSourceFetchRequest,
)


class TestBootSourceFetchRequest:
    @pytest.mark.parametrize(
        "keyring_path, keyring_data, should_raise",
        [
            (None, "a2V5cmluZ19kYXRh", False),
            ("/tmp/keyrings/a", None, False),
            ("/tmp/keyrings/a", "a2V5cmluZ19kYXRh", True),
        ],
    )
    def test_validate_keyring_fields(
        self,
        keyring_path: str | None,
        keyring_data: str | None,
        should_raise: bool,
    ) -> None:
        """
        Ensure that either `keyring_path` or `keyring_data` is specified,
        never both at the same time.
        """
        if should_raise:
            with pytest.raises(ValidationError):
                BootSourceFetchRequest(
                    url="http://abc.example.com",
                    keyring_path=keyring_path,
                    keyring_data=keyring_data,
                )
        else:
            BootSourceFetchRequest(
                url="http://abc.example.com",
                keyring_path=keyring_path,
                keyring_data=keyring_data,
            )

    @pytest.mark.parametrize(
        "keyring_data, should_raise",
        [
            ("a2V5cmluZ19kYXRh", False),
            ("a2V5-_luZ19kYXRh", True),
        ],
    )
    def test_validate_keyring_data(
        self,
        keyring_data: str | None,
        should_raise: bool,
    ) -> None:
        """Ensure base64-encoding for `keyring_data` is valid."""
        if should_raise:
            with pytest.raises(ValidationError):
                BootSourceFetchRequest(
                    url="http://abc.example.com",
                    keyring_path=None,
                    keyring_data=keyring_data,
                )
        else:
            BootSourceFetchRequest(
                url="http://abc.example.com",
                keyring_path=None,
                keyring_data=keyring_data,
            )
