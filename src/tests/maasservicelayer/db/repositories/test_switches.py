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
from tests.fixtures.factories.switches import create_test_switch, create_test_switch_interface
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

    def test_with_hostname(self) -> None:
        clause = SwitchClauseFactory.with_hostname("test-switch")
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_switch.hostname = 'test-switch'"
        )

    def test_with_vendor(self) -> None:
        clause = SwitchClauseFactory.with_vendor("Cisco")
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_switch.vendor = 'Cisco'"
        )

    def test_with_state(self) -> None:
        clause = SwitchClauseFactory.with_state("ready")
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_switch.state = 'ready'"
        )

    def test_with_serial_number(self) -> None:
        clause = SwitchClauseFactory.with_serial_number("SN123456")
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_switch.serial_number = 'SN123456'"
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
                hostname=f"switch-{i}",
                serial_number=f"SN{i:04d}",
                state="registered",
            )
            for i in range(num_objects)
        ]
        return created_switches

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> Switch:
        return await create_test_switch(
            fixture,
            hostname="test-switch",
            vendor="Cisco",
            state="registered",
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[SwitchBuilder]:
        return SwitchBuilder

    @pytest.fixture
    async def instance_builder(self) -> SwitchBuilder:
        return SwitchBuilder(
            hostname="new-switch",
            vendor="Juniper",
            state="registered",
            serial_number="TEST-SN-123456",
        )

    async def test_create(
        self,
        repository_instance: SwitchesRepository,
        instance_builder: SwitchBuilder,
    ):
        """Test creating a switch."""
        resource = await repository_instance.create(instance_builder)
        assert resource.id > 0
        assert resource.hostname == "new-switch"
        assert resource.vendor == "Juniper"
        assert resource.state == "registered"

    async def test_list_with_query_by_hostname(
        self, repository_instance: SwitchesRepository, fixture: Fixture
    ) -> None:
        """Test listing switches filtered by hostname."""
        await create_test_switch(
            fixture, hostname="switch-alpha", state="registered"
        )
        await create_test_switch(
            fixture, hostname="switch-beta", state="registered"
        )
        await create_test_switch(
            fixture, hostname="switch-gamma", state="registered"
        )

        retrieved_switches = await repository_instance.list(
            page=1,
            size=20,
            query=QuerySpec(
                where=SwitchClauseFactory.with_hostname("switch-beta")
            ),
        )
        assert len(retrieved_switches.items) == 1
        assert retrieved_switches.total == 1
        assert retrieved_switches.items[0].hostname == "switch-beta"

    async def test_list_with_query_by_vendor(
        self, repository_instance: SwitchesRepository, fixture: Fixture
    ) -> None:
        """Test listing switches filtered by vendor."""
        await create_test_switch(
            fixture, hostname="switch-1", vendor="Cisco", state="registered"
        )
        target_switch = await create_test_switch(
            fixture, hostname="switch-2", vendor="Juniper", state="registered"
        )
        await create_test_switch(
            fixture, hostname="switch-3", vendor="Cisco", state="registered"
        )

        retrieved_switches = await repository_instance.list(
            page=1,
            size=20,
            query=QuerySpec(where=SwitchClauseFactory.with_vendor("Juniper")),
        )
        assert len(retrieved_switches.items) == 1
        assert retrieved_switches.total == 1
        assert retrieved_switches.items[0].vendor == target_switch.vendor
        assert retrieved_switches.items[0].id == target_switch.id

    async def test_list_with_query_by_state(
        self, repository_instance: SwitchesRepository, fixture: Fixture
    ) -> None:
        """Test listing switches filtered by state."""
        await create_test_switch(
            fixture,
            hostname="switch-1",
            state="registered",
        )
        await create_test_switch(
            fixture,
            hostname="switch-2",
            state="ready",
        )
        target_switch = await create_test_switch(
            fixture,
            hostname="switch-3",
            state="broken",
        )

        retrieved_switches = await repository_instance.list(
            page=1,
            size=20,
            query=QuerySpec(where=SwitchClauseFactory.with_state("broken")),
        )
        assert len(retrieved_switches.items) == 1
        assert retrieved_switches.total == 1
        assert retrieved_switches.items[0].state == "broken"
        assert retrieved_switches.items[0].id == target_switch.id

    async def test_update_switch(
        self,
        repository_instance: SwitchesRepository,
        created_instance: Switch,
    ) -> None:
        """Test updating a switch."""
        builder = SwitchBuilder(
            hostname="updated-switch",
            state="ready",
        )
        updated = await repository_instance.update_by_id(
            created_instance.id, builder
        )
        assert updated.id == created_instance.id
        assert updated.hostname == "updated-switch"
        assert updated.state == "ready"

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

    async def test_create_duplicated(
        self,
        db_connection: AsyncConnection,
        fixture: Fixture,
    ) -> None:
        """Test that creating switches with duplicate MAC addresses in interfaces fails."""
        from maasservicelayer.db.repositories.switches import SwitchInterfacesRepository
        from maasservicelayer.builders.switches import SwitchInterfaceBuilder
        from maasservicelayer.exceptions.catalog import AlreadyExistsException
        from maasservicelayer.context import Context
        
        # Create first switch with an interface
        switch1 = await create_test_switch(
            fixture, hostname="switch-1", state="registered"
        )
        await create_test_switch_interface(
            fixture, switch_id=switch1.id, mac_address="00:11:22:33:44:55"
        )

        # Create second switch
        switch2 = await create_test_switch(
            fixture, hostname="switch-2", state="registered"
        )

        # Try to create interface with duplicate MAC address through repository - should fail
        interface_repo = SwitchInterfacesRepository(Context(connection=db_connection))
        builder = SwitchInterfaceBuilder(
            name="mgmt",
            mac_address="00:11:22:33:44:55",
            switch_id=switch2.id
        )
        with pytest.raises(AlreadyExistsException):
            await interface_repo.create(builder)

    async def test_create_many_duplicated(
        self,
        db_connection: AsyncConnection,
        fixture: Fixture,
    ) -> None:
        """Test that creating multiple switches with duplicate MAC addresses in interfaces fails."""
        from maasservicelayer.db.repositories.switches import SwitchInterfacesRepository
        from maasservicelayer.builders.switches import SwitchInterfaceBuilder
        from maasservicelayer.exceptions.catalog import AlreadyExistsException
        from maasservicelayer.context import Context
        
        # Create first switch with an interface
        switch1 = await create_test_switch(
            fixture, hostname="switch-1", state="registered"
        )
        await create_test_switch_interface(
            fixture, switch_id=switch1.id, mac_address="00:11:22:33:44:55"
        )

        # Create second switch
        switch2 = await create_test_switch(
            fixture, hostname="switch-2", state="registered"
        )
        
        # Try to create multiple interfaces with duplicate MAC address - should fail
        interface_repo = SwitchInterfacesRepository(Context(connection=db_connection))
        
        with pytest.raises(AlreadyExistsException):
            await interface_repo.create_many([
                SwitchInterfaceBuilder(
                    name="eth0",
                    mac_address="aa:bb:cc:dd:ee:ff",
                    switch_id=switch1.id,
                ),
                SwitchInterfaceBuilder(
                    name="eth0",
                    mac_address="aa:bb:cc:dd:ee:ff",  # Duplicate MAC
                    switch_id=switch2.id,
                ),
            ])
