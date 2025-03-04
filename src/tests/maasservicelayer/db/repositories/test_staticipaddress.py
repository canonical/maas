# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from collections.abc import Sequence
from ipaddress import IPv4Address

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.ipaddress import IpAddressFamily, IpAddressType
from maascommon.enums.node import NodeTypeEnum
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.staticipaddress import (
    StaticIPAddressClauseFactory,
    StaticIPAddressRepository,
)
from maasservicelayer.models.fields import MacAddress
from maasservicelayer.models.staticipaddress import (
    StaticIPAddress,
    StaticIPAddressBuilder,
)
from tests.fixtures.factories.interface import create_test_interface_entry
from tests.fixtures.factories.node import create_test_region_controller_entry
from tests.fixtures.factories.node_config import create_test_node_config_entry
from tests.fixtures.factories.staticipaddress import (
    create_test_staticipaddress_entry,
)
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestStaticIPAddressClauseFactory:
    def test_with_id(self) -> None:
        clause = StaticIPAddressClauseFactory.with_id(1)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_staticipaddress.id = 1")

    def test_with_node_type(self) -> None:
        clause = StaticIPAddressClauseFactory.with_node_type(
            type=NodeTypeEnum.RACK_CONTROLLER
        )
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_node.node_type = 2")

    def test_with_subnet_id(self) -> None:
        clause = StaticIPAddressClauseFactory.with_subnet_id(1)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_staticipaddress.subnet_id = 1")

    def test_with_ip(self) -> None:
        clause = StaticIPAddressClauseFactory.with_ip(IPv4Address("10.10.0.2"))
        # NOTE: compile with literal_binds can't render IPv4Address
        assert str(clause.condition.compile()) == (
            "maasserver_staticipaddress.ip = :ip_1"
        )

    def test_with_alloc_type(self) -> None:
        clause = StaticIPAddressClauseFactory.with_alloc_type(
            alloc_type=IpAddressType.DISCOVERED
        )
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_staticipaddress.alloc_type = 6")

    def test_with_interface_ids(self) -> None:
        clause = StaticIPAddressClauseFactory.with_interface_ids(
            interface_ids=[1]
        )
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_interface.id IN (1)")
        assert str(
            clause.joins[0].compile(compile_kwargs={"literal_binds": True})
        ) == (
            "maasserver_staticipaddress JOIN maasserver_interface_ip_addresses ON maasserver_staticipaddress.id = maasserver_interface_ip_addresses.staticipaddress_id"
        )
        assert str(
            clause.joins[1].compile(compile_kwargs={"literal_binds": True})
        ) == (
            "maasserver_interface_ip_addresses JOIN maasserver_interface ON maasserver_interface_ip_addresses.interface_id = maasserver_interface.id"
        )


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
        v4_addrs = [
            (
                await create_test_staticipaddress_entry(
                    fixture,
                    subnet=v4_subnet,
                    alloc_type=IpAddressType.DISCOVERED,
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
            await create_test_interface_entry(fixture, ips=v4_addrs + v6_addrs)
            for _ in range(3)
        ]

        result = await repository_instance.get_discovered_ips_in_family_for_interfaces(
            interfaces, family=IpAddressFamily.IPV4
        )

        assert {addr.id for addr in result} == {
            addr["id"] for addr in v4_addrs
        }

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
                where=StaticIPAddressClauseFactory().with_node_type(
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
                where=StaticIPAddressClauseFactory().with_node_type(
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
            query=QuerySpec(where=StaticIPAddressClauseFactory.with_ip(ipv4))
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
                where=StaticIPAddressClauseFactory.with_interface_ids(
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
