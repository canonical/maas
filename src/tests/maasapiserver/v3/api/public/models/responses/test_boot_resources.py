#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from maasapiserver.v3.api.public.models.responses.boot_resources import (
    BootResourceResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.boot_resources import (
    BOOT_RESOURCE_TYPE_DICT,
    BootResourceType,
)
from maasservicelayer.models.bootresources import BootResource
from maasservicelayer.utils.date import utcnow


class TestBootResourceResponse:
    def test_from_model(self) -> None:
        now = utcnow()
        boot_resource = BootResource(
            id=1,
            created=now,
            updated=now,
            name="custom/image",
            architecture="amd64/generic",
            extra={"subarches": "generic,hwe-24.04,ga-24.04"},
            rtype=BootResourceType.UPLOADED,
            rolling=False,
            base_image="ubuntu/noble",
            kflavor=None,
            bootloader_type=None,
            alias=None,
            last_deployed=None,
        )
        boot_resource_response = BootResourceResponse.from_model(
            boot_resource=boot_resource,
            self_base_hyperlink=f"{V3_API_PREFIX}/boot_resources",
        )

        assert boot_resource.id == boot_resource_response.id
        assert boot_resource.name == boot_resource_response.name
        assert (
            boot_resource.architecture == boot_resource_response.architecture
        )
        assert boot_resource.extra == boot_resource_response.extra
        assert (
            BOOT_RESOURCE_TYPE_DICT[boot_resource.rtype]
            == boot_resource_response.type
        )
        assert (
            boot_resource.last_deployed == boot_resource_response.last_deployed
        )
        assert (
            boot_resource_response.hal_links.self.href  # pyright: ignore[reportOptionalMemberAccess]
            == f"{V3_API_PREFIX}/boot_resources/{boot_resource.id}"
        )
