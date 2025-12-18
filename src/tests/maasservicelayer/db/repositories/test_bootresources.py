# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.boot_resources import BootResourceType
from maascommon.enums.node import NodeStatus
from maasservicelayer.builders.bootresources import BootResourceBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bootresources import (
    BootResourceClauseFactory,
    BootResourcesRepository,
)
from maasservicelayer.models.bootresources import BootResource
from tests.fixtures.factories.bootresources import (
    create_test_bootresource_entry,
    create_test_custom_bootresource_status_entry,
)
from tests.fixtures.factories.node import (
    create_test_machine_entry,
    create_test_region_controller_entry,
)
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestBootResourceClauseFactory:
    def test_with_name(self) -> None:
        clause = BootResourceClauseFactory.with_name("ubuntu/noble")
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootresource.name = 'ubuntu/noble'")

    def test_with_architecture(self) -> None:
        clause = BootResourceClauseFactory.with_architecture("amd64/generic")
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootresource.architecture = 'amd64/generic'")

    def test_with_architecture_starting_with(self) -> None:
        clause = BootResourceClauseFactory.with_architecture_starting_with(
            "amd64"
        )
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootresource.architecture LIKE 'amd64' || '%'")

    def test_with_alias(self) -> None:
        clause = BootResourceClauseFactory.with_alias("ubuntu/24.04")
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootresource.alias = 'ubuntu/24.04'")

    def test_with_rtype(self) -> None:
        clause = BootResourceClauseFactory.with_rtype(BootResourceType.SYNCED)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootresource.rtype = 0")

    def test_with_ids(self) -> None:
        clause = BootResourceClauseFactory.with_ids({1, 2, 3})
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootresource.id IN (1, 2, 3)")

    def test_with_selection_id(self) -> None:
        clause = BootResourceClauseFactory.with_selection_id(5)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootresource.selection_id = 5")

    def test_with_selection_ids(self) -> None:
        clause = BootResourceClauseFactory.with_selection_ids([1, 2])
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootresource.selection_id IN (1, 2)")

    def test_with_bootloader_type(self) -> None:
        clause = BootResourceClauseFactory.with_bootloader_type(None)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootresource.bootloader_type IS NULL")

    def test_with_selection_boot_source_id(self) -> None:
        clause = BootResourceClauseFactory.with_selection_boot_source_id(5)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootsourceselection.boot_source_id = 5")
        compiled_joins = [
            str(_join.compile(compile_kwargs={"literal_binds": True}))
            for _join in clause.joins
        ]
        assert len(compiled_joins) == 1
        assert (
            "maasserver_bootsourceselection JOIN maasserver_bootresource ON maasserver_bootsourceselection.id = maasserver_bootresource.selection_id"
            in compiled_joins
        )


class TestCommonBootResourceRepository(RepositoryCommonTests[BootResource]):
    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[BootResource]:
        return [
            await create_test_bootresource_entry(
                fixture,
                rtype=BootResourceType.SYNCED,
                name=f"ubuntu/noble-{i}",
                architecture="amd64/generic",
            )
            for i in range(num_objects)
        ]

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> BootResource:
        return await create_test_bootresource_entry(
            fixture,
            rtype=BootResourceType.SYNCED,
            name="ubuntu/noble",
            architecture="amd64/generic",
        )

    @pytest.fixture
    async def instance_builder(self, *args, **kwargs) -> BootResourceBuilder:
        return BootResourceBuilder(
            rtype=BootResourceType.SYNCED,
            name="ubuntu/jammy",
            architecture="amd64/generic",
            rolling=False,
            base_image="",
            extra={},
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[BootResourceBuilder]:
        return BootResourceBuilder

    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> BootResourcesRepository:
        return BootResourcesRepository(Context(connection=db_connection))

    @pytest.mark.skip(reason="Doesn't apply to boot resources")
    async def test_create_duplicated(
        self, repository_instance, instance_builder
    ):
        raise NotImplementedError()

    @pytest.mark.skip(reason="Doesn't apply to boot resources")
    async def test_create_many_duplicated(
        self, repository_instance, instance_builder
    ):
        raise NotImplementedError()


class TestBootResourceRepository:
    @pytest.fixture
    def repository(
        self, db_connection: AsyncConnection
    ) -> BootResourcesRepository:
        return BootResourcesRepository(Context(connection=db_connection))

    async def test_get_custom_image_status_by_id(
        self,
        repository: BootResourcesRepository,
        fixture: Fixture,
    ):
        region_controller = await create_test_region_controller_entry(
            fixture,
        )
        resource_ready = await create_test_custom_bootresource_status_entry(
            fixture,
            name="custom-image-1",
            architecture="amd64/generic",
            region_controller=region_controller,
        )
        fetched = await repository.get_custom_image_status_by_id(
            resource_ready.id
        )
        assert fetched == resource_ready

    async def test_get_custom_image_status_by_id__returns_none(
        self,
        repository: BootResourcesRepository,
    ):
        fetched = await repository.get_custom_image_status_by_id(0)
        assert fetched is None

    async def test_list_get_custom_images_status(
        self,
        repository: BootResourcesRepository,
        fixture: Fixture,
    ):
        region_controller = await create_test_region_controller_entry(
            fixture,
        )
        resource_ready = await create_test_custom_bootresource_status_entry(
            fixture,
            name="custom-image-1",
            architecture="amd64/generic",
            region_controller=region_controller,
        )

        resource_downloading = (
            await create_test_custom_bootresource_status_entry(
                fixture,
                name="custom-image-2",
                architecture="amd64/generic",
                region_controller=region_controller,
                sync_size=512,
            )
        )

        resource_waiting = await create_test_custom_bootresource_status_entry(
            fixture,
            name="custom-image-3",
            architecture="amd64/generic",
            region_controller=region_controller,
            sync_size=0,
        )

        status_list = await repository.list_custom_images_status(
            page=1, size=10
        )
        assert len(status_list.items) == 3

        assert resource_ready in status_list.items
        assert resource_downloading in status_list.items
        assert resource_waiting in status_list.items

    async def test_get_custom_image_statistic_by_id(
        self,
        repository: BootResourcesRepository,
        fixture: Fixture,
    ):
        region_controller = await create_test_region_controller_entry(
            fixture,
        )
        osystem = "custom"
        release = "image-1"
        arch = "amd64/generic"
        resource = await create_test_custom_bootresource_status_entry(
            fixture,
            name=f"{osystem}/{release}",
            architecture=arch,
            region_controller=region_controller,
        )

        for status in (
            NodeStatus.DEPLOYING,
            NodeStatus.DEPLOYED,
            NodeStatus.READY,
        ):
            await create_test_machine_entry(
                fixture,
                region_id=region_controller["id"],
                osystem=osystem,
                distro_series=release,
                architecture=arch,
                status=status,
            )

        stat = await repository.get_custom_image_statistic_by_id(resource.id)
        assert stat is not None
        assert stat.id == resource.id
        assert stat.last_updated is not None
        assert stat.last_deployed is None
        assert stat.size == 1024
        # only deployed and deploying nodes are counted
        assert stat.node_count == 2
        # file is of type ROOT_TGZ
        assert stat.deploy_to_memory is True

    async def test_get_custom_image_statistic_by_id__returns_none(
        self,
        repository: BootResourcesRepository,
    ):
        stat = await repository.get_custom_image_status_by_id(0)
        assert stat is None

    async def test_list_custom_image_statistics(
        self,
        repository: BootResourcesRepository,
        fixture: Fixture,
    ):
        region_controller = await create_test_region_controller_entry(
            fixture,
        )
        osystem = "custom"
        release = "image-1"
        arch = "amd64/generic"
        await create_test_custom_bootresource_status_entry(
            fixture,
            name=f"{osystem}/{release}",
            architecture=arch,
            region_controller=region_controller,
        )

        for status in (
            NodeStatus.DEPLOYING,
            NodeStatus.DEPLOYED,
            NodeStatus.READY,
        ):
            await create_test_machine_entry(
                fixture,
                region_id=region_controller["id"],
                osystem=osystem,
                distro_series=release,
                architecture=arch,
                status=status,
            )

        stats_list = await repository.list_custom_images_statistics(
            page=1, size=20
        )
        assert len(stats_list.items) == 1
        assert stats_list.total == 1
