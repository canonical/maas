# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from base64 import b64encode

from pydantic import ValidationError
import pytest

from maasapiserver.v3.api.public.models.requests.boot_sources import (
    BootSourceFetchRequest,
    BootSourceRequest,
)
from maasservicelayer.exceptions.catalog import ValidationException


class TestBootSourceRequest:
    def test_to_builder(self) -> None:
        bootsource_request = BootSourceRequest(
            url="http://example.com",
            keyring_filename="/path/to/file.gpg",
            priority=102,
            skip_keyring_verification=False,
        )
        builder = bootsource_request.to_builder()

        assert builder.url == "http://example.com"
        assert builder.priority == 102
        assert not builder.skip_keyring_verification

    def test_mandatory_params(self):
        with pytest.raises(ValidationError) as e:
            BootSourceRequest(keyring_filename="/path/to/file.gpg")
        assert len(e.value.errors()) == 2
        assert {"url", "priority"} == set(
            [f["loc"][0] for f in e.value.errors()]
        )

    def test_keyring_validation_missing_both_when_verification_required(self):
        with pytest.raises(ValidationException) as e:
            BootSourceRequest(
                url="http://example.com",
                priority=1,
                skip_keyring_verification=False,
            )
        assert (
            "One of keyring_filename or keyring_data must be specified."
            == e.value.details[0].message
        )

    def test_keyring_validation_given_both_when_verification_required(self):
        with pytest.raises(ValidationException) as e:
            data = b64encode("data".encode("utf-8")).decode("utf-8")
            BootSourceRequest(
                url="http://example.com",
                keyring_filename="/file/to/file.gpg",
                keyring_data=data,
                priority=1,
                skip_keyring_verification=False,
            )
        assert (
            "Only one of keyring_filename or keyring_data can be specified."
            == e.value.details[0].message
        )

    def test_keyring_validation_given_both_when_verification_skipped(self):
        with pytest.raises(ValidationException) as e:
            data = b64encode("data".encode("utf-8")).decode("utf-8")
            BootSourceRequest(
                url="http://example.com",
                keyring_filename="file.gpg",
                keyring_data=data,
                priority=1,
                skip_keyring_verification=True,
            )
        assert (
            "Only one of keyring_filename or keyring_data can be specified."
            == e.value.details[0].message
        )

    def test_keyring_data_valid_base64(self):
        data = b64encode("data".encode("utf-8")).decode("utf-8")
        request = BootSourceRequest(
            url="http://example.com",
            keyring_data=data,
            priority=1,
            skip_keyring_verification=False,
        )
        assert request.keyring_data == data

    def test_keyring_data_invalid_base64(self):
        with pytest.raises(ValidationException) as e:
            BootSourceRequest(
                url="http://example.com",
                keyring_data="not-base64",
                priority=1,
                skip_keyring_verification=True,
            )
        assert (
            "keyring_data must be valid Base64 encoded binary data."
            == e.value.details[0].message
        )

    def test_invalid_url_raises(self):
        with pytest.raises(ValidationException) as e:
            BootSourceRequest(
                url="not-a-valid-url",
                priority=1,
                skip_keyring_verification=True,
            )
        assert (
            "URL must be a valid HTTP or HTTPS address."
            == e.value.details[0].message
        )

    def test_negative_priority_raises(self):
        with pytest.raises(ValidationException) as e:
            BootSourceRequest(
                url="http://example.com",
                keyring_filename="keyring.gpg",
                priority=-1,
                skip_keyring_verification=False,
            )
        assert (
            "Priority must be a non-negative integer."
            == e.value.details[0].message
        )

    def test_verification_skipped_and_no_keyring_fields(self):
        request = BootSourceRequest(
            url="http://example.com",
            priority=1,
            skip_keyring_verification=True,
        )
        assert request.url == "http://example.com"
        assert request.keyring_filename == ""
        assert request.keyring_data == ""
        assert request.skip_keyring_verification is True

    def test_verification_skipped_with_only_filename(self):
        request = BootSourceRequest(
            url="http://example.com",
            keyring_filename="mykeyring.gpg",
            priority=1,
            skip_keyring_verification=True,
        )
        assert request.keyring_filename == "mykeyring.gpg"
        assert request.keyring_data == ""

    def test_verification_skipped_with_only_data(self):
        data = b64encode("data".encode("utf-8")).decode("utf-8")
        request = BootSourceRequest(
            url="http://example.com",
            keyring_data=data,
            priority=1,
            skip_keyring_verification=True,
        )
        assert request.keyring_filename == ""
        assert request.keyring_data == data


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
        assert "keyring_data must be valid Base64 encoded binary data"
