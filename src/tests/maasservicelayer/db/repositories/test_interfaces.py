#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import copy
from math import ceil

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.interface import InterfaceType
from maascommon.enums.ipaddress import IpAddressType
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.interfaces import InterfaceRepository
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.interfaces import Interface
from maasservicelayer.models.staticipaddress import StaticIPAddress
from tests.fixtures.factories.bmc import create_test_bmc
from tests.fixtures.factories.interface import (
    create_test_interface,
    create_test_interface_entry,
)
from tests.fixtures.factories.machines import create_test_machine
from tests.fixtures.factories.node_config import create_test_node_config_entry
from tests.fixtures.factories.staticipaddress import (
    create_test_staticipaddress_entry,
)
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.fixtures.factories.user import create_test_user
from tests.fixtures.factories.vlan import create_test_vlan_entry
from tests.maasapiserver.fixtures.db import Fixture


def _assert_interfaces_match_without_links(
    interface1: Interface, interface2: Interface
) -> None:
    assert interface1.id == interface2.id
    interface1.links = interface2.links = []
    assert interface1 == interface2, (
        f"{interface1} does not match {interface2}!"
    )


def _assert_interface_in_list(
    interface: Interface, interfaces_response: ListResult[Interface]
) -> None:
    interface_response = next(
        filter(
            lambda interface_response: interface.id == interface_response.id,
            interfaces_response.items,
        )
    )
    assert interface.id == interface_response.id
    _assert_interfaces_match_without_links(
        copy.deepcopy(interface), copy.deepcopy(interface_response)
    )


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestInterfaceRepository:
    @pytest.mark.parametrize("page_size", range(1, 4))
    @pytest.mark.parametrize(
        "alloc_type",
        [
            IpAddressType.AUTO,
            IpAddressType.STICKY,
            IpAddressType.USER_RESERVED,
        ],
    )
    async def test_list_for_node(
        self,
        page_size: int,
        alloc_type: str,
        db_connection: AsyncConnection,
        fixture: Fixture,
    ) -> None:
        bmc = await create_test_bmc(fixture)
        user = await create_test_user(fixture)
        machine = (
            await create_test_machine(fixture, bmc=bmc, user=user)
        ).dict()
        config = await create_test_node_config_entry(fixture, node=machine)
        machine["current_config_id"] = config["id"]

        interface_count = 4
        interfaces_repository = InterfaceRepository(
            Context(connection=db_connection)
        )
        created_interfaces = [
            (
                await create_test_interface(
                    fixture,
                    name=str(i),
                    node=machine,
                    ip_count=4,
                    alloc_type=alloc_type,
                )
            )
            for i in range(0, interface_count)
        ][::-1]

        total_pages = ceil(interface_count / page_size)
        total_retrieved = 0
        for page in range(1, total_pages + 1):
            interfaces_result = await interfaces_repository.list_for_node(
                node_id=machine["id"], page=page, size=page_size
            )
            actual_page_size = len(interfaces_result.items)
            assert interfaces_result.total == interface_count
            total_retrieved += actual_page_size

            if page == total_pages:
                expected_length = page_size - (
                    (total_pages * page_size) % interface_count
                )
            else:
                expected_length = page_size
            assert expected_length == actual_page_size, (
                f"page {page} has length {actual_page_size}? expected {expected_length}"
            )

            for interface in created_interfaces[
                ((page - 1) * page_size) : (page * page_size)
            ]:
                _assert_interface_in_list(interface, interfaces_result)
        assert total_retrieved == interface_count

    async def test_lists_only_on_selected_node(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        bmc = await create_test_bmc(fixture)
        user = await create_test_user(fixture)
        machine1 = (
            await create_test_machine(fixture, bmc=bmc, user=user)
        ).dict()
        machine2 = (
            await create_test_machine(
                fixture,
                bmc=bmc,
                user=user,
            )
        ).dict()

        config1 = await create_test_node_config_entry(fixture, node=machine1)
        machine1["current_config_id"] = config1["id"]

        config2 = await create_test_node_config_entry(fixture, node=machine2)
        machine2["current_config_id"] = config2["id"]

        interface1_count = 4
        interfaces_repository = InterfaceRepository(
            Context(connection=db_connection)
        )
        created_interfaces1 = [
            (
                await create_test_interface(
                    fixture,
                    name=str(i),
                    node=machine1,
                    ip_count=4,
                    alloc_type=IpAddressType.DISCOVERED,
                )
            )
            for i in range(0, interface1_count)
        ][::-1]

        interface2_count = 3
        created_interfaces2 = [
            (
                await create_test_interface(
                    fixture,
                    name=str(i),
                    node=machine2,
                    ip_count=2,
                    alloc_type=IpAddressType.DISCOVERED,
                )
            )
            for i in range(0, interface2_count)
        ][::-1]

        interfaces1_result = await interfaces_repository.list_for_node(
            node_id=machine1["id"], page=1, size=20
        )

        interfaces2_result = await interfaces_repository.list_for_node(
            node_id=machine2["id"], page=1, size=20
        )

        assert len(interfaces1_result.items) == interface1_count
        assert interfaces1_result.total == interface1_count
        assert len(interfaces2_result.items) == interface2_count
        assert interfaces2_result.total == interface2_count
        for interface in created_interfaces1:
            _assert_interface_in_list(interface, interfaces1_result)

        for interface in created_interfaces2:
            _assert_interface_in_list(interface, interfaces2_result)

    async def test_list_links_empty_if_only_discovered_type(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        # Discovered links are not returned from the database when listing
        # all the links on an interface, so this should be empty

        bmc = await create_test_bmc(fixture)
        user = await create_test_user(fixture)
        machine = (
            await create_test_machine(fixture, bmc=bmc, user=user)
        ).dict()
        config = await create_test_node_config_entry(fixture, node=machine)
        machine["current_config_id"] = config["id"]

        interface_count = 4
        interfaces_repository = InterfaceRepository(
            Context(connection=db_connection)
        )
        created_interfaces = [
            (
                await create_test_interface(
                    fixture,
                    name=str(i),
                    node=machine,
                    ip_count=4,
                    alloc_type=IpAddressType.DISCOVERED,
                )
            )
            for i in range(0, interface_count)
        ][::-1]

        interfaces_result = await interfaces_repository.list_for_node(
            node_id=machine["id"], page=1, size=interface_count
        )

        for iface in interfaces_result.items:
            assert not iface.links

        for interface in created_interfaces:
            assert interface.links
            _assert_interface_in_list(interface, interfaces_result)

    async def test_list_interfaces_use_discovered_ip_for_dhcp_links(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        # A dhcp link gets it ip address from discovered links on the same subnet
        # if we have some, their ip address should match the first discovered

        def _assert_interface_in_list(
            interface: Interface, interfaces_response: ListResult[Interface]
        ) -> None:
            interface_response = next(
                filter(
                    lambda interface_response: interface.id
                    == interface_response.id,
                    interfaces_response.items,
                )
            )
            assert interface.id == interface_response.id

            created_links = sorted(interface.links, key=lambda link: link.id)
            response_links = sorted(
                interface_response.links, key=lambda link: link.id
            )

            # if correct, the first link should be the discovery, the remaining dhcp
            created_discovery = created_links.pop(0)
            for created_dhcp, response_link in zip(
                created_links,
                response_links,
            ):
                assert created_dhcp.ip_type == IpAddressType.DHCP
                assert created_discovery.ip_type == IpAddressType.DISCOVERED

                assert created_dhcp.ip_address is None
                assert created_discovery.ip_address is not None

                # response should be dhcp with the discovery ip
                assert response_link.ip_type == IpAddressType.DHCP
                assert response_link.ip_address == created_discovery.ip_address

            _assert_interfaces_match_without_links(
                interface, interface_response
            )

        bmc = await create_test_bmc(fixture)
        user = await create_test_user(fixture)
        machine = (
            await create_test_machine(fixture, bmc=bmc, user=user)
        ).dict()
        config = await create_test_node_config_entry(fixture, node=machine)
        machine["current_config_id"] = config["id"]

        ip_count = 4
        interface_count = 4
        interfaces_repository = InterfaceRepository(
            Context(connection=db_connection)
        )

        created_interfaces = []
        for i in range(0, interface_count):
            vlan = await create_test_vlan_entry(fixture)
            subnet = await create_test_subnet_entry(
                fixture, vlan_id=vlan["id"]
            )

            ips = []
            for _ in range(ip_count):
                ips.extend(
                    await create_test_staticipaddress_entry(
                        fixture=fixture,
                        subnet=subnet,
                        alloc_type=IpAddressType.DHCP,
                    )
                )
            this_interface = await create_test_interface_entry(
                fixture=fixture,
                name=str(i),
                node=machine,
                ips=ips[::-1],
                vlan=vlan,
            )
            created_interfaces.insert(0, this_interface)

        interfaces_result = await interfaces_repository.list_for_node(
            node_id=machine["id"], page=1, size=interface_count
        )

        for interface in created_interfaces:
            _assert_interface_in_list(interface, interfaces_result)

    async def test_get_interfaces_in_fabric_has_interfaces(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        bmc = await create_test_bmc(fixture)
        user = await create_test_user(fixture)
        machine = (
            await create_test_machine(fixture, bmc=bmc, user=user)
        ).dict()
        config = await create_test_node_config_entry(fixture, node=machine)
        machine["current_config_id"] = config["id"]

        fabric_id = 0

        vlan = await create_test_vlan_entry(
            fixture=fixture,
            fabric_id=fabric_id,
        )
        subnet = await create_test_subnet_entry(fixture, vlan_id=vlan["id"])
        static_ip = await create_test_staticipaddress_entry(
            fixture=fixture,
            subnet=subnet,
            alloc_type=IpAddressType.DHCP,
        )
        this_interface = await create_test_interface_entry(
            fixture=fixture,
            node=machine,
            ips=static_ip,
            vlan=vlan,
            name="test_interface",
        )
        interfaces = [this_interface]

        interfaces_repository = InterfaceRepository(
            context=Context(connection=db_connection)
        )

        retrieved_interfaces = (
            await interfaces_repository.get_interfaces_in_fabric(
                fabric_id=fabric_id
            )
        )

        _assert_interfaces_match_without_links(
            interfaces[0], retrieved_interfaces[0]
        )

    async def test_get_interfaces_in_fabric_no_interfaces(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        bmc = await create_test_bmc(fixture)
        user = await create_test_user(fixture)
        machine = (
            await create_test_machine(fixture, bmc=bmc, user=user)
        ).dict()
        config = await create_test_node_config_entry(fixture, node=machine)
        machine["current_config_id"] = config["id"]

        fabric_id = 0

        _ = await create_test_vlan_entry(
            fixture=fixture,
            fabric_id=fabric_id,
        )

        interfaces_repository = InterfaceRepository(
            context=Context(connection=db_connection)
        )

        retrieved_interfaces = (
            await interfaces_repository.get_interfaces_in_fabric(
                fabric_id=fabric_id
            )
        )

        assert len(retrieved_interfaces) == 0

    async def test_link_ip(
        self, db_connection: AsyncConnection, fixture: Fixture
    ):
        vlan = await create_test_vlan_entry(
            fixture=fixture,
            fabric_id=0,
        )
        subnet = await create_test_subnet_entry(fixture, vlan_id=vlan["id"])

        static_ip = StaticIPAddress(
            **(
                await create_test_staticipaddress_entry(
                    fixture=fixture,
                    subnet=subnet,
                    alloc_type=IpAddressType.DHCP,
                )
            )[0]
        )
        interface = await create_test_interface_entry(
            fixture=fixture,
            vlan=vlan,
            name="test_interface",
        )

        interfaces_repository = InterfaceRepository(
            context=Context(connection=db_connection)
        )

        await interfaces_repository.link_ip(interface, static_ip)

        link = (await fixture.get("maasserver_interface_ip_addresses"))[0]
        assert link["interface_id"] == interface.id
        assert link["staticipaddress_id"] == static_ip.id

    async def test_link_ip_ignores_existing(
        self, db_connection: AsyncConnection, fixture: Fixture
    ):
        vlan = await create_test_vlan_entry(
            fixture=fixture,
            fabric_id=0,
        )
        subnet = await create_test_subnet_entry(fixture, vlan_id=vlan["id"])

        static_ip = await create_test_staticipaddress_entry(
            fixture=fixture,
            subnet=subnet,
            alloc_type=IpAddressType.DHCP,
        )
        interface = await create_test_interface_entry(
            fixture=fixture,
            ips=static_ip,
            vlan=vlan,
            name="test_interface",
        )

        static_ip_obj = StaticIPAddress(**static_ip[0])

        interfaces_repository = InterfaceRepository(
            context=Context(connection=db_connection)
        )

        await interfaces_repository.link_ip(interface, static_ip_obj)

        link = (await fixture.get("maasserver_interface_ip_addresses"))[0]
        assert link["interface_id"] == interface.id
        assert link["staticipaddress_id"] == static_ip_obj.id

    async def test_create_unkwnown_interface(
        self, db_connection: AsyncConnection, fixture: Fixture
    ):
        vlan = await create_test_vlan_entry(
            fixture=fixture,
            fabric_id=0,
        )
        interfaces_repository = InterfaceRepository(
            context=Context(connection=db_connection)
        )
        unknown_interface = (
            await interfaces_repository.create_unknwown_interface(
                "00:00:00:00:00", vlan["id"]
            )
        )

        assert unknown_interface.type == InterfaceType.UNKNOWN
        assert unknown_interface.links == []
        assert unknown_interface.name == "eth0"
        assert unknown_interface.mac_address == "00:00:00:00:00"
        assert unknown_interface.enabled is True
        assert unknown_interface.link_connected is True
        assert unknown_interface.interface_speed == 0
        assert unknown_interface.link_speed == 0
        assert unknown_interface.sriov_max_vf == 0
