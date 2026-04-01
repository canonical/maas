# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.boot_resources import BootResourceType
from maasservicelayer.builders.bootresources import BootResourceBuilder
from maasservicelayer.builders.switches import SwitchBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bootresources import (
    BootResourcesRepository,
)
from maasservicelayer.db.repositories.switches import (
    SwitchClauseFactory,
    SwitchesRepository,
)
from maasservicelayer.models.bootresources import BootResource
from maasservicelayer.models.switches import Switch
from maasservicelayer.utils.date import utcnow
from tests.fixtures.factories.switches import create_test_switch
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

    @pytest.fixture
    async def boot_resource(
        self, db_connection: AsyncConnection
    ) -> BootResource:
        boot_resources = BootResourcesRepository(
            Context(connection=db_connection)
        )
        builder = BootResourceBuilder(
            alias="",
            architecture="amd64",
            bootloader_type=None,
            kflavor=None,
            name="onie/sonic",
            extra={},
            rolling=False,
            base_image="",
            rtype=BootResourceType.UPLOADED,
            last_deployed=None,
            created=utcnow(),
            updated=utcnow(),
        )
        return await boot_resources.create(builder)

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

    async def test_get_one_with_target_image(
        self,
        fixture: Fixture,
        boot_resource: BootResource,
        repository_instance: SwitchesRepository,
    ) -> None:
        switch_id = await create_test_switch(
            fixture, target_image_id=boot_resource.id
        )

        switch = await repository_instance.get_one_with_target_image(switch_id)
        assert switch is not None
        assert switch.target_image == "onie/sonic"
        assert switch.target_image_id == boot_resource.id

    async def test_get_one_with_target_image_no_image(
        self,
        created_instance: Switch,
        repository_instance: SwitchesRepository,
    ) -> None:
        switch = await repository_instance.get_one_with_target_image(
            created_instance.id
        )
        assert switch is not None
        assert switch.target_image is None
        assert switch.target_image_id is None

    async def test_list_with_target_image(
        self,
        fixture: Fixture,
        boot_resource: BootResource,
        repository_instance: SwitchesRepository,
    ) -> None:
        switch1_id = await create_test_switch(
            fixture, target_image_id=boot_resource.id
        )
        switch2_id = await create_test_switch(fixture)

        switches = await repository_instance.list_with_target_image(1, 2)
        assert switches.total == 2
        assert len(switches.items) == 2
        assert switches.items[0].id == switch1_id
        assert switches.items[0].target_image == "onie/sonic"
        assert switches.items[0].target_image_id == boot_resource.id
        assert switches.items[1].id == switch2_id
        assert switches.items[1].target_image is None
        assert switches.items[1].target_image_id is None

    async def test_list_with_target_image_with_pagination(
        self,
        fixture: Fixture,
        boot_resource: BootResource,
        repository_instance: SwitchesRepository,
    ) -> None:
        await create_test_switch(fixture, target_image_id=boot_resource.id)
        switch2_id = await create_test_switch(fixture)

        switches = await repository_instance.list_with_target_image(2, 1)
        assert switches.total == 2
        assert len(switches.items) == 1
        assert switches.items[0].id == switch2_id
        assert switches.items[0].target_image is None
        assert switches.items[0].target_image_id is None
