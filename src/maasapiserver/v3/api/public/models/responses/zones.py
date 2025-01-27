# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Self

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maasservicelayer.models.zones import Zone


class ZoneResponse(HalResponse[BaseHal]):
    kind = "Zone"
    id: int
    name: str
    description: str

    @classmethod
    def from_model(cls, zone: Zone, self_base_hyperlink: str) -> Self:
        return cls(
            id=zone.id,
            name=zone.name,
            description=zone.description,
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{zone.id}"
                )
            ),
        )


class ZonesListResponse(PaginatedResponse[ZoneResponse]):
    kind = "ZonesList"
