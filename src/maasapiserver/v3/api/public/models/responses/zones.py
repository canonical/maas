# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Self

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maasservicelayer.models.zones import Zone, ZoneWithSummary


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


class ZoneWithSummaryResponse(ZoneResponse):
    kind = "ZoneWithSummary"
    devices_count: int
    machines_count: int
    controllers_count: int

    @classmethod
    def from_model(
        cls, zone_with_summary: ZoneWithSummary, self_base_hyperlink: str
    ) -> Self:
        return cls(
            id=zone_with_summary.id,
            name=zone_with_summary.name,
            description=zone_with_summary.description,
            machines_count=zone_with_summary.machines_count,
            devices_count=zone_with_summary.devices_count,
            controllers_count=zone_with_summary.controllers_count,
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{zone_with_summary.id}"
                )
            ),
        )


class ZonesWithSummaryListResponse(PaginatedResponse[ZoneWithSummaryResponse]):
    kind = "ZonesWithSummaryList"
