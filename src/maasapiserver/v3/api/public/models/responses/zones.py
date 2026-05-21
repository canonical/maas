# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Self

from pydantic import Field

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maasservicelayer.models.zones import Zone, ZoneWithStatistics


class ZoneResponse(HalResponse[BaseHal]):
    kind: str = Field(default="Zone")
    id: int
    name: str
    description: str

    @classmethod
    def from_model(cls, zone: Zone, self_base_hyperlink: str) -> Self:
        return cls(
            id=zone.id,
            name=zone.name,
            description=zone.description,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{zone.id}"
                )
            ),
        )


class ZonesListResponse(PaginatedResponse[ZoneResponse]):
    kind: str = Field(default="ZonesList")


class ZoneWithStatisticsResponse(HalResponse[BaseHal]):
    kind: str = Field(default="ZoneWithStatistics")
    id: int
    devices_count: int
    machines_count: int
    controllers_count: int

    @classmethod
    def from_model(
        cls, zone_with_statistics: ZoneWithStatistics, self_base_hyperlink: str
    ) -> Self:
        return cls(
            id=zone_with_statistics.id,
            machines_count=zone_with_statistics.machines_count,
            devices_count=zone_with_statistics.devices_count,
            controllers_count=zone_with_statistics.controllers_count,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{zone_with_statistics.id}"
                )
            ),
        )


class ZonesWithStatisticsListResponse(
    PaginatedResponse[ZoneWithStatisticsResponse]
):
    kind: str = Field(default="ZonesWithStatisticsList")
