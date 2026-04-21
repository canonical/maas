# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from base64 import b64encode
from unittest.mock import Mock

from pydantic import ValidationError
import pytest

from maasapiserver.v3.api.public.models.requests.boot_sources import (
    BootSourceCreateRequest,
    BootSourceRequest,
    BootSourceUpdateRequest,
    validate_priority,
    validate_url_format,
)
from maasservicelayer.exceptions.catalog import ValidationException
from maasservicelayer.models.bootsources import BootSource
from maasservicelayer.services.boot_sources import BootSourcesService
from maasservicelayer.utils.date import utcnow


class TestValidators:
    def test_invalid_url_raises(self):
        with pytest.raises(ValidationException) as e:
            validate_url_format("not-a-valid-url")
        assert (
            "URL must be a valid HTTP or HTTPS address."
            == e.value.details[0].message
        )

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("http://example.com/", "http://example.com"),
            ("http://example.com///", "http://example.com"),
            ("http://example.com", "http://example.com"),
        ],
    )
    def test_url_trailing_slash_stripped(self, url, expected):
        assert validate_url_format(url) == expected

    @pytest.mark.asyncio
    async def test_negative_priority_raises(self, services_mock):
        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.exists.return_value = False
        with pytest.raises(ValidationException) as e:
            await validate_priority(-1, services_mock)
        assert (
            "Priority must be a non-negative integer."
            == e.value.details[0].message
        )

    @pytest.mark.asyncio
    async def test_priority_already_exists_raises(self, services_mock):
        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.exists.return_value = True
        with pytest.raises(ValidationException) as e:
            await validate_priority(2, services_mock)
        assert (
            "A boot source with the same priority already exists."
            == e.value.details[0].message
        )


class TestBootSourceRequest:
    def test_keyring_validation_missing_both_when_verification_required(self):
        with pytest.raises(ValidationException) as e:
            BootSourceRequest(
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
                keyring_filename="/file/to/file.gpg",
                keyring_data=data,
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
                keyring_filename="file.gpg",
                keyring_data=data,
                skip_keyring_verification=True,
            )
        assert (
            "Only one of keyring_filename or keyring_data can be specified."
            == e.value.details[0].message
        )

    def test_keyring_data_valid_base64(self):
        data = b64encode("data".encode("utf-8")).decode("utf-8")
        request = BootSourceRequest(
            keyring_data=data,
            skip_keyring_verification=False,
        )
        assert request.keyring_data == data

    def test_keyring_data_invalid_base64(self):
        with pytest.raises(ValidationException) as e:
            BootSourceRequest(
                keyring_data="not-base64",
                skip_keyring_verification=True,
            )
        assert (
            "keyring_data must be valid Base64 encoded binary data."
            == e.value.details[0].message
        )

    def test_verification_skipped_and_no_keyring_fields(self):
        request = BootSourceRequest(
            skip_keyring_verification=True,
        )
        assert request.keyring_filename == ""
        assert request.keyring_data == ""
        assert request.skip_keyring_verification is True

    def test_verification_skipped_with_only_filename(self):
        request = BootSourceRequest(
            keyring_filename="mykeyring.gpg",
            skip_keyring_verification=True,
        )
        assert request.keyring_filename == "mykeyring.gpg"
        assert request.keyring_data == ""

    def test_verification_skipped_with_only_data(self):
        data = b64encode("data".encode("utf-8")).decode("utf-8")
        request = BootSourceRequest(
            keyring_data=data,
            skip_keyring_verification=True,
        )
        assert request.keyring_filename == ""
        assert request.keyring_data == data


class TestBootSourceCreateRequest:
    @pytest.mark.asyncio
    async def test_to_builder(self, services_mock) -> None:
        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.exists.return_value = False
        bootsource_request = BootSourceCreateRequest(
            name="My Boot Source",
            url="http://example.com",
            keyring_filename="/path/to/file.gpg",
            priority=102,
            skip_keyring_verification=False,
            enabled=True,
        )
        builder = await bootsource_request.to_builder(services_mock)

        assert builder.name == "My Boot Source"
        assert builder.url == "http://example.com"
        assert builder.priority == 102
        assert not builder.skip_keyring_verification
        assert builder.enabled is True

    def test_mandatory_params(self):
        with pytest.raises(ValidationError) as e:
            BootSourceCreateRequest(keyring_filename="/path/to/file.gpg")
        assert len(e.value.errors()) == 4
        assert {"url", "priority", "name", "enabled"} == set(
            [f["loc"][0] for f in e.value.errors()]
        )


class TestBootSourceUpdateRequest:
    def test_mandatory_params(self):
        with pytest.raises(ValidationError) as e:
            BootSourceUpdateRequest(keyring_filename="/path/to/file.gpg")
        assert {"url", "priority", "name", "enabled"} == set(
            [f["loc"][0] for f in e.value.errors()]
        )

    @pytest.mark.asyncio
    async def test_to_builder(self, services_mock) -> None:
        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.exists.return_value = False
        instance = BootSource(
            id=1,
            created=utcnow(),
            updated=utcnow(),
            name="Old Name",
            url="http://example.com",
            keyring_filename="/path/to/file.gpg",
            keyring_data=b"",
            priority=50,
            skip_keyring_verification=False,
            enabled=True,
        )
        bootsource_request = BootSourceUpdateRequest(
            name="My Boot Source",
            url="http://example.com",
            keyring_filename="/path/to/file.gpg",
            priority=102,
            skip_keyring_verification=False,
            enabled=False,
        )
        builder = await bootsource_request.to_builder(services_mock, instance)

        assert builder.name == "My Boot Source"
        assert builder.priority == 102
        assert not builder.skip_keyring_verification
        assert builder.enabled is False

    @pytest.mark.asyncio
    async def test_to_builder_rejects_url_change(self, services_mock) -> None:
        services_mock.boot_sources = Mock(BootSourcesService)
        instance = BootSource(
            id=1,
            created=utcnow(),
            updated=utcnow(),
            name="Source",
            url="http://original.example.com",
            keyring_filename="/path/to/file.gpg",
            keyring_data=b"",
            priority=10,
            skip_keyring_verification=False,
            enabled=True,
        )
        bootsource_request = BootSourceUpdateRequest(
            name="Source",
            url="http://different.example.com",
            keyring_filename="/path/to/file.gpg",
            priority=10,
            skip_keyring_verification=False,
            enabled=True,
        )
        with pytest.raises(ValidationException) as e:
            await bootsource_request.to_builder(services_mock, instance)
        assert (
            "URL of a boot source is immutable." == e.value.details[0].message
        )

    @pytest.mark.asyncio
    async def test_to_builder_skips_priority_validation_when_unchanged(
        self, services_mock
    ) -> None:
        services_mock.boot_sources = Mock(BootSourcesService)
        instance = BootSource(
            id=1,
            created=utcnow(),
            updated=utcnow(),
            name="Source",
            url="http://example.com",
            keyring_filename="/path/to/file.gpg",
            keyring_data=b"",
            priority=10,
            skip_keyring_verification=False,
            enabled=True,
        )
        bootsource_request = BootSourceUpdateRequest(
            name="Source",
            url="http://example.com",
            keyring_filename="/path/to/file.gpg",
            priority=10,
            skip_keyring_verification=False,
            enabled=True,
        )
        builder = await bootsource_request.to_builder(services_mock, instance)
        assert builder.priority == 10
        services_mock.boot_sources.exists.assert_not_called()
