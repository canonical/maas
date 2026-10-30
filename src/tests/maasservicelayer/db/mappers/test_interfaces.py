# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from copy import deepcopy
from ipaddress import IPv4Address
from types import MappingProxyType

import pytest

from maascommon.enums.interface import InterfaceType
from maascommon.enums.ipaddress import IpAddressType
from maasservicelayer.db.mappers.interfaces import (
    DiscoveredInterfaceIP,
    DiscoveredInterfaceIPDomainDataMapper,
    InterfaceDomainDataMapper,
)
from maasservicelayer.db.tables import InterfaceTable, StaticIPAddressTable
from maasservicelayer.models.interfaces import Interface, Link


class TestInterfaceDomainDataMapper:
    @pytest.fixture
    def mapper(self) -> InterfaceDomainDataMapper:
        return InterfaceDomainDataMapper(Interface, InterfaceTable)

    def test_raw_row_preserves_fields_and_link_defaults(
        self, mapper: InterfaceDomainDataMapper
    ) -> None:
        row = MappingProxyType(
            {
                "id": 1,
                "name": "mgmt0",
                "type": "physical",
                "switch_id": 42,
                "enabled": False,
                "link_connected": False,
            }
        )

        interface = mapper.to_domain(row)

        assert interface.type == InterfaceType.PHYSICAL
        assert interface.switch_id == 42
        assert interface.enabled is False
        assert interface.link_connected is False
        assert interface.links == []
        assert interface.interface_speed == 0
        assert interface.link_speed == 0
        assert interface.sriov_max_vf == 0
        assert "links" not in row

    @pytest.mark.parametrize(
        "links",
        [
            None,
            [],
            [
                {
                    "id": None,
                    "ip_type": None,
                    "ip_address": None,
                    "ip_subnet": None,
                }
            ],
        ],
    )
    def test_empty_aggregates_have_no_links(
        self, mapper: InterfaceDomainDataMapper, links
    ) -> None:
        row = {
            "id": 1,
            "name": "eth0",
            "type": "physical",
            "links": links,
        }
        original = deepcopy(row)

        interface = mapper.to_domain(MappingProxyType(row))

        assert interface.links == []
        assert row == original

    def test_links_are_deduplicated_sorted_and_independent_of_row(
        self, mapper: InterfaceDomainDataMapper
    ) -> None:
        row = {
            "id": 1,
            "name": "eth0",
            "type": "physical",
            "links": [
                {"id": 2, "ip_type": IpAddressType.DHCP, "ip_subnet": 10},
                {"id": 5, "ip_type": IpAddressType.STICKY},
                {
                    "id": None,
                    "ip_type": None,
                    "ip_address": None,
                    "ip_subnet": None,
                },
                {
                    "id": 2,
                    "ip_type": IpAddressType.DHCP,
                    "ip_subnet": 20,
                    "ip_address": "192.0.2.2",
                },
            ],
        }
        original = deepcopy(row)

        interface = mapper.to_domain(MappingProxyType(row))

        assert interface.links == [
            Link(id=5, ip_type=IpAddressType.STICKY),
            Link(
                id=2,
                ip_type=IpAddressType.DHCP,
                ip_subnet=20,
                ip_address=IPv4Address("192.0.2.2"),
            ),
        ]
        interface.links[1].ip_address = IPv4Address("192.0.2.3")
        assert row == original


class TestDiscoveredInterfaceIPDomainDataMapper:
    def test_hydrates_address_without_changing_row(self) -> None:
        mapper = DiscoveredInterfaceIPDomainDataMapper(
            DiscoveredInterfaceIP, StaticIPAddressTable
        )
        row = MappingProxyType({"ip_subnet": 10, "ip_address": "192.0.2.2"})

        discovered = mapper.to_domain(row)

        assert discovered.ip_subnet == 10
        assert discovered.ip_address == IPv4Address("192.0.2.2")
        assert row["ip_address"] == "192.0.2.2"
