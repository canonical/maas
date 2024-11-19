from netaddr import IPAddress
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.ipaddress import IpAddressFamily, IpAddressType
from maascommon.enums.node import NodeTypeEnum
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.staticipaddress import (
    StaticIPAddressClauseFactory,
    StaticIPAddressRepository,
    StaticIPAddressResourceBuilder,
)
from maasservicelayer.db.tables import StaticIPAddressTable
from maasservicelayer.utils.date import utcnow
from tests.fixtures.factories.interface import create_test_interface_entry
from tests.fixtures.factories.node import create_test_region_controller_entry
from tests.fixtures.factories.node_config import create_test_node_config_entry
from tests.fixtures.factories.staticipaddress import (
    create_test_staticipaddress_entry,
)
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.maasapiserver.fixtures.db import Fixture


class TestStaticIPAddressClauseFactory:
    def test_builder(self) -> None:
        clause = StaticIPAddressClauseFactory.with_node_type(
            type=NodeTypeEnum.RACK_CONTROLLER
        )
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_node.node_type = 2")


@pytest.mark.asyncio
class TestStaticIPAddressRepository:
    async def test_create(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        subnet = await create_test_subnet_entry(fixture, cidr="10.0.0.0/24")

        staticipaddress_repository = StaticIPAddressRepository(
            Context(connection=db_connection)
        )

        now = utcnow()

        resource = (
            StaticIPAddressResourceBuilder()
            .with_ip("10.0.0.1")
            .with_alloc_type(IpAddressType.DISCOVERED)
            .with_subnet_id(subnet["id"])
            .with_lease_time(30)
            .with_created(now)
            .with_updated(now)
            .build()
        )

        await staticipaddress_repository.create(resource)

        result_stmt = (
            select(StaticIPAddressTable)
            .select_from(StaticIPAddressTable)
            .filter(
                StaticIPAddressTable.c.ip == IPAddress("10.0.0.1"),
                StaticIPAddressTable.c.alloc_type
                == IpAddressType.DISCOVERED.value,
            )
        )

        result = (await db_connection.execute(result_stmt)).one()

        assert result is not None

    async def test_update(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        subnet = await create_test_subnet_entry(fixture, cidr="10.0.0.0/24")
        sip = (
            await create_test_staticipaddress_entry(
                fixture,
                subnet=subnet,
                alloc_type=IpAddressType.DISCOVERED.value,
            )
        )[0]

        assert sip["lease_time"] == 600  # default value

        resource = (
            StaticIPAddressResourceBuilder()
            .with_ip(sip["ip"])
            .with_subnet_id(subnet["id"])
            .with_lease_time(30)
            .build()
        )

        staticipaddress_repository = StaticIPAddressRepository(
            Context(connection=db_connection)
        )

        await staticipaddress_repository.update(sip["id"], resource)

        result_stmt = (
            select(StaticIPAddressTable)
            .select_from(StaticIPAddressTable)
            .where(StaticIPAddressTable.c.id == sip["id"])
        )

        result = (await db_connection.execute(result_stmt)).one()

        assert result._asdict()["lease_time"] == 30

    async def test_create_or_update(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        subnet = await create_test_subnet_entry(fixture, cidr="10.0.0.0/24")
        sip = (
            await create_test_staticipaddress_entry(
                fixture,
                subnet=subnet,
                alloc_type=IpAddressType.DISCOVERED.value,
            )
        )[0]

        assert sip["lease_time"] == 600  # default value

        resource = (
            StaticIPAddressResourceBuilder()
            .with_ip(sip["ip"])
            .with_subnet_id(subnet["id"])
            .with_alloc_type(IpAddressType(sip["alloc_type"]))
            .with_lease_time(30)
            .with_created(utcnow())
            .with_updated(utcnow())
            .build()
        )

        staticipaddress_repository = StaticIPAddressRepository(
            Context(connection=db_connection)
        )

        await staticipaddress_repository.create_or_update(resource)

        result_stmt = (
            select(StaticIPAddressTable)
            .select_from(StaticIPAddressTable)
            .where(StaticIPAddressTable.c.id == sip["id"])
        )

        result = (await db_connection.execute(result_stmt)).one()

        assert result._asdict()["lease_time"] == 30

    async def test_get_discovered_ips_in_family_for_interfaces(
        self, db_connection: AsyncConnection, fixture: Fixture
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
                    alloc_type=IpAddressType.DISCOVERED.value,
                )
            )[0]
            for _ in range(3)
        ]
        v6_addrs = [
            (
                await create_test_staticipaddress_entry(
                    fixture,
                    subnet=v6_subnet,
                    alloc_type=IpAddressType.DISCOVERED.value,
                )
            )[0]
            for _ in range(3)
        ]
        interfaces = [
            await create_test_interface_entry(fixture, ips=v4_addrs + v6_addrs)
            for _ in range(3)
        ]

        staticipaddress_repository = StaticIPAddressRepository(
            Context(connection=db_connection)
        )
        result = await staticipaddress_repository.get_discovered_ips_in_family_for_interfaces(
            interfaces, family=IpAddressFamily.IPV4.value
        )

        assert {addr.id for addr in result} == {
            addr["id"] for addr in v4_addrs
        }

    async def test_get_for_nodes_not_found(
        self, db_connection: AsyncConnection, fixture: Fixture
    ):
        subnet = await create_test_subnet_entry(fixture)
        region_controller = await create_test_region_controller_entry(fixture)
        [ip] = await create_test_staticipaddress_entry(fixture, subnet=subnet)
        await create_test_interface_entry(
            fixture, node=region_controller, ips=[ip]
        )
        staticipaddress_repository = StaticIPAddressRepository(
            Context(connection=db_connection)
        )

        result = await staticipaddress_repository.get_for_nodes(
            query=QuerySpec(
                where=StaticIPAddressClauseFactory().with_node_type(
                    NodeTypeEnum.RACK_CONTROLLER
                )
            )
        )
        assert len(result) == 0

    async def test_get_for_nodes_found(
        self, db_connection: AsyncConnection, fixture: Fixture
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

        staticipaddress_repository = StaticIPAddressRepository(
            Context(connection=db_connection)
        )

        result = await staticipaddress_repository.get_for_nodes(
            query=QuerySpec(
                where=StaticIPAddressClauseFactory().with_node_type(
                    NodeTypeEnum.REGION_CONTROLLER
                )
            )
        )
        assert len(result) == 2
        assert any(ip1["ip"] == ip.ip for ip in result)
        assert any(ip2["ip"] == ip.ip for ip in result)
