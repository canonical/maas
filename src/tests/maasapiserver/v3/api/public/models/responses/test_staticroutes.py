# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address

from maasapiserver.v3.api.public.models.responses.staticroutes import (
    StaticRouteResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.models.staticroutes import StaticRoute
from maasservicelayer.utils.date import utcnow


class TestStaticRouteResponse:
    def test_from_model(self) -> None:
        now = utcnow()
        static_route = StaticRoute(
            id=0,
            created=now,
            updated=now,
            gateway_ip=IPv4Address("10.0.0.1"),
            metric=0,
            destination_id=1,
            source_id=0,
        )
        static_route_response = StaticRouteResponse.from_model(
            static_route=static_route,
            self_base_hyperlink=f"{V3_API_PREFIX}/staticroutes",
        )
        assert static_route.id == static_route_response.id
        assert static_route.metric == static_route_response.metric
        assert static_route.gateway_ip == static_route_response.gateway_ip
        assert (
            static_route.destination_id == static_route_response.destination_id
        )
        assert static_route_response.hal_links.self.href.endswith(
            f"staticroutes/{static_route.id}"
        )
