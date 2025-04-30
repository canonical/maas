# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Self

from pydantic import IPvAnyAddress

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maasservicelayer.models.staticroutes import StaticRoute


class StaticRouteResponse(HalResponse[BaseHal]):
    kind = "StaticRoute"
    id: int
    destination_id: int
    gateway_ip: IPvAnyAddress
    metric: int

    @classmethod
    def from_model(
        cls, static_route: StaticRoute, self_base_hyperlink: str
    ) -> Self:
        return cls(
            id=static_route.id,
            destination_id=static_route.destination_id,
            gateway_ip=static_route.gateway_ip,
            metric=static_route.metric,
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{static_route.id}"
                )
            ),
        )


class StaticRoutesListResponse(PaginatedResponse[StaticRouteResponse]):
    kind = "StaticRoutesList"
