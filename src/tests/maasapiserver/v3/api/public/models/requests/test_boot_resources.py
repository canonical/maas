#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from unittest.mock import MagicMock, Mock, patch

import pytest

from maasapiserver.v3.api.public.models.requests.boot_resources import (
    BootResourceCreateRequest,
    BootResourceFileTypeChoice,
    CustomImageFilterParams,
)
from maascommon.enums.boot_resources import BootResourceType
from maasservicelayer.builders.bootresources import BootResourceBuilder
from maasservicelayer.db.repositories.bootresources import (
    BootResourceClauseFactory,
)
from maasservicelayer.exceptions.catalog import ValidationException
from maasservicelayer.models.bootresources import BootResource
from maasservicelayer.models.bootsources import BootSourceCacheOSRelease
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.bootresources import BootResourceService
from maasservicelayer.services.bootsourcecache import BootSourceCacheService
from maasservicelayer.services.configurations import ConfigurationsService
from maastesting.factory import factory


class TestBootResourceCreateRequest:
    @patch(
        "maasapiserver.v3.api.public.models.requests.boot_resources.BootResourceCreateRequest._validate_architecture"
    )
    @patch(
        "maasapiserver.v3.api.public.models.requests.boot_resources.BootResourceCreateRequest._validate_base_image"
    )
    @patch(
        "maasapiserver.v3.api.public.models.requests.boot_resources.BootResourceCreateRequest._validate_name"
    )
    async def test_to_builder(
        self,
        validate_name_mock: MagicMock,
        validate_base_image_mock: MagicMock,
        validate_architecture_mock: MagicMock,
    ) -> None:
        services_mock = Mock(ServiceCollectionV3)

        request = BootResourceCreateRequest(
            name="test-name",
            sha256="test-sha256",
            architecture="amd64/generic",
            file_type=BootResourceFileTypeChoice.TGZ,
            base_image="custom/base",
            title=None,
        )

        validate_name_mock.return_value = request.name
        validate_base_image_mock.return_value = request.base_image
        validate_architecture_mock.return_value = request.architecture

        resource_builder: BootResourceBuilder = await request.to_builder(
            services=services_mock
        )

        assert resource_builder.name == request.name
        assert resource_builder.base_image == request.base_image
        assert resource_builder.architecture == request.architecture
        assert resource_builder.rtype == BootResourceType.UPLOADED

    async def test_validate_name_custom(self) -> None:
        services_mock = Mock(ServiceCollectionV3)

        services_mock.boot_source_cache = Mock(BootSourceCacheService)
        services_mock.boot_source_cache.get_unique_os_releases.return_value = []

        name = "custom/my_custom_image"

        request = BootResourceCreateRequest(
            name=name,
            sha256="test-sha256",
            architecture="amd64/generic",
            file_type=BootResourceFileTypeChoice.TGZ,
            title=None,
            base_image=None,
        )

        validated_name = await request._validate_name(name, services_mock)

        assert validated_name == "custom/my_custom_image"

    @pytest.mark.parametrize(
        "os",
        [
            "ubuntu-core",
            "centos",
            "rhel",
            "ol",
            "custom",
            "windows",
            "suse",
            "esxi",
        ],
    )
    async def test_validate_name_supported(self, os: str) -> None:
        services_mock = Mock(ServiceCollectionV3)

        services_mock.boot_source_cache = Mock(BootSourceCacheService)
        services_mock.boot_source_cache.get_unique_os_releases.return_value = []

        name = f"{os}/my-release"

        request = BootResourceCreateRequest(
            name=name,
            sha256="test-sha256",
            architecture="amd64/generic",
            file_type=BootResourceFileTypeChoice.TGZ,
            title=None,
            base_image=None,
        )
        validated_name = await request._validate_name(name, services_mock)

        assert validated_name == name

    async def test_validate_name_fails_when_not_supported(self) -> None:
        services_mock = Mock(ServiceCollectionV3)

        services_mock.boot_source_cache = Mock(BootSourceCacheService)
        services_mock.boot_source_cache.get_unique_os_releases.return_value = []

        name = "unsupported/os"

        request = BootResourceCreateRequest(
            name=name,
            sha256="test-sha256",
            architecture="amd64/generic",
            file_type=BootResourceFileTypeChoice.TGZ,
            title=None,
            base_image=None,
        )
        with pytest.raises(ValidationException) as validation_exception:
            await request._validate_name(name, services_mock)

        assert validation_exception.value.details[0].field == "name"

    async def test_validate_name_fails_when_centos_name(self) -> None:
        services_mock = Mock(ServiceCollectionV3)

        services_mock.boot_source_cache = Mock(BootSourceCacheService)
        services_mock.boot_source_cache.get_unique_os_releases.return_value = []

        name = "centos7"

        request = BootResourceCreateRequest(
            name=name,
            sha256="test-sha256",
            architecture="amd64/generic",
            file_type=BootResourceFileTypeChoice.TGZ,
            title=None,
            base_image=None,
        )
        with pytest.raises(ValidationException) as validation_exception:
            await request._validate_name(name, services_mock)

        assert validation_exception.value.details[0].field == "name"

    async def test_validate_name_fails_when_reserved_name(self) -> None:
        services_mock = Mock(ServiceCollectionV3)

        services_mock.boot_source_cache = Mock(BootSourceCacheService)
        services_mock.boot_source_cache.get_unique_os_releases.return_value = [
            BootSourceCacheOSRelease(os="centos", release="8"),
        ]

        name = "centos/8"

        request = BootResourceCreateRequest(
            name=name,
            sha256="test-sha256",
            architecture="amd64/generic",
            file_type=BootResourceFileTypeChoice.TGZ,
            title=None,
            base_image=None,
        )
        with pytest.raises(ValidationException) as validation_exception:
            await request._validate_name(name, services_mock)

        assert validation_exception.value.details[0].field == "name"

    async def test_validate_name_fails_when_reserved_osystem(self) -> None:
        services_mock = Mock(ServiceCollectionV3)

        services_mock.boot_source_cache = Mock(BootSourceCacheService)
        services_mock.boot_source_cache.get_unique_os_releases.return_value = [
            BootSourceCacheOSRelease(os="ubuntu", release="noble"),
            BootSourceCacheOSRelease(os="ubuntu", release="focal"),
            BootSourceCacheOSRelease(os="ubuntu", release="jammy"),
            BootSourceCacheOSRelease(os="centos", release="8"),
        ]

        name = "ubuntu"

        request = BootResourceCreateRequest(
            name=name,
            sha256="test-sha256",
            architecture="amd64/generic",
            file_type=BootResourceFileTypeChoice.TGZ,
            title=None,
            base_image=None,
        )
        with pytest.raises(ValidationException) as validation_exception:
            await request._validate_name(name, services_mock)

        assert validation_exception.value.details[0].field == "name"

    async def test_validate_name_fails_if_os_is_ubuntu(self) -> None:
        services_mock = Mock(ServiceCollectionV3)
        services_mock.boot_source_cache = Mock(BootSourceCacheService)
        services_mock.boot_source_cache.get_unique_os_releases.return_value = [
            BootSourceCacheOSRelease(os="ubuntu", release="noble"),
            BootSourceCacheOSRelease(os="ubuntu", release="focal"),
            BootSourceCacheOSRelease(os="ubuntu", release="jammy"),
            BootSourceCacheOSRelease(os="centos", release="8"),
        ]

        name = "ubuntu/my-ubuntu-release"
        request = BootResourceCreateRequest(
            name=name,
            sha256="test-sha256",
            architecture="amd64/generic",
            file_type=BootResourceFileTypeChoice.TGZ,
            title=None,
            base_image=None,
        )
        with pytest.raises(ValidationException) as validation_exception:
            await request._validate_name(name, services_mock)

        assert validation_exception.value.details[0].field == "name"
        assert (
            validation_exception.value.details[0].message
            == "To upload an Ubuntu custom image you have to specify 'custom' as the OS"
        )

    async def test_validate_name_fails_when_reserved_release(self) -> None:
        services_mock = Mock(ServiceCollectionV3)

        services_mock.boot_source_cache = Mock(BootSourceCacheService)
        services_mock.boot_source_cache.get_unique_os_releases.return_value = [
            BootSourceCacheOSRelease(os="ubuntu", release="noble"),
            BootSourceCacheOSRelease(os="ubuntu", release="focal"),
            BootSourceCacheOSRelease(os="ubuntu", release="jammy"),
            BootSourceCacheOSRelease(os="centos", release="8"),
        ]

        name = "noble"

        request = BootResourceCreateRequest(
            name=name,
            sha256="test-sha256",
            architecture="amd64/generic",
            file_type=BootResourceFileTypeChoice.TGZ,
            title=None,
            base_image=None,
        )
        with pytest.raises(ValidationException) as validation_exception:
            await request._validate_name(name, services_mock)

        assert validation_exception.value.details[0].field == "name"

    async def test_validate_base_image_defaults_to_commissioning_release(
        self,
    ) -> None:
        services_mock = Mock(ServiceCollectionV3)

        test_base_image = None

        name = "custom/my_custom_image"
        architecture = "amd64/generic"

        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_one.return_value = None

        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.configurations.get_many.return_value = {
            "commissioning_osystem": "ubuntu",
            "commissioning_distro_series": "noble",
        }

        request = BootResourceCreateRequest(
            name=name,
            sha256="test-sha256",
            architecture=architecture,
            file_type=BootResourceFileTypeChoice.TGZ,
            title=None,
            base_image=test_base_image,
        )

        validated_base_image = await request._validate_base_image(
            test_base_image, name, architecture, services_mock
        )

        assert validated_base_image == "ubuntu/noble"

    async def test_validate_base_image_windows_does_not_require_base_image(
        self,
    ) -> None:
        services_mock = Mock(ServiceCollectionV3)

        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_one.return_value = []

        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.configurations.get_many.return_value = []

        test_base_image = None

        name = f"windows/{factory.make_name()}"
        architecture = "amd64/generic"

        request = BootResourceCreateRequest(
            name=name,
            sha256="test-sha256",
            architecture=architecture,
            file_type=BootResourceFileTypeChoice.TGZ,
            title=None,
            base_image=test_base_image,
        )

        validated_base_image = await request._validate_base_image(
            test_base_image, name, architecture, services_mock
        )

        assert validated_base_image == ""

    async def test_validate_base_image_esxi_does_not_require_base_image(
        self,
    ) -> None:
        services_mock = Mock(ServiceCollectionV3)

        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_one.return_value = []

        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.configurations.get_many.return_value = []

        test_base_image = None

        name = f"esxi/{factory.make_name()}"
        architecture = "amd64/generic"

        request = BootResourceCreateRequest(
            name=name,
            sha256="test-sha256",
            architecture=architecture,
            file_type=BootResourceFileTypeChoice.TGZ,
            title=None,
            base_image=test_base_image,
        )

        validated_base_image = await request._validate_base_image(
            test_base_image, name, architecture, services_mock
        )

        assert validated_base_image == ""

    async def test_validate_base_image_rhel_does_not_require_base_image(
        self,
    ) -> None:
        services_mock = Mock(ServiceCollectionV3)

        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_one.return_value = []

        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.configurations.get_many.return_value = []

        test_base_image = None

        name = f"rhel/{factory.make_name()}"
        architecture = "amd64/generic"

        request = BootResourceCreateRequest(
            name=name,
            sha256="test-sha256",
            architecture=architecture,
            file_type=BootResourceFileTypeChoice.TGZ,
            title=None,
            base_image=test_base_image,
        )

        validated_base_image = await request._validate_base_image(
            test_base_image, name, architecture, services_mock
        )

        assert validated_base_image == ""

    async def test_validate_base_image_custom_image_name_no_prefix(
        self,
    ) -> None:
        services_mock = Mock(ServiceCollectionV3)

        test_base_image = "ubuntu/noble"

        base_image = "ubuntu/noble"
        name = "my_custom_image"
        architecture = "amd64/generic"

        existing_resource = BootResource(
            id=1,
            name=name,
            architecture=architecture,
            rtype=BootResourceType.UPLOADED,
            rolling=False,
            extra={},
            base_image=base_image,
        )

        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_one.return_value = existing_resource

        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.configurations.get_many.return_value = []

        request = BootResourceCreateRequest(
            name=name,
            sha256="test-sha256",
            architecture=architecture,
            file_type=BootResourceFileTypeChoice.TGZ,
            title=None,
            base_image=test_base_image,
        )

        validated_base_image = await request._validate_base_image(
            test_base_image, name, architecture, services_mock
        )

        assert validated_base_image == base_image

    async def test_validate_base_image_fails_when_non_existent_custom_image_no_prefix(
        self,
    ) -> None:
        services_mock = Mock(ServiceCollectionV3)

        test_base_image = "invalid"

        name = "my_custom_image"
        architecture = "amd64/generic"

        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_one.return_value = None

        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.configurations.get_many.return_value = []

        request = BootResourceCreateRequest(
            name=name,
            sha256="test-sha256",
            architecture=architecture,
            file_type=BootResourceFileTypeChoice.TGZ,
            title=None,
            base_image=test_base_image,
        )

        with pytest.raises(ValidationException) as validation_exception:
            await request._validate_base_image(
                test_base_image, name, architecture, services_mock
            )

        assert validation_exception.value.details[0].field == "base_image"

    async def test_validate_base_image_fails_if_release_unsupported(
        self,
    ) -> None:
        services_mock = Mock(ServiceCollectionV3)

        test_base_image = "ubuntu/asdf"

        name = "custom/my_custom_image"
        architecture = "amd64/generic"

        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_one.return_value = None

        services_mock.configurations = Mock(ConfigurationsService)

        request = BootResourceCreateRequest(
            name=name,
            sha256="test-sha256",
            architecture=architecture,
            file_type=BootResourceFileTypeChoice.TGZ,
            title=None,
            base_image=test_base_image,
        )

        with pytest.raises(ValidationException) as validation_exception:
            await request._validate_base_image(
                test_base_image, name, architecture, services_mock
            )

        assert validation_exception.value.details[0].field == "base_image"
        assert (
            validation_exception.value.details[0].message
            == f"Unsupported base image {test_base_image}"
        )

        services_mock.configurations.get_many.assert_not_called()

    async def test_validate_architecture_usable(self) -> None:
        services_mock = Mock(ServiceCollectionV3)

        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_usable_architectures.return_value = [
            "amd64/generic",
        ]

        test_architecture = "amd64/generic"

        name = f"custom/{factory.make_name()}"

        request = BootResourceCreateRequest(
            name=name,
            sha256="test-sha256",
            architecture=test_architecture,
            file_type=BootResourceFileTypeChoice.TGZ,
            title=None,
            base_image=None,
        )

        validated_base_architecture = await request._validate_architecture(
            test_architecture, services_mock
        )

        assert validated_base_architecture == test_architecture

    async def test_validate_architecture_not_usable(self) -> None:
        services_mock = Mock(ServiceCollectionV3)

        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_usable_architectures.return_value = [
            "amd64/generic",
        ]

        test_architecture = "arm64/generic"

        name = f"custom/{factory.make_name()}"

        request = BootResourceCreateRequest(
            name=name,
            sha256="test-sha256",
            architecture=test_architecture,
            file_type=BootResourceFileTypeChoice.TGZ,
            title=None,
            base_image=None,
        )

        with pytest.raises(ValidationException) as validation_exception:
            await request._validate_architecture(
                test_architecture, services_mock
            )

        assert validation_exception.value.details[0].field == "architecture"

    async def test_validate_architecture_invalid_format(self) -> None:
        services_mock = Mock(ServiceCollectionV3)

        test_architecture = "asdfghjkl;./"

        name = f"custom/{factory.make_name()}"

        request = BootResourceCreateRequest(
            name=name,
            sha256="test-sha256",
            architecture=test_architecture,
            file_type=BootResourceFileTypeChoice.TGZ,
            title=None,
            base_image=None,
        )

        with pytest.raises(ValidationException) as validation_exception:
            await request._validate_architecture(
                test_architecture, services_mock
            )

        assert validation_exception.value.details[0].field == "architecture"

    async def test_validate_architecture_fails_if_no_usable_architectures(
        self,
    ) -> None:
        services_mock = Mock(ServiceCollectionV3)

        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_usable_architectures.return_value = []

        test_architecture = "amd64/generic"

        name = f"custom/{factory.make_name()}"

        request = BootResourceCreateRequest(
            name=name,
            sha256="test-sha256",
            architecture=test_architecture,
            file_type=BootResourceFileTypeChoice.TGZ,
            title=None,
            base_image=None,
        )

        with pytest.raises(ValidationException) as validation_exception:
            await request._validate_architecture(
                test_architecture, services_mock
            )

        assert validation_exception.value.details[0].field == "architecture"


class TestCustomImageFilterParams:
    @pytest.mark.parametrize(
        "ids,expected",
        [
            (None, None),
            ([1], BootResourceClauseFactory.with_ids([1])),
            ([1, 2, 3], BootResourceClauseFactory.with_ids([1, 2, 3])),
        ],
    )
    def test_to_clause(self, ids, expected):
        filters = CustomImageFilterParams(ids=ids)
        clause = filters.to_clause()
        assert clause == expected

    @pytest.mark.parametrize(
        "ids,expected",
        [(None, None), ([1], "id=1"), ([1, 2, 3], "id=1&id=2&id=3")],
    )
    def test_to_href_format(self, ids, expected):
        filters = CustomImageFilterParams(ids=ids)
        href = filters.to_href_format()
        assert href == expected
