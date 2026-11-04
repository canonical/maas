# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from collections.abc import Sequence
from datetime import datetime, timezone
from ipaddress import IPv4Address

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.ipaddress import IpAddressFamily, IpAddressType
from maascommon.enums.node import NodeTypeEnum
from maasservicelayer.builders.staticipaddress import StaticIPAddressBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.staticipaddress import (
    StaticIPAddressRepository,
)
from maasservicelayer.filters.query import QuerySpec
from maasservicelayer.filters.staticipaddress import StaticIPAddressFilters
from maasservicelayer.models.fields import MacAddress
from maasservicelayer.models.staticipaddress import StaticIPAddress
from tests.fixtures.factories.interface import create_test_interface_entry
from tests.fixtures.factories.node import create_test_region_controller_entry
from tests.fixtures.factories.node_config import create_test_node_config_entry
from tests.fixtures.factories.staticipaddress import (
    create_test_staticipaddress_entry,
)
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


@pytest.mark.asyncio
class TestStaticIPAddressRepository(RepositoryCommonTests[StaticIPAddress]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> StaticIPAddressRepository:
        return StaticIPAddressRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> Sequence[StaticIPAddress]:
        subnet = await create_test_subnet_entry(fixture, cidr="10.0.0.0/24")
        sip_sequence = [
            StaticIPAddress(
                **(
                    await create_test_staticipaddress_entry(
                        fixture,
                        subnet=subnet,
                        alloc_type=IpAddressType.DISCOVERED,
                    )
                )[0]
            )
            for _ in range(num_objects)
        ]
        return sip_sequence

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> StaticIPAddress:
        subnet = await create_test_subnet_entry(fixture, cidr="10.0.0.0/24")
        sip = (
            await create_test_staticipaddress_entry(
                fixture,
                subnet=subnet,
                alloc_type=IpAddressType.DISCOVERED,
            )
        )[0]
        assert sip["lease_time"] == 600  # default value
        return StaticIPAddress(**sip)

    @pytest.fixture
    async def instance_builder_model(self) -> type[StaticIPAddressBuilder]:
        return StaticIPAddressBuilder

    @pytest.fixture
    async def instance_builder(
        self, fixture: Fixture
    ) -> StaticIPAddressBuilder:
        subnet = await create_test_subnet_entry(fixture, cidr="10.0.0.0/24")
        return StaticIPAddressBuilder(
            ip=IPv4Address("10.0.0.1"),
            alloc_type=IpAddressType.DISCOVERED,
            subnet_id=subnet["id"],
            lease_time=30,
        )

    async def test_create_or_update(
        self, repository_instance: StaticIPAddressRepository, fixture: Fixture
    ) -> None:
        subnet = await create_test_subnet_entry(fixture, cidr="10.0.0.0/24")
        sip = (
            await create_test_staticipaddress_entry(
                fixture,
                subnet=subnet,
                alloc_type=IpAddressType.DISCOVERED,
            )
        )[0]

        assert sip["lease_time"] == 600  # default value

        builder = StaticIPAddressBuilder(
            ip=sip["ip"],
            subnet_id=subnet["id"],
            alloc_type=IpAddressType(sip["alloc_type"]),
            lease_time=30,
        )

        await repository_instance.create_or_update(builder)

        result = await repository_instance.get_by_id(sip["id"])
        assert result is not None
        assert result.lease_time == 30

    async def test_get_discovered_ips_in_family_for_interfaces(
        self, repository_instance: StaticIPAddressRepository, fixture: Fixture
    ) -> None:
        v4_subnet = await create_test_subnet_entry(fixture, cidr="10.0.0.0/24")
        v6_subnet = await create_test_subnet_entry(
            fixture, cidr="fd42:be3f:b08a:3d6c::/64"
        )
        v4_discovered_addrs = [
            (
                await create_test_staticipaddress_entry(
                    fixture,
                    subnet=v4_subnet,
                    alloc_type=IpAddressType.DISCOVERED,
                )
            )[0]
            for _ in range(3)
        ]
        v4_other_addrs = [
            (
                await create_test_staticipaddress_entry(
                    fixture,
                    subnet=v4_subnet,
                    alloc_type=IpAddressType.AUTO,
                )
            )[0]
            for _ in range(3)
        ]
        v6_addrs = [
            (
                await create_test_staticipaddress_entry(
                    fixture,
                    subnet=v6_subnet,
                    alloc_type=IpAddressType.DISCOVERED,
                )
            )[0]
            for _ in range(3)
        ]
        interfaces = [
            await create_test_interface_entry(
                fixture, ips=v4_discovered_addrs + v4_other_addrs + v6_addrs
            )
            for _ in range(3)
        ]

        result = await repository_instance.get_discovered_ips_in_family_for_interfaces(
            interfaces, family=IpAddressFamily.IPV4
        )

        assert {addr.id for addr in result} == {
            addr["id"] for addr in v4_discovered_addrs
        }

    async def test_get_discovered_ips_no_duplicates_for_shared_mac(
        self, repository_instance: StaticIPAddressRepository, fixture: Fixture
    ) -> None:
        subnet = await create_test_subnet_entry(fixture, cidr="10.0.0.0/24")
        discovered_ip = (
            await create_test_staticipaddress_entry(
                fixture,
                subnet=subnet,
                alloc_type=IpAddressType.DISCOVERED,
            )
        )[0]

        interfaces = []
        mac = "aa:bb:cc:dd:ee:ff"
        interfaces.append(
            await create_test_interface_entry(
                fixture, ips=[discovered_ip], mac_address=mac
            )
        )
        interfaces.append(
            await create_test_interface_entry(
                fixture, ips=[discovered_ip], mac_address=mac, type="bridge"
            )
        )

        result = await repository_instance.get_discovered_ips_in_family_for_interfaces(
            interfaces, family=IpAddressFamily.IPV4
        )

        assert len(result) == 1
        assert result[0].id == discovered_ip["id"]

    async def test_get_for_nodes_not_found(
        self, repository_instance: StaticIPAddressRepository, fixture: Fixture
    ):
        subnet = await create_test_subnet_entry(fixture)
        region_controller = await create_test_region_controller_entry(fixture)
        [ip] = await create_test_staticipaddress_entry(fixture, subnet=subnet)
        await create_test_interface_entry(
            fixture, node=region_controller, ips=[ip]
        )

        result = await repository_instance.get_for_nodes(
            query=QuerySpec(
                where=StaticIPAddressFilters().with_node_type(
                    NodeTypeEnum.RACK_CONTROLLER
                )
            )
        )
        assert len(result) == 0

    async def test_get_for_nodes_found(
        self, repository_instance: StaticIPAddressRepository, fixture: Fixture
    ):
        subnet1 = await create_test_subnet_entry(fixture)
        subnet2 = await create_test_subnet_entry(fixture)
        region_controller = await create_test_region_controller_entry(fixture)
        current_node_config = await create_test_node_config_entry(
            fixture, node=region_controller
        )
        region_controller["current_config_id"] = current_node_config["id"]
        [ip1] = await create_test_staticipaddress_entry(
            fixture, subnet=subnet1
        )
        [ip2] = await create_test_staticipaddress_entry(
            fixture, subnet=subnet2
        )
        await create_test_interface_entry(
            fixture, node=region_controller, ips=[ip1]
        )
        await create_test_interface_entry(
            fixture, node=region_controller, ips=[ip2]
        )

        result = await repository_instance.get_for_nodes(
            query=QuerySpec(
                where=StaticIPAddressFilters().with_node_type(
                    NodeTypeEnum.REGION_CONTROLLER
                )
            )
        )
        assert len(result) == 2
        assert any(ip1["ip"] == ip.ip for ip in result)
        assert any(ip2["ip"] == ip.ip for ip in result)

    async def test_get_mac_addresses(
        self, repository_instance: StaticIPAddressRepository, fixture: Fixture
    ):
        v4_subnet = await create_test_subnet_entry(fixture, cidr="10.0.0.0/24")
        ip = (
            await create_test_staticipaddress_entry(
                fixture,
                subnet=v4_subnet,
                alloc_type=IpAddressType.DISCOVERED,
            )
        )[0]
        ipv4 = IPv4Address(ip["ip"])
        interfaces = [
            await create_test_interface_entry(fixture, ips=[ip])
            for _ in range(3)
        ]
        result = await repository_instance.get_mac_addresses(
            query=QuerySpec(where=StaticIPAddressFilters.with_ip(ipv4))
        )
        expected_mac_addresses = sorted(
            [MacAddress(i.mac_address) for i in interfaces]
        )
        assert sorted(result) == expected_mac_addresses

    async def test_get_with_interface_ids(
        self, repository_instance: StaticIPAddressRepository, fixture: Fixture
    ):
        subnet = await create_test_subnet_entry(fixture, cidr="10.0.0.0/24")
        ip = (
            await create_test_staticipaddress_entry(
                fixture,
                subnet=subnet,
                alloc_type=IpAddressType.DISCOVERED,
            )
        )[0]
        interface = await create_test_interface_entry(fixture, ips=[ip])

        ip2 = (
            await create_test_staticipaddress_entry(
                fixture,
                subnet=subnet,
                alloc_type=IpAddressType.DISCOVERED,
            )
        )[0]
        interface2 = await create_test_interface_entry(fixture, ips=[ip2])

        results = await repository_instance.get_many(
            query=QuerySpec(
                where=StaticIPAddressFilters.with_interface_ids(
                    interface_ids=[interface.id, interface2.id]
                )
            )
        )

        ips = [ip.ip for ip in results]
        assert len(results) == 2
        assert ip["ip"] in ips
        assert ip2["ip"] in ips

    async def test_unlink_from_interfaces(
        self, repository_instance: StaticIPAddressRepository, fixture: Fixture
    ):
        subnet = await create_test_subnet_entry(fixture, cidr="10.0.0.0/24")
        ip = (
            await create_test_staticipaddress_entry(
                fixture,
                subnet=subnet,
                alloc_type=IpAddressType.DISCOVERED,
            )
        )[0]
        await create_test_interface_entry(fixture, ips=[ip])

        links = await fixture.get("maasserver_interface_ip_addresses")
        assert len(links) == 1

        await repository_instance.unlink_from_interfaces(ip["id"])

        links = await fixture.get("maasserver_interface_ip_addresses")
        assert len(links) == 0

    async def test_get_ips_for_interfaces_without_other_links(
        self, repository_instance: StaticIPAddressRepository, fixture: Fixture
    ):
        """Test getting IPs that would be orphaned if interfaces were deleted."""
        subnet = await create_test_subnet_entry(fixture, cidr="10.0.0.0/24")
        ip1 = (
            await create_test_staticipaddress_entry(
                fixture,
                subnet=subnet,
                alloc_type=IpAddressType.DISCOVERED,
            )
        )[0]
        ip2 = (
            await create_test_staticipaddress_entry(
                fixture,
                subnet=subnet,
                alloc_type=IpAddressType.DISCOVERED,
            )
        )[0]
        ip3 = (
            await create_test_staticipaddress_entry(
                fixture,
                subnet=subnet,
                alloc_type=IpAddressType.DISCOVERED,
            )
        )[0]
        # interface1 has ip1 only
        interface1 = await create_test_interface_entry(fixture, ips=[ip1])
        # interface2 has ip2 and ip3
        interface2 = await create_test_interface_entry(fixture, ips=[ip2, ip3])
        # interface3 also has ip3 (shared IP)
        await create_test_interface_entry(fixture, ips=[ip3])  # interface3

        # If we delete interface1 and interface2, ip1 and ip2 would be orphaned, but not ip3
        result = await repository_instance.get_ips_for_interfaces_without_other_links(
            [interface1.id, interface2.id]
        )

        result_ids = {r.id for r in result}
        assert result_ids == {ip1["id"], ip2["id"]}

    async def test_get_ips_for_interfaces_without_other_links_empty(
        self, repository_instance: StaticIPAddressRepository, fixture: Fixture
    ):
        """Test with empty interface list."""
        result = await repository_instance.get_ips_for_interfaces_without_other_links(
            []
        )

        assert result == []

    async def test_get_ips_for_interfaces_without_other_links_no_ips(
        self, repository_instance: StaticIPAddressRepository, fixture: Fixture
    ):
        """Test with interfaces that have no IPs."""
        interface = await create_test_interface_entry(fixture, ips=[])

        result = await repository_instance.get_ips_for_interfaces_without_other_links(
            [interface.id]
        )

        assert result == []

    @pytest.mark.parametrize("select_null", [True, False])
    async def test_null_ip_selection(
        self, repository_instance, fixture, select_null
    ):
        [null_ip] = await create_test_staticipaddress_entry(fixture, ip=None)
        [assigned_ip] = await create_test_staticipaddress_entry(
            fixture, ip="10.0.0.1"
        )
        filter = (
            StaticIPAddressFilters.with_ip(None)
            if select_null
            else StaticIPAddressFilters.with_ip_not_null()
        )
        result = await repository_instance.get_many(QuerySpec(where=filter))
        expected = null_ip if select_null else assigned_ip
        assert [ip.id for ip in result] == [expected["id"]]

    @pytest.mark.parametrize("enabled", [True, False])
    async def test_interface_enabled_filter(
        self, repository_instance, fixture, enabled
    ):
        [enabled_ip] = await create_test_staticipaddress_entry(
            fixture, ip="10.0.0.1"
        )
        [disabled_ip] = await create_test_staticipaddress_entry(
            fixture, ip="10.0.0.2"
        )
        await create_test_staticipaddress_entry(fixture, ip="10.0.0.3")
        await create_test_interface_entry(
            fixture, ips=[enabled_ip], enabled=True
        )
        await create_test_interface_entry(
            fixture, ips=[disabled_ip], enabled=False
        )
        result = await repository_instance.get_many(
            QuerySpec(
                where=StaticIPAddressFilters.and_filters(
                    [
                        StaticIPAddressFilters.with_linked_to_interface(),
                        StaticIPAddressFilters.with_interface_enabled(enabled),
                    ]
                )
            )
        )
        expected = enabled_ip if enabled else disabled_ip
        assert [ip.id for ip in result] == [expected["id"]]

    async def test_node_system_id_filter_on_base_query(
        self, repository_instance, fixture
    ):
        node = await create_test_region_controller_entry(fixture)
        config = await create_test_node_config_entry(fixture, node=node)
        node["current_config_id"] = config["id"]
        [linked_ip] = await create_test_staticipaddress_entry(
            fixture, ip="10.0.0.1"
        )
        await create_test_interface_entry(fixture, node=node, ips=[linked_ip])
        await create_test_staticipaddress_entry(fixture, ip="10.0.0.2")
        result = await repository_instance.get_many(
            QuerySpec(
                where=StaticIPAddressFilters.with_node_system_id(
                    node["system_id"]
                )
            )
        )
        assert [ip.id for ip in result] == [linked_ip["id"]]

    @pytest.mark.parametrize(
        "filter_kind, expected_indexes",
        [("in", {0, 1}), ("not_in", {2}), ("no_expiration", {0, 2})],
    )
    async def test_allocation_and_expiration_filters(
        self, repository_instance, fixture, filter_kind, expected_indexes
    ):
        ips = []
        for index, alloc_type in enumerate(
            [
                IpAddressType.AUTO,
                IpAddressType.STICKY,
                IpAddressType.DISCOVERED,
            ]
        ):
            [ip] = await create_test_staticipaddress_entry(
                fixture,
                ip=f"10.0.0.{index + 1}",
                alloc_type=alloc_type,
                temp_expires_on=datetime.now(timezone.utc)
                if index == 1
                else None,
            )
            ips.append(ip)
        filters = {
            "in": StaticIPAddressFilters.with_alloc_type_in(
                [IpAddressType.AUTO, IpAddressType.STICKY]
            ),
            "not_in": StaticIPAddressFilters.with_alloc_type_not_in(
                [IpAddressType.AUTO, IpAddressType.STICKY]
            ),
            "no_expiration": StaticIPAddressFilters.with_temp_expires_on_is_null(),
        }
        result = await repository_instance.get_many(
            QuerySpec(where=filters[filter_kind])
        )
        assert {ip.id for ip in result} == {
            ips[index]["id"] for index in expected_indexes
        }
