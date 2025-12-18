#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from maasapiserver.v3.api.public.models.responses.boot_resources import (
    BootloaderResponse,
    BootResourceResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.boot_resources import BootResourceType
from maasservicelayer.models.bootresources import BootResource
from maasservicelayer.utils.date import utcnow


class TestBootResourceResponse:
    def test_from_model(self) -> None:
        now = utcnow()
        boot_resource = BootResource(
            id=1,
            created=now,
            updated=now,
            name="ubuntu/noble",
            architecture="amd64/hwe-24.04",
            extra={"subarches": "generic,hwe-24.04,ga-24.04"},
            rtype=BootResourceType.SYNCED,
            rolling=False,
            base_image="",
            kflavor=None,
            bootloader_type=None,
            alias=None,
            last_deployed=None,
        )
        boot_resource_response = BootResourceResponse.from_model(
            boot_resource=boot_resource,
            self_base_hyperlink=f"{V3_API_PREFIX}/boot_sources/1/selections/1/resources",
        )

        assert boot_resource_response.id == boot_resource.id
        assert boot_resource_response.os == "ubuntu"
        assert boot_resource_response.release == "noble"
        assert boot_resource_response.architecture == "amd64"
        assert boot_resource_response.sub_architecture == "hwe-24.04"
        assert (
            boot_resource_response.hal_links.self.href  # pyright: ignore[reportOptionalMemberAccess]
            == f"{V3_API_PREFIX}/boot_sources/1/selections/1/resources/{boot_resource.id}"
        )


class TestBootloaderResponse:
    def test_from_model(self) -> None:
        now = utcnow()
        boot_resource = BootResource(
            id=1,
            created=now,
            updated=now,
            name="grub-efi/uefi",
            architecture="amd64/generic",
            extra={},
            rtype=BootResourceType.UPLOADED,
            rolling=False,
            base_image="",
            kflavor=None,
            bootloader_type="uefi",
            alias=None,
            last_deployed=None,
        )
        bootloader_response = BootloaderResponse.from_model(
            boot_resource=boot_resource,
            self_base_hyperlink=f"{V3_API_PREFIX}/bootloaders",
        )

        assert bootloader_response.id == boot_resource.id
        assert bootloader_response.name == "grub-efi"
        assert bootloader_response.architecture == "amd64"
        assert bootloader_response.bootloader_type == "uefi"
        assert (
            bootloader_response.hal_links.self.href  # pyright: ignore[reportOptionalMemberAccess]
            == f"{V3_API_PREFIX}/bootloaders/{boot_resource.id}"
        )
