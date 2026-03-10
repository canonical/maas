# Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.interfaces import InterfaceBuilder
from maasservicelayer.builders.switches import SwitchBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.interfaces import InterfaceRepository
from maasservicelayer.db.repositories.switches import (
    SwitchClauseFactory,
    SwitchesRepository,
)
from maasservicelayer.exceptions.catalog import AlreadyExistsException
from maasservicelayer.models.switches import Switch
from tests.fixtures.factories.switches import (
    create_test_switch,
    create_test_switch_interface,
)
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
            await create_test_switch(fixture) for i in range(num_objects)
        ]
        return created_switches

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> Switch:
        return await create_test_switch(fixture)

    @pytest.fixture
    async def instance_builder_model(self) -> type[SwitchBuilder]:
        return SwitchBuilder

    @pytest.fixture
    async def instance_builder(self) -> SwitchBuilder:
        return SwitchBuilder(
            target_image_id=None,
        )

    async def test_create(
        self,
        repository_instance: SwitchesRepository,
        instance_builder: SwitchBuilder,
    ):
        """Test creating a switch."""
        resource = await repository_instance.create(instance_builder)
        assert resource.id > 0
        assert resource.target_image_id is None

    async def test_update_switch(
        self,
        repository_instance: SwitchesRepository,
        created_instance: Switch,
    ) -> None:
        """Test updating a switch."""
        builder = SwitchBuilder(
            target_image_id=1,
        )
        updated = await repository_instance.update_by_id(
            created_instance.id, builder
        )
        assert updated.id == created_instance.id
        assert updated.target_image_id == 1

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

        # Create first switch with an interface
        switch1 = await create_test_switch(fixture, hostname="switch-1")
        await create_test_switch_interface(
            fixture, switch_id=switch1.id, mac_address="00:11:22:33:44:55"
        )

        # Create second switch
        switch2 = await create_test_switch(fixture, hostname="switch-2")

        # Try to create interface with duplicate MAC address through repository - should fail
        interface_repo = InterfaceRepository(Context(connection=db_connection))
        builder = InterfaceBuilder(
            name="mgmt", mac_address="00:11:22:33:44:55", switch_id=switch2.id
        )
        with pytest.raises(AlreadyExistsException):
            await interface_repo.create(builder)

    async def test_create_many_duplicated(
        self,
        db_connection: AsyncConnection,
        fixture: Fixture,
    ) -> None:
        """Test that creating multiple switches with duplicate MAC addresses in interfaces fails."""
        # Create first switch with an interface
        switch1 = await create_test_switch(fixture, hostname="switch-1")
        await create_test_switch_interface(
            fixture, switch_id=switch1.id, mac_address="00:11:22:33:44:55"
        )

        # Create second switch
        switch2 = await create_test_switch(fixture, hostname="switch-2")

        # Try to create multiple interfaces with duplicate MAC address - should fail
        interface_repo = InterfaceRepository(Context(connection=db_connection))

        with pytest.raises(AlreadyExistsException):
            await interface_repo.create_many(
                [
                    InterfaceBuilder(
                        name="eth0",
                        mac_address="aa:bb:cc:dd:ee:ff",
                        switch_id=switch1.id,
                    ),
                    InterfaceBuilder(
                        name="eth0",
                        mac_address="aa:bb:cc:dd:ee:ff",  # Duplicate MAC
                        switch_id=switch2.id,
                    ),
                ]
            )
