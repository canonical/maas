# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasapiserver.v3.api.public.models.responses.discoveries import (
    DiscoveryResponse,
)
from maasservicelayer.models.discoveries import Discovery
from maasservicelayer.models.fields import MacAddress
from maasservicelayer.utils.date import utcnow


class TestDiscoveryResponse:
    def test_from_model(self) -> None:
        discovery = Discovery(
            id=1,
            discovery_id="MTAuMTAuMC4yOSwwMDoxNjozZToyOTphNTphMQ==",
            neighbour_id=1,
            ip="10.10.0.29",
            mac_address=MacAddress("aa:bb:cc:dd:ee:ff"),
            first_seen=utcnow(),
            last_seen=utcnow(),
            vid=1,
            observer_hostname="foo",
            observer_system_id="aabbcc",
            observer_id=1,
            observer_interface_id=1,
            observer_interface_name="eth0",
            mdns_id=1,
            hostname="bar",
            fabric_id=1,
            fabric_name="fabric-0",
            vlan_id=5001,
            is_external_dhcp=False,
            subnet_id=1,
            subnet_cidr="10.10.0.0/24",
            subnet_prefixlen=24,
        )
        discovery_response = DiscoveryResponse.from_model(
            discovery, self_base_hyperlink="http://test"
        )
        assert discovery_response.id == discovery.id
        assert discovery_response.discovery_id == discovery.discovery_id
        assert discovery_response.neighbour_id == discovery.neighbour_id
        assert discovery_response.ip == discovery.ip
        assert discovery_response.mac_address == discovery.mac_address
        assert discovery_response.first_seen == discovery.first_seen
        assert discovery_response.last_seen == discovery.last_seen
        assert discovery_response.vid == discovery.vid
        assert (
            discovery_response.observer_hostname == discovery.observer_hostname
        )
        assert (
            discovery_response.observer_system_id
            == discovery.observer_system_id
        )
        assert discovery_response.observer_id == discovery.observer_id
        assert (
            discovery_response.observer_interface_id
            == discovery.observer_interface_id
        )
        assert (
            discovery_response.observer_interface_name
            == discovery.observer_interface_name
        )
        assert discovery_response.mdns_id == discovery.mdns_id
        assert discovery_response.hostname == discovery.hostname
        assert discovery_response.fabric_id == discovery.fabric_id
        assert discovery_response.fabric_name == discovery.fabric_name
        assert discovery_response.vlan_id == discovery.vlan_id
        assert (
            discovery_response.is_external_dhcp == discovery.is_external_dhcp
        )
        assert discovery_response.subnet_id == discovery.subnet_id
        assert discovery_response.subnet_cidr == discovery.subnet_cidr
        assert (
            discovery_response.hal_links.self.href
            == f"http://test/{discovery.id}"
        )
