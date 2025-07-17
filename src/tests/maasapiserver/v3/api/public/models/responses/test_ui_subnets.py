# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from ipaddress import IPv4Address, IPv4Network

from maasapiserver.v3.api.public.models.responses.ui_subnets import (
    UISubnetResponse,
)
from maasapiserver.v3.constants import V3_API_UI_PREFIX
from maascommon.enums.subnet import RdnsMode
from maasservicelayer.models.ui_subnets import UISubnet
from maasservicelayer.utils.date import utcnow


class TestUISubnetResponse:
    def test_from_model(self) -> None:
        ui_subnet = UISubnet(
            id=1,
            created=utcnow(),
            updated=utcnow(),
            name="10.0.0.1/24",
            cidr=IPv4Network("10.0.0.1"),
            description="",
            rdns_mode=RdnsMode.DEFAULT,
            gateway_ip=IPv4Address("10.0.0.1"),
            dns_servers=[],
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            disabled_boot_architectures=[],
            vlan_id=1,
            vlan_vid=0,
            fabric_id=1,
            fabric_name="fabric-1",
            space_id=1,
            space_name="space-1",
        )

        ui_subnet_response = UISubnetResponse.from_model(
            ui_subnet, self_base_hyperlink=f"{V3_API_UI_PREFIX}/subnets"
        )

        assert ui_subnet_response.kind == "UISubnet"
        assert ui_subnet_response.id == ui_subnet.id
        assert ui_subnet_response.name == ui_subnet.name
        assert ui_subnet_response.description == ui_subnet.description
        assert ui_subnet_response.cidr == ui_subnet.cidr
        assert ui_subnet_response.rdns_mode == ui_subnet.rdns_mode
        assert ui_subnet_response.gateway_ip == ui_subnet.gateway_ip
        assert ui_subnet_response.dns_servers == ui_subnet.dns_servers
        assert ui_subnet_response.allow_dns == ui_subnet.allow_dns
        assert ui_subnet_response.allow_proxy == ui_subnet.allow_proxy
        assert (
            ui_subnet_response.active_discovery == ui_subnet.active_discovery
        )
        assert ui_subnet_response.managed == ui_subnet.managed
        assert (
            ui_subnet_response.disabled_boot_architectures
            == ui_subnet.disabled_boot_architectures
        )

        assert ui_subnet_response.hal_embedded is not None
        assert "fabric" in ui_subnet_response.hal_embedded
        assert "vlan" in ui_subnet_response.hal_embedded
        assert "space" in ui_subnet_response.hal_embedded
