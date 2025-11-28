# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.switches import SwitchBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.switches import (
    SwitchClauseFactory,
    SwitchesRepository,
)
from maasservicelayer.models.switches import Switch
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.fixtures.factories.switches import create_test_switch
from tests.fixtures.factories.vlan import create_test_vlan_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestSwitchClauseFactory:
    """Tests for SwitchClauseFactory query builder."""

    def test_with_id(self) -> None:
        clause = SwitchClauseFactory.with_id(1)
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_switch.id = 1"
        )

    def test_with_ids(self) -> None:
        clause = SwitchClauseFactory.with_ids([1, 2, 3])
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_switch.id IN (1, 2, 3)"
        )

    def test_with_name(self) -> None:
        clause = SwitchClauseFactory.with_name("test-switch")
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_switch.name = 'test-switch'"
        )

    def test_with_mac_address(self) -> None:
        clause = SwitchClauseFactory.with_mac_address("00:11:22:33:44:55")
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_switch.mac_address = '00:11:22:33:44:55'"
        )

    def test_with_vlan_id(self) -> None:
        clause = SwitchClauseFactory.with_vlan_id(5)
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_switch.vlan_id = 5"
        )

    def test_with_subnet_id(self) -> None:
        clause = SwitchClauseFactory.with_subnet_id(10)
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_switch.subnet_id = 10"
        )


class TestSwitchesRepository(RepositoryCommonTests[Switch]):
    """Tests for SwitchesRepository database operations."""

    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> SwitchesRepository:
        return SwitchesRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[Switch]:
        created_switches = [
            await create_test_switch(
                fixture,
                name=f"switch-{i}",
                mac_address=f"00:11:22:33:44:{i:02x}",
            )
            for i in range(num_objects)
        ]
        return created_switches

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> Switch:
        return await create_test_switch(
            fixture,
            name="test-switch",
            mac_address="aa:bb:cc:dd:ee:ff",
            description="Test switch instance",
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[SwitchBuilder]:
        return SwitchBuilder

    @pytest.fixture
    async def instance_builder(self) -> SwitchBuilder:
        return SwitchBuilder(
            name="new-switch",
            mac_address="11:22:33:44:55:66",
            description="A new switch",
        )

    async def test_create(
        self,
        repository_instance: SwitchesRepository,
        instance_builder: SwitchBuilder,
    ):
        """Test creating a switch."""
        resource = await repository_instance.create(instance_builder)
        assert resource.id > 0
        assert resource.name == "new-switch"
        assert resource.mac_address == "11:22:33:44:55:66"
        assert resource.description == "A new switch"

    async def test_list_with_query_by_name(
        self, repository_instance: SwitchesRepository, fixture: Fixture
    ) -> None:
        """Test listing switches filtered by name."""
        await create_test_switch(
            fixture, name="switch-alpha", mac_address="aa:aa:aa:aa:aa:01"
        )
        await create_test_switch(
            fixture, name="switch-beta", mac_address="bb:bb:bb:bb:bb:02"
        )
        await create_test_switch(
            fixture, name="switch-gamma", mac_address="cc:cc:cc:cc:cc:03"
        )

        retrieved_switches = await repository_instance.list(
            page=1,
            size=20,
            query=QuerySpec(
                where=SwitchClauseFactory.with_name("switch-beta")
            ),
        )
        assert len(retrieved_switches.items) == 1
        assert retrieved_switches.total == 1
        assert retrieved_switches.items[0].name == "switch-beta"

    async def test_list_with_query_by_mac_address(
        self, repository_instance: SwitchesRepository, fixture: Fixture
    ) -> None:
        """Test listing switches filtered by MAC address."""
        await create_test_switch(
            fixture, name="switch-1", mac_address="aa:aa:aa:aa:aa:aa"
        )
        target_switch = await create_test_switch(
            fixture, name="switch-2", mac_address="bb:bb:bb:bb:bb:bb"
        )
        await create_test_switch(
            fixture, name="switch-3", mac_address="cc:cc:cc:cc:cc:cc"
        )

        retrieved_switches = await repository_instance.list(
            page=1,
            size=20,
            query=QuerySpec(
                where=SwitchClauseFactory.with_mac_address("bb:bb:bb:bb:bb:bb")
            ),
        )
        assert len(retrieved_switches.items) == 1
        assert retrieved_switches.total == 1
        assert (
            retrieved_switches.items[0].mac_address
            == target_switch.mac_address
        )
        assert retrieved_switches.items[0].id == target_switch.id

    async def test_list_with_query_by_vlan(
        self, repository_instance: SwitchesRepository, fixture: Fixture
    ) -> None:
        """Test listing switches filtered by VLAN."""
        vlan1 = await create_test_vlan_entry(fixture)
        vlan2 = await create_test_vlan_entry(fixture)

        await create_test_switch(
            fixture,
            name="switch-1",
            mac_address="aa:aa:aa:aa:aa:01",
            vlan_id=vlan1["id"],
        )
        await create_test_switch(
            fixture,
            name="switch-2",
            mac_address="aa:aa:aa:aa:aa:02",
            vlan_id=vlan1["id"],
        )
        await create_test_switch(
            fixture,
            name="switch-3",
            mac_address="aa:aa:aa:aa:aa:03",
            vlan_id=vlan2["id"],
        )

        retrieved_switches = await repository_instance.list(
            page=1,
            size=20,
            query=QuerySpec(
                where=SwitchClauseFactory.with_vlan_id(vlan1["id"])
            ),
        )
        assert len(retrieved_switches.items) == 2
        assert retrieved_switches.total == 2
        assert all(
            sw.vlan_id == vlan1["id"] for sw in retrieved_switches.items
        )

    async def test_list_with_query_by_subnet(
        self, repository_instance: SwitchesRepository, fixture: Fixture
    ) -> None:
        """Test listing switches filtered by subnet."""
        subnet1 = await create_test_subnet_entry(fixture)
        subnet2 = await create_test_subnet_entry(fixture)

        await create_test_switch(
            fixture,
            name="switch-1",
            mac_address="bb:bb:bb:bb:bb:01",
            subnet_id=subnet1["id"],
        )
        await create_test_switch(
            fixture,
            name="switch-2",
            mac_address="bb:bb:bb:bb:bb:02",
            subnet_id=subnet2["id"],
        )
        await create_test_switch(
            fixture,
            name="switch-3",
            mac_address="bb:bb:bb:bb:bb:03",
            subnet_id=subnet1["id"],
        )

        retrieved_switches = await repository_instance.list(
            page=1,
            size=20,
            query=QuerySpec(
                where=SwitchClauseFactory.with_subnet_id(subnet1["id"])
            ),
        )
        assert len(retrieved_switches.items) == 2
        assert retrieved_switches.total == 2
        assert all(
            sw.subnet_id == subnet1["id"] for sw in retrieved_switches.items
        )

    async def test_update_switch(
        self,
        repository_instance: SwitchesRepository,
        created_instance: Switch,
    ) -> None:
        """Test updating a switch."""
        builder = SwitchBuilder(
            name="updated-switch",
            description="Updated description",
        )
        updated = await repository_instance.update_by_id(
            created_instance.id, builder
        )
        assert updated.id == created_instance.id
        assert updated.name == "updated-switch"
        assert updated.description == "Updated description"
        # MAC address should remain unchanged
        assert updated.mac_address == created_instance.mac_address

    async def test_delete_switch(
        self,
        repository_instance: SwitchesRepository,
        created_instance: Switch,
    ) -> None:
        """Test deleting a switch."""
        await repository_instance.delete_by_id(created_instance.id)

        # Verify it's deleted
        result = await repository_instance.get_by_id(created_instance.id)
        assert result is None
