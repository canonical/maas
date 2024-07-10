# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone
from ipaddress import IPv4Address, IPv4Network

from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.models.subnets import Subnet
from maasserver.enum import RDNS_MODE


class TestSubnetModel:
    def test_to_response(self) -> None:
        now = datetime.now(timezone.utc)
        subnet = Subnet(
            id=1,
            name="my subnet",
            description="subnet description",
            cidr=IPv4Network("10.0.0.0/24"),
            rdns_mode=RDNS_MODE.DEFAULT,
            gateway_ip=IPv4Address("10.0.0.1"),
            dns_servers=[],
            allow_dns=True,
            allow_proxy=True,
            active_discovery=False,
            managed=True,
            disabled_boot_architectures=[],
            created=now,
            updated=now,
        )
        response = subnet.to_response(f"{V3_API_PREFIX}/subnets")
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
