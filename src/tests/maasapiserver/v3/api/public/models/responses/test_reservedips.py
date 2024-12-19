# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address

from maasapiserver.v3.api.public.models.responses.reservedips import (
    ReservedIPResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.models.fields import MacAddress
from maasservicelayer.models.reservedips import ReservedIP
from maasservicelayer.utils.date import utcnow


class TestReservedIPsResponse:
    def test_from_model(self) -> None:
        now = utcnow()
        reservedip = ReservedIP(
            id=1,
            ip=IPv4Address("10.0.0.3"),
            mac_address=MacAddress("11:11:11:11:11:11"),
            comment="comment",
            subnet_id=1,
            created=now,
            updated=now,
        )
        response = ReservedIPResponse.from_model(
            reservedip=reservedip,
            self_base_hyperlink=f"{V3_API_PREFIX}/fabrics/1/vlans/1/subnets/1/reservedips",
        )
        assert reservedip.id == response.id
        assert reservedip.ip == response.ip
        assert reservedip.mac_address == response.mac_address
        assert reservedip.comment == response.comment
        assert (
            response.hal_links.self.href
            == f"{V3_API_PREFIX}/fabrics/1/vlans/1/subnets/1/reservedips/{reservedip.id}"
        )
