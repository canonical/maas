# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv4Network

from maasapiserver.v3.api.public.models.responses.subnets import SubnetResponse
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.subnet import RdnsMode
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.utils.date import utcnow


class TestSubnetResponse:
    def test_from_model(self) -> None:
        now = utcnow()
        subnet = Subnet(
            id=1,
            name="my subnet",
            description="subnet description",
            cidr=IPv4Network("10.0.0.0/24"),
            rdns_mode=RdnsMode.DEFAULT,
            gateway_ip=IPv4Address("10.0.0.1"),
            dns_servers=[],
            allow_dns=True,
            allow_proxy=True,
            active_discovery=False,
            managed=True,
            vlan_id=1,
            disabled_boot_architectures=[],
            created=now,
            updated=now,
        )
        response = SubnetResponse.from_model(
            subnet=subnet, self_base_hyperlink=f"{V3_API_PREFIX}/subnets"
        )
        assert subnet.id == response.id
        assert subnet.name == response.name
        assert subnet.description == response.description
        assert subnet.cidr == response.cidr
        assert subnet.rdns_mode == response.rdns_mode
        assert subnet.gateway_ip == response.gateway_ip
        assert subnet.dns_servers == response.dns_servers
        assert subnet.allow_dns == response.allow_dns
        assert subnet.allow_proxy == response.allow_proxy
        assert subnet.active_discovery == response.active_discovery
        assert subnet.managed == response.managed
        assert (
            subnet.disabled_boot_architectures
            == response.disabled_boot_architectures
        )
        assert (
            response.hal_links.self.href
            == f"{V3_API_PREFIX}/subnets/{subnet.id}"
        )
