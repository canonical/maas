# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.boot_resources import (
    BootResourceFileType,
    ImageStatus,
    ImageUpdateStatus,
)
from maascommon.enums.node import NodeStatus
from maasservicelayer.builders.bootsourceselections import (
    BootSourceSelectionBuilder,
)
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootsourceselections import (
    BootSourceSelectionClauseFactory,
    BootSourceSelectionsRepository,
    BootSourceSelectionStatusClauseFactory,
    BootSourceSelectionStatusRepository,
)
from maasservicelayer.db.tables import BootResourceTable
from maasservicelayer.models.bootresources import BootResource
from maasservicelayer.models.bootsourceselections import (
    BootSourceSelection,
    BootSourceSelectionStatus,
)
from tests.fixtures.factories.boot_sources import create_test_bootsource_entry
from tests.fixtures.factories.bootresourcefiles import (
    create_test_bootresourcefile_entry,
)
from tests.fixtures.factories.bootresourcefilesync import (
    create_test_bootresourcefilesync_entry,
)
from tests.fixtures.factories.bootresourcesets import (
    create_test_bootresourceset_entry,
)
from tests.fixtures.factories.bootsourceselections import (
    create_test_bootsourceselection_entry,
)
from tests.fixtures.factories.bootsourceselectionview import (
    create_test_selection_status_entry,
)
from tests.fixtures.factories.node import (
    create_test_machine_entry,
    create_test_region_controller_entry,
)
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import (
    ReadOnlyRepositoryCommonTests,
    RepositoryCommonTests,
)


class TestBootSourceSelectionClauseFactory:
    def test_with_id(self) -> None:
        clause = BootSourceSelectionClauseFactory.with_id(1)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootsourceselection.id = 1")

    def test_with_ids(self) -> None:
        clause = BootSourceSelectionClauseFactory.with_ids([1, 2])
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootsourceselection.id IN (1, 2)")

    def test_with_boot_source_id(self) -> None:
        clause = BootSourceSelectionClauseFactory.with_boot_source_id(1)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootsourceselection.boot_source_id = 1")

    def test_with_boot_source_ids(self) -> None:
        clause = BootSourceSelectionClauseFactory.with_boot_source_ids([1, 2])
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootsourceselection.boot_source_id IN (1, 2)")

    def test_with_os(self) -> None:
        clause = BootSourceSelectionClauseFactory.with_os("ubuntu")
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootsourceselection.os = 'ubuntu'")

    def test_with_release(self) -> None:
        clause = BootSourceSelectionClauseFactory.with_release("noble")
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootsourceselection.release = 'noble'")


class TestCommonBootSourceSelectionRepository(
    RepositoryCommonTests[BootSourceSelection]
):
    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[BootSourceSelection]:
        return [
            await create_test_bootsourceselection_entry(
                fixture,
                os="ubuntu",
                release=f"noble-{i}",
                boot_source_id=1,
                arch="amd64",
            )
            for i in range(num_objects)
        ]

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> BootSourceSelection:
        return await create_test_bootsourceselection_entry(
            fixture,
            os="ubuntu",
            release="noble",
            boot_source_id=1,
            arch="amd64",
        )

    @pytest.fixture
    async def instance_builder(
        self, *args, **kwargs
    ) -> BootSourceSelectionBuilder:
        return BootSourceSelectionBuilder(
            os="ubuntu",
            release="jammy",
            arch="amd64",
            boot_source_id=1,
            legacyselection_id=10,
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[BootSourceSelectionBuilder]:
        return BootSourceSelectionBuilder

    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> BootSourceSelectionsRepository:
        return BootSourceSelectionsRepository(
            Context(connection=db_connection)
        )

    async def test_update_one(self, repository_instance, instance_builder):
        with pytest.raises(NotImplementedError):
            return await super().test_update_one(
                repository_instance, instance_builder
            )

    @pytest.mark.parametrize("num_objects", [2])
    async def test_update_one_multiple_results(
        self,
        repository_instance,
        instance_builder_model,
        _setup_test_list,
        num_objects,
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_update_one_multiple_results(
                repository_instance,
                instance_builder_model,
                _setup_test_list,
                2,
            )

    @pytest.mark.parametrize("num_objects", [2])
    async def test_update_many(
        self,
        repository_instance,
        instance_builder_model,
        _setup_test_list,
        num_objects,
    ):
        with pytest.raises(NotImplementedError):
            await repository_instance.update_many(
                QuerySpec(), BootSourceSelectionBuilder()
            )

    async def test_update_by_id(self, repository_instance, instance_builder):
        with pytest.raises(NotImplementedError):
            return await super().test_update_by_id(
                repository_instance, instance_builder
            )


class TestBootSourceSelectionRepository:
    @pytest.fixture
    def repository(self, db_connection: AsyncConnection):
        return BootSourceSelectionsRepository(
            context=Context(connection=db_connection)
        )

    async def test_get_all_highest_priority(
        self, fixture: Fixture, repository: BootSourceSelectionsRepository
    ) -> None:
        source_1 = await create_test_bootsource_entry(
            fixture, url="http://foo.com", priority=1
        )
        source_2 = await create_test_bootsource_entry(
            fixture, url="http://bar.com", priority=2
        )
        selection_1 = await create_test_bootsourceselection_entry(
            fixture,
            os="ubuntu",
            release="noble",
            arch="amd64",
            boot_source_id=source_1.id,
        )
        selection_2 = await create_test_bootsourceselection_entry(
            fixture,
            os="ubuntu",
            release="noble",
            arch="amd64",
            boot_source_id=source_2.id,
        )

        selections = await repository.get_all_highest_priority()
        assert len(selections) == 1
        assert selection_1 not in selections
        assert selection_2 in selections

    async def test_get_selection_statistic_by_id(
        self, repository: BootSourceSelectionsRepository, fixture: Fixture
    ):
        region_controller = await create_test_region_controller_entry(
            fixture,
        )
        created = await create_test_selection_status_entry(
            fixture,
            region_controller=region_controller,
            os="ubuntu",
            release="jammy",
            arch="amd64",
        )
        for status in (
            NodeStatus.DEPLOYING,
            NodeStatus.DEPLOYED,
            NodeStatus.READY,
        ):
            await create_test_machine_entry(
                fixture,
                region_id=region_controller["id"],
                osystem="ubuntu",
                distro_series="jammy",
                architecture="amd64/generic",
                status=status,
            )
        stat = await repository.get_selection_statistic_by_id(created.id)

        assert stat is not None
        assert stat.id == created.id
        assert stat.last_updated is not None
        assert stat.last_deployed is None
        assert stat.size == 1024
        # only deployed and deploying nodes are counted
        assert stat.node_count == 2
        # squashfs is present
        assert stat.deploy_to_memory is True

    async def test_get_selection_statistic_by_id__no_resource_yet(
        self, fixture: Fixture, repository: BootSourceSelectionsRepository
    ):
        selection = await create_test_bootsourceselection_entry(
            fixture,
            os="ubuntu",
            release="noble",
            arch="amd64",
            boot_source_id=1,
        )
        stat = await repository.get_selection_statistic_by_id(selection.id)
        assert stat is not None
        assert stat.last_updated is None
        assert stat.last_deployed is None
        assert stat.size == 0
        assert stat.deploy_to_memory is False
        assert stat.node_count == 0

    async def test_get_selection_statistic_by_id__returns_none(
        self, repository: BootSourceSelectionsRepository
    ):
        stat = await repository.get_selection_statistic_by_id(0)
        assert stat is None

    async def test_list_selection_statistics(
        self, repository: BootSourceSelectionsRepository, fixture: Fixture
    ):
        region_controller = await create_test_region_controller_entry(
            fixture,
        )
        await create_test_selection_status_entry(
            fixture,
            region_controller=region_controller,
            os="ubuntu",
            release="jammy",
            arch="amd64",
        )
        for status in (
            NodeStatus.DEPLOYING,
            NodeStatus.DEPLOYED,
            NodeStatus.READY,
        ):
            await create_test_machine_entry(
                fixture,
                region_id=region_controller["id"],
                osystem="ubuntu",
                distro_series="jammy",
                architecture="amd64/generic",
                status=status,
            )
        stats_list = await repository.list_selections_statistics(
            page=1, size=20
        )
        assert len(stats_list.items) == 1
        assert stats_list.total == 1


class TestBootSourceSelectionStatusClauseFactory:
    def test_with_ids(self) -> None:
        clause = BootSourceSelectionStatusClauseFactory.with_ids([1, 2])
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_bootsourceselectionstatus_view.id IN (1, 2)")


class TestCommonBootSourceSelectionStatusRepository(
    ReadOnlyRepositoryCommonTests[BootSourceSelectionStatus]
):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> BootSourceSelectionStatusRepository:
        return BootSourceSelectionStatusRepository(
            Context(connection=db_connection)
        )

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[BootSourceSelectionStatus]:
        region = await create_test_region_controller_entry(
            fixture,
        )
        boot_source = await create_test_bootsource_entry(
            fixture,
            name="test-boot-source",
            url="http://example.com",
            priority=1,
        )
        return [
            await create_test_selection_status_entry(
                fixture,
                os="ubuntu",
                release=f"noble-{i}",
                arch="amd64",
                boot_source=boot_source,
                region_controller=region,
            )
            for i in range(num_objects)
        ]

    @pytest.fixture
    async def created_instance(
        self, fixture: Fixture
    ) -> BootSourceSelectionStatus:
        return await create_test_selection_status_entry(
            fixture,
            release="jammy",
        )


class TestBootSourceSelectionStatusRepository:
    @pytest.fixture
    def repository(
        self, db_connection: AsyncConnection
    ) -> BootSourceSelectionStatusRepository:
        return BootSourceSelectionStatusRepository(
            Context(connection=db_connection)
        )

    async def test_ready(
        self, repository: BootSourceSelectionStatusRepository, fixture: Fixture
    ):
        created = await create_test_selection_status_entry(fixture)
        fetched = await repository.get_by_id(created.id)

        assert fetched is not None
        assert fetched.status == ImageStatus.READY
        assert fetched.update_status == ImageUpdateStatus.NO_UPDATES_AVAILABLE
        assert fetched.sync_percentage == 100.0

    async def test_downloading(
        self, repository: BootSourceSelectionStatusRepository, fixture: Fixture
    ):
        created = await create_test_selection_status_entry(
            fixture, file_size=1024, sync_size=512
        )
        fetched = await repository.get_by_id(created.id)

        assert fetched is not None
        assert fetched.status == ImageStatus.DOWNLOADING
        assert fetched.update_status == ImageUpdateStatus.NO_UPDATES_AVAILABLE
        assert fetched.sync_percentage == 50.0

    async def test_waiting_for_download(
        self, repository: BootSourceSelectionStatusRepository, fixture: Fixture
    ):
        created = await create_test_selection_status_entry(
            fixture, sync_size=0
        )
        fetched = await repository.get_by_id(created.id)

        assert fetched is not None
        assert fetched.status == ImageStatus.WAITING_FOR_DOWNLOAD
        assert fetched.update_status == ImageUpdateStatus.NO_UPDATES_AVAILABLE
        assert fetched.sync_percentage == 0.0

    async def test_update_available(
        self, repository: BootSourceSelectionStatusRepository, fixture: Fixture
    ):
        created = await create_test_selection_status_entry(
            fixture, cache_version="2", set_version="1"
        )
        fetched = await repository.get_by_id(created.id)

        assert fetched is not None
        assert fetched.status == ImageStatus.READY
        assert fetched.update_status == ImageUpdateStatus.UPDATE_AVAILABLE
        assert fetched.sync_percentage == 100.0

    async def test_downloading_update(
        self, repository: BootSourceSelectionStatusRepository, fixture: Fixture
    ):
        region_controller = await create_test_region_controller_entry(fixture)
        created = await create_test_selection_status_entry(
            fixture,
            cache_version="2",
            set_version="1",
            region_controller=region_controller,
        )
        boot_resource = (
            await fixture.get_typed(
                BootResourceTable.name,
                BootResource,
                eq(BootResourceTable.c.selection_id, created.id),
            )
        )[0]

        # create a boot resource set with the same version of the cache
        boot_resource_set = await create_test_bootresourceset_entry(
            fixture, version="2", label="stable", resource_id=boot_resource.id
        )
        boot_resource_file = await create_test_bootresourcefile_entry(
            fixture,
            filename="file",
            filetype=BootResourceFileType.SQUASHFS_IMAGE,
            sha256="abc123",
            size=1024,
            filename_on_disk="file",
            resource_set_id=boot_resource_set.id,
        )
        # currently downloading as the size is less than the file size
        await create_test_bootresourcefilesync_entry(
            fixture,
            size=512,
            file_id=boot_resource_file.id,
            region_id=region_controller["id"],
        )

        fetched = await repository.get_by_id(created.id)

        assert fetched is not None
        assert fetched.status == ImageStatus.READY
        assert fetched.update_status == ImageUpdateStatus.DOWNLOADING
        assert fetched.sync_percentage == 50.0

    async def test_selected(
        self, repository: BootSourceSelectionStatusRepository, fixture: Fixture
    ):
        boot_source_1 = await create_test_bootsource_entry(
            fixture, name="source-1", url="http://example.com/1", priority=1
        )
        boot_source_2 = await create_test_bootsource_entry(
            fixture, name="source-2", url="http://example.com/2", priority=2
        )
        s1 = await create_test_selection_status_entry(
            fixture, boot_source=boot_source_1
        )
        s2 = await create_test_selection_status_entry(
            fixture, boot_source=boot_source_2
        )
        not_selected = await repository.get_by_id(s1.id)
        selected = await repository.get_by_id(s2.id)

        assert selected is not None
        assert not_selected is not None

        assert selected.selected is True
        assert not_selected.selected is False
