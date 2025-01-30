# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.operators import eq

from maascommon.enums.node import NodeTypeEnum
from maasservicelayer.builders.vlans import VlanBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.vlans import (
    VlansClauseFactory,
    VlansRepository,
)
from maasservicelayer.db.tables import VlanTable
from maasservicelayer.models.vlans import Vlan
from tests.fixtures.factories.fabric import create_test_fabric_entry
from tests.fixtures.factories.interface import create_test_interface_entry
from tests.fixtures.factories.node import create_test_rack_controller_entry
from tests.fixtures.factories.node_config import create_test_node_config_entry
from tests.fixtures.factories.staticipaddress import (
    create_test_staticipaddress_entry,
)
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.fixtures.factories.vlan import create_test_vlan_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestVlansClauseFactory:
    def test_builder(self) -> None:
        clause = VlansClauseFactory.with_system_id(system_id="abc")
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_node.system_id = 'abc'")

        clause = VlansClauseFactory.with_node_type(
            type=NodeTypeEnum.RACK_CONTROLLER
        )
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_node.node_type = 2")


class TestVlansRepository(RepositoryCommonTests[Vlan]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> VlansRepository:
        return VlansRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[Vlan]:
        fabric = await create_test_fabric_entry(fixture)
        created_vlans = [
            Vlan(
                **(await create_test_vlan_entry(fixture, fabric_id=fabric.id))
            )
            for _ in range(num_objects)
        ]
        return created_vlans

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> Vlan:
        fabric = await create_test_fabric_entry(fixture)
        return Vlan(
            **(await create_test_vlan_entry(fixture, fabric_id=fabric.id))
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[VlanBuilder]:
        return VlanBuilder

    @pytest.fixture
    async def instance_builder(self) -> VlanBuilder:
        return VlanBuilder(
            name="myvlan",
            description="mydesc",
            mtu=1500,
            vid=1,
            dhcp_on=True,
            fabric_id=1,
            space_id=1,
            primary_rack_id=1,
            secondary_rack_id=1,
        )

    async def test_get_node_vlans_no_system_id(
        self, repository_instance: VlansRepository
    ):
        result = await repository_instance.get_node_vlans(
            query=QuerySpec(
                where=VlansClauseFactory.with_system_id(system_id="abc")
            )
        )
        assert result == []

    async def test_get_fabric_default_vlan(
        self, fixture: Fixture, repository_instance: VlansRepository
    ):
        fabric = await create_test_fabric_entry(fixture)
        vlan1 = await create_test_vlan_entry(fixture, fabric_id=fabric.id)
        await create_test_vlan_entry(fixture, fabric_id=fabric.id)
        await create_test_vlan_entry(fixture, fabric_id=fabric.id)
        result = await repository_instance.get_fabric_default_vlan(fabric.id)
        assert result.id == vlan1["id"]

    async def test_get_node_vlans_with_valid_system_id(
        self, fixture: Fixture, repository_instance: VlansRepository
    ):
        subnet = await create_test_subnet_entry(fixture)
        rack_controller = await create_test_rack_controller_entry(fixture)
        [ip] = await create_test_staticipaddress_entry(fixture, subnet=subnet)
        await create_test_interface_entry(
            fixture, node=rack_controller, ips=[ip]
        )

        result = await repository_instance.get_node_vlans(
            query=QuerySpec(
                where=VlansClauseFactory.with_system_id(
                    rack_controller["system_id"]
                )
            )
        )

        [vlan] = await fixture.get_typed(
            VlanTable.name, Vlan, eq(VlanTable.c.id, subnet["vlan_id"])
        )
        assert len(result) == 1
        assert result[0] == vlan

    async def test_get_rack_controller_vlans_multiple_vlans(
        self, fixture: Fixture, repository_instance: VlansRepository
    ):
        vlan1 = await create_test_vlan_entry(fixture)
        vlan2 = await create_test_vlan_entry(fixture)
        subnet1 = await create_test_subnet_entry(fixture, vlan_id=vlan1["id"])
        subnet2 = await create_test_subnet_entry(fixture, vlan_id=vlan2["id"])
        rack_controller = await create_test_rack_controller_entry(fixture)
        current_node_config = await create_test_node_config_entry(
            fixture, node=rack_controller
        )
        rack_controller["current_config_id"] = current_node_config["id"]
        [ip1] = await create_test_staticipaddress_entry(
            fixture, subnet=subnet1
        )
        [ip2] = await create_test_staticipaddress_entry(
            fixture, subnet=subnet2
        )
        await create_test_interface_entry(
            fixture, node=rack_controller, ips=[ip1]
        )
        await create_test_interface_entry(
            fixture, node=rack_controller, ips=[ip2]
        )
        result = await repository_instance.get_node_vlans(
            query=QuerySpec(
                where=VlansClauseFactory.with_system_id(
                    rack_controller["system_id"]
                )
            )
        )
        assert len(result) == 2
        assert any(
            retrieved_vlan.id == vlan1["id"] for retrieved_vlan in result
        )
        assert any(
            retrieved_vlan.id == vlan2["id"] for retrieved_vlan in result
        )
