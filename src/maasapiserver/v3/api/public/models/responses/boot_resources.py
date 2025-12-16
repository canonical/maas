#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from datetime import datetime
from typing import Optional, Self

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maascommon.enums.boot_resources import BOOT_RESOURCE_TYPE_DICT
from maasservicelayer.models.bootresources import BootResource


class BootResourceResponse(HalResponse[BaseHal]):
    kind = "BootResource"

    id: int
    name: str
    architecture: str
    type: str
    extra: dict
    last_deployed: Optional[datetime]

    @classmethod
    def from_model(
        cls, boot_resource: BootResource, self_base_hyperlink: str
    ) -> Self:
        return cls(
            id=boot_resource.id,
            name=boot_resource.name,
            architecture=boot_resource.architecture,
            type=BOOT_RESOURCE_TYPE_DICT[boot_resource.rtype],
            extra=boot_resource.extra,
            last_deployed=boot_resource.last_deployed,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{boot_resource.id}"
                )
            ),
        )


class BootResourceListResponse(PaginatedResponse[BootResourceResponse]):
    kind = "BootResourceList"
