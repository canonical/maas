# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.switches import SwitchBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.switches import (
    SwitchClauseFactory,
    SwitchesRepository,
)
from maasservicelayer.models.switches import Switch
from tests.fixtures.factories.switches import create_test_switch
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestSwitchesRepository(RepositoryCommonTests[Switch]):
    """Tests for SwitchesRepository database operations."""

    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> SwitchesRepository:
        return SwitchesRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self,
        fixture: Fixture,
        num_objects: int,
        repository_instance: SwitchesRepository,
    ) -> list[Switch]:
        switch_ids = [
            await create_test_switch(fixture) for i in range(num_objects)
        ]
        created_switches = [
            await repository_instance.get_by_id(switch_id)
            for switch_id in switch_ids
        ]
        return [s for s in created_switches if s is not None]

    @pytest.fixture
    async def created_instance(
        self, fixture: Fixture, repository_instance: SwitchesRepository
    ) -> Switch:
        switch_id = await create_test_switch(fixture)
        switch = await repository_instance.get_by_id(switch_id)
        assert switch is not None
        return switch

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
        resource = await repository_instance.create(instance_builder)
        assert resource.id > 0
        assert resource.target_image_id is None

    async def test_update_switch(
        self,
        repository_instance: SwitchesRepository,
        created_instance: Switch,
    ) -> None:
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
        await repository_instance.delete_by_id(created_instance.id)

        result = await repository_instance.get_by_id(created_instance.id)
        assert result is None

    @pytest.mark.skip(
        reason="Switches have no unique constraints on model fields"
    )
    async def test_create_duplicated(
        self, repository_instance, instance_builder
    ):
        pass

    @pytest.mark.skip(
        reason="Switches have no unique constraints on model fields"
    )
    async def test_create_many_duplicated(
        self, repository_instance, instance_builder
    ):
        pass
