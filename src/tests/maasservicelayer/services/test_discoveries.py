# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from ipaddress import IPv4Address
from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.discoveries import DiscoveriesRepository
from maasservicelayer.db.repositories.mdns import MDNSClauseFactory
from maasservicelayer.db.repositories.neighbours import NeighbourClauseFactory
from maasservicelayer.db.repositories.rdns import RDNSClauseFactory
from maasservicelayer.models.discoveries import Discovery
from maasservicelayer.models.fields import MacAddress
from maasservicelayer.services.discoveries import DiscoveriesService
from maasservicelayer.services.mdns import MDNSService
from maasservicelayer.services.neighbours import NeighboursService
from maasservicelayer.services.rdns import RDNSService
from tests.maasservicelayer.services.base import ReadOnlyServiceCommonTests


class TestDiscoveriesService(ReadOnlyServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> DiscoveriesService:
        return DiscoveriesService(
            context=Context(),
            discoveries_repository=Mock(DiscoveriesRepository),
            mdns_service=Mock(MDNSService),
            rdns_service=Mock(RDNSService),
            neighbours_service=Mock(NeighboursService),
        )

    @pytest.fixture
    def test_instance(self) -> Discovery:
        return Discovery(
            id=1,
            discovery_id="MTAuMTAuMC4yOSwwMDoxNjozZToyOTphNTphMQ==",
            neighbour_id=1,
            ip="10.10.0.29",
            mac_address=MacAddress("aa:bb:cc:dd:ee:ff"),
            first_seen=datetime.now(),
            last_seen=datetime.now(),
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


class TestDiscoveriesClear:
    @pytest.fixture(autouse=True)
    def mdns_service_mock(self):
        return Mock(MDNSService)

    @pytest.fixture(autouse=True)
    def rdns_service_mock(self):
        return Mock(RDNSService)

    @pytest.fixture(autouse=True)
    def neighbours_service_mock(self):
        return Mock(NeighboursService)

    @pytest.fixture(autouse=True)
    def discoveries_service(
        self,
        mdns_service_mock: Mock,
        rdns_service_mock: Mock,
        neighbours_service_mock: Mock,
    ):
        return DiscoveriesService(
            context=Context(),
            discoveries_repository=Mock(DiscoveriesRepository),
            mdns_service=mdns_service_mock,
            rdns_service=rdns_service_mock,
            neighbours_service=neighbours_service_mock,
        )

    async def test_clear_by_ip_and_mac(
        self,
        mdns_service_mock: Mock,
        rdns_service_mock: Mock,
        neighbours_service_mock: Mock,
        discoveries_service: DiscoveriesService,
    ):
        ip = IPv4Address("10.0.0.1")
        mac = MacAddress("aa:bb:cc:dd:ee:ff")
        await discoveries_service.clear_by_ip_and_mac(ip=ip, mac=mac)
        mdns_service_mock.delete_many.assert_called_once_with(
            query=QuerySpec(where=MDNSClauseFactory.with_ip(ip))
        )
        rdns_service_mock.delete_many.assert_called_once_with(
            query=QuerySpec(where=RDNSClauseFactory.with_ip(ip))
        )
        neighbours_service_mock.delete_many.assert_called_once_with(
            query=QuerySpec(
                where=NeighbourClauseFactory.and_clauses(
                    [
                        NeighbourClauseFactory.with_ip(ip),
                        NeighbourClauseFactory.with_mac(mac),
                    ]
                )
            )
        )

    async def test_clear_mdns_and_rdns(
        self,
        mdns_service_mock: Mock,
        rdns_service_mock: Mock,
        neighbours_service_mock: Mock,
        discoveries_service: DiscoveriesService,
    ):
        await discoveries_service.clear_mdns_and_rdns_records()
        mdns_service_mock.delete_many.assert_called_once_with(
            query=QuerySpec()
        )
        rdns_service_mock.delete_many.assert_called_once_with(
            query=QuerySpec()
        )
        neighbours_service_mock.delete_many.assert_not_called()

    async def test_clear_neighours(
        self,
        mdns_service_mock: Mock,
        rdns_service_mock: Mock,
        neighbours_service_mock: Mock,
        discoveries_service: DiscoveriesService,
    ):
        await discoveries_service.clear_neighbours()
        neighbours_service_mock.delete_many.assert_called_once_with(
            query=QuerySpec()
        )
        mdns_service_mock.delete_many.assert_not_called()
        rdns_service_mock.delete_many.assert_not_called()

    async def test_clear_all(
        self,
        mdns_service_mock: Mock,
        rdns_service_mock: Mock,
        neighbours_service_mock: Mock,
        discoveries_service: DiscoveriesService,
    ):
        await discoveries_service.clear_all()
        mdns_service_mock.delete_many.assert_called_once_with(
            query=QuerySpec()
        )
        rdns_service_mock.delete_many.assert_called_once_with(
            query=QuerySpec()
        )

        neighbours_service_mock.delete_many.assert_called_once_with(
            query=QuerySpec()
        )
