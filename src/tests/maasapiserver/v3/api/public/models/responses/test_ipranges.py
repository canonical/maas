# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address

from maasapiserver.v3.api.public.models.responses.ipranges import (
    IPRangeResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.ipranges import IPRangeType
from maasservicelayer.models.ipranges import IPRange
from maasservicelayer.utils.date import utcnow


class TestIPrangeResponse:
    def test_from_model(self) -> None:
        now = utcnow()
        iprange = IPRange(
            id=1,
            created=now,
            updated=now,
            type=IPRangeType.RESERVED,
            start_ip=IPv4Address("10.10.0.1"),
            end_ip=IPv4Address("10.10.0.3"),
            comment="comment",
            subnet_id=1,
            user_id=0,
        )
        iprange_response = IPRangeResponse.from_model(
            iprange=iprange, self_base_hyperlink=f"{V3_API_PREFIX}/ipranges"
        )
        assert iprange.id == iprange_response.id
        assert iprange.type == iprange_response.type
        assert iprange.start_ip == iprange_response.start_ip
        assert iprange.end_ip == iprange_response.end_ip
        assert iprange.comment == iprange_response.comment
        assert iprange.user_id == iprange_response.owner_id
