#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional, Self

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.models.fabrics import Fabric


class FabricResponse(HalResponse[BaseHal]):
    kind = "Fabric"
    id: int
    name: Optional[str]
    description: Optional[str]
    class_type: Optional[str]
    vlans: BaseHref

    @classmethod
    def from_model(cls, fabric: Fabric, self_base_hyperlink: str) -> Self:
        return cls(
            id=fabric.id,
            name=fabric.name,
            description=fabric.description,
            class_type=fabric.class_type,
            vlans=BaseHref(href=f"{V3_API_PREFIX}/fabrics/{fabric.id}/vlans"),
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{fabric.id}"
                )
            ),
        )


class FabricsListResponse(PaginatedResponse[FabricResponse]):
    kind = "FabricsList"
