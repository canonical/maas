# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.boot_resources import (
    BootResourceFileType,
    BootResourceType,
    ImageStatus,
    ImageUpdateStatus,
)
from maascommon.enums.node import NodeStatus
from maasservicelayer.builders.bootresources import BootResourceBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootresources import (
    BootResourceClauseFactory,
    BootResourcesRepository,
)
from maasservicelayer.models.bootresources import BootResource
from tests.fixtures.factories.bootresourcefiles import (
    create_test_bootresourcefile_entry,
)
from tests.fixtures.factories.bootresources import (
    create_test_bootresource_entry,
    create_test_custom_bootresource_status_entry,
)
from tests.fixtures.factories.bootresourcesets import (
    create_test_bootresourceset_entry,
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

    def test_with_filetype(self) -> None:
        clause = BootResourceClauseFactory.with_filetype(
            BootResourceFileType.SELF_EXTRACTING
        )
        compiled = str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        )
        assert (
            compiled
            == "maasserver_bootresource.id IN (SELECT DISTINCT maasserver_bootresourceset.resource_id \nFROM maasserver_bootresourceset JOIN maasserver_bootresourcefile ON maasserver_bootresourcefile.resource_set_id = maasserver_bootresourceset.id \nWHERE maasserver_bootresourcefile.filetype = 'self-extracting')"
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

    async def test_get_custom_image_status_by_id__no_resource_set(
        self,
        repository: BootResourcesRepository,
        fixture: Fixture,
    ):
        resource = await create_test_bootresource_entry(
            fixture,
            rtype=BootResourceType.UPLOADED,
            name="custom/noble",
            architecture="amd64/generic",
        )
        status = await repository.get_custom_image_status_by_id(resource.id)

        assert status is not None
        assert status.status == ImageStatus.WAITING_FOR_DOWNLOAD
        assert status.update_status == ImageUpdateStatus.NO_UPDATES_AVAILABLE
        assert status.sync_percentage == 0
        assert status.selected is True

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

    async def test_list_with_filetype_filter(
        self,
        repository: BootResourcesRepository,
        fixture: Fixture,
    ):
        """Test filtering boot resources by file type."""

        # Create boot resource with self-extracting file (switch image)
        switch_resource = await create_test_bootresource_entry(
            fixture,
            rtype=BootResourceType.UPLOADED,
            name="onie/cumulus",
            architecture="amd64/generic",
        )
        switch_set = await create_test_bootresourceset_entry(
            fixture,
            version="1.0",
            label="release",
            resource_id=switch_resource.id,
        )
        await create_test_bootresourcefile_entry(
            fixture,
            filename="installer.bin",
            filetype=BootResourceFileType.SELF_EXTRACTING,
            sha256="switch123",
            size=2048,
            filename_on_disk="installer.bin",
            resource_set_id=switch_set.id,
        )

        # Create boot resource with tgz file (regular image)
        regular_resource = await create_test_bootresource_entry(
            fixture,
            rtype=BootResourceType.UPLOADED,
            name="custom/noble",
            architecture="amd64/generic",
        )
        regular_set = await create_test_bootresourceset_entry(
            fixture,
            version="20.04",
            label="release",
            resource_id=regular_resource.id,
        )
        await create_test_bootresourcefile_entry(
            fixture,
            filename="root.tgz",
            filetype=BootResourceFileType.ROOT_TGZ,
            sha256="ubuntu123",
            size=1024,
            filename_on_disk="root.tgz",
            resource_set_id=regular_set.id,
        )

        result = await repository.list(
            page=1,
            size=10,
            query=QuerySpec(
                where=BootResourceClauseFactory.and_clauses(
                    [
                        BootResourceClauseFactory.with_rtype(
                            BootResourceType.UPLOADED
                        ),
                        BootResourceClauseFactory.with_filetype(
                            BootResourceFileType.SELF_EXTRACTING
                        ),
                    ]
                )
            ),
        )

        assert result.total == 1
        assert len(result.items) == 1
        assert result.items[0].id == switch_resource.id
        assert result.items[0].name == "onie/cumulus"

        result_tgz = await repository.list(
            page=1,
            size=10,
            query=QuerySpec(
                where=BootResourceClauseFactory.and_clauses(
                    [
                        BootResourceClauseFactory.with_rtype(
                            BootResourceType.UPLOADED
                        ),
                        BootResourceClauseFactory.with_filetype(
                            BootResourceFileType.ROOT_TGZ
                        ),
                    ]
                )
            ),
        )

        assert result_tgz.total == 1
        assert len(result_tgz.items) == 1
        assert result_tgz.items[0].id == regular_resource.id
        assert result_tgz.items[0].name == "custom/noble"

    async def test_list_with_filetype_filter_no_duplicates(
        self,
        repository: BootResourcesRepository,
        fixture: Fixture,
    ):
        """Test that filtering by file type doesn't return duplicates when a resource has multiple sets."""
        multi_version_resource = await create_test_bootresource_entry(
            fixture,
            rtype=BootResourceType.UPLOADED,
            name="onie/cumulus",
            architecture="amd64/generic",
        )

        set_v1 = await create_test_bootresourceset_entry(
            fixture,
            version="1.0",
            label="release",
            resource_id=multi_version_resource.id,
        )
        await create_test_bootresourcefile_entry(
            fixture,
            filename="installer_v1.bin",
            filetype=BootResourceFileType.SELF_EXTRACTING,
            sha256="sonic123v1",
            size=2048,
            filename_on_disk="installer_v1.bin",
            resource_set_id=set_v1.id,
        )

        set_v2 = await create_test_bootresourceset_entry(
            fixture,
            version="2.0",
            label="release",
            resource_id=multi_version_resource.id,
        )
        await create_test_bootresourcefile_entry(
            fixture,
            filename="installer_v2.bin",
            filetype=BootResourceFileType.SELF_EXTRACTING,
            sha256="sonic123v2",
            size=3072,
            filename_on_disk="installer_v2.bin",
            resource_set_id=set_v2.id,
        )

        result = await repository.list(
            page=1,
            size=10,
            query=QuerySpec(
                where=BootResourceClauseFactory.and_clauses(
                    [
                        BootResourceClauseFactory.with_rtype(
                            BootResourceType.UPLOADED
                        ),
                        BootResourceClauseFactory.with_filetype(
                            BootResourceFileType.SELF_EXTRACTING
                        ),
                    ]
                )
            ),
        )

        assert result.total == 1
        assert len(result.items) == 1
        assert result.items[0].id == multi_version_resource.id
        assert result.items[0].name == "onie/cumulus"

    async def test_list_with_combined_filters(
        self,
        repository: BootResourcesRepository,
        fixture: Fixture,
    ):
        """Test combining file type filter with other filters."""

        resources = []
        for i in range(3):
            resource = await create_test_bootresource_entry(
                fixture,
                rtype=BootResourceType.UPLOADED,
                name=f"onie/image-{i}",
                architecture="amd64/generic",
            )
            resource_set = await create_test_bootresourceset_entry(
                fixture,
                version=f"{i}.0",
                label="release",
                resource_id=resource.id,
            )
            await create_test_bootresourcefile_entry(
                fixture,
                filename=f"installer-{i}.bin",
                filetype=BootResourceFileType.SELF_EXTRACTING,
                sha256=f"hash{i}",
                size=1024 * (i + 1),
                filename_on_disk=f"installer-{i}.bin",
                resource_set_id=resource_set.id,
            )
            resources.append(resource)

        # Filter by IDs and file type
        target_ids = [resources[0].id, resources[2].id]
        result = await repository.list(
            page=1,
            size=10,
            query=QuerySpec(
                where=BootResourceClauseFactory.and_clauses(
                    [
                        BootResourceClauseFactory.with_rtype(
                            BootResourceType.UPLOADED
                        ),
                        BootResourceClauseFactory.with_ids(target_ids),
                        BootResourceClauseFactory.with_filetype(
                            BootResourceFileType.SELF_EXTRACTING
                        ),
                    ]
                )
            ),
        )

        # Should return only resources 0 and 2
        assert result.total == 2
        assert len(result.items) == 2
        returned_ids = {item.id for item in result.items}
        assert returned_ids == set(target_ids)

    async def test_find_or_create_bootloader_creates_new(
        self, repository: BootResourcesRepository
    ) -> None:
        bootloader = await repository.find_or_create_bootloader(
            "ubuntu/jammy", "amd64/generic"
        )

        assert bootloader.name == "ubuntu/jammy"
        assert bootloader.architecture == "amd64/generic"
        assert bootloader.rtype == BootResourceType.UPLOADED
        assert bootloader.bootloader_type == "custom"

    async def test_find_or_create_bootloader_returns_existing(
        self, repository: BootResourcesRepository, fixture: Fixture
    ) -> None:
        existing = await create_test_bootresource_entry(
            fixture,
            rtype=BootResourceType.UPLOADED,
            name="ubuntu/jammy",
            architecture="amd64/generic",
            bootloader_type="custom",
        )

        bootloader = await repository.find_or_create_bootloader(
            "ubuntu/jammy", "amd64/generic"
        )

        assert bootloader.id == existing.id

    async def test_find_or_create_kernel_creates_new(
        self, repository: BootResourcesRepository
    ) -> None:
        kernel = await repository.find_or_create_kernel(
            "ubuntu/noble", "amd64/generic", "generic"
        )

        assert kernel.name == "ubuntu/noble"
        assert kernel.architecture == "amd64/generic"
        assert kernel.rtype == BootResourceType.UPLOADED
        assert kernel.kflavor == "generic"
        assert kernel.bootloader_type is None

    async def test_find_or_create_kernel_returns_existing(
        self, repository: BootResourcesRepository, fixture: Fixture
    ) -> None:
        existing = await create_test_bootresource_entry(
            fixture,
            rtype=BootResourceType.UPLOADED,
            name="ubuntu/noble",
            architecture="amd64/generic",
            kflavor="generic",
            bootloader_type=None,
        )

        kernel = await repository.find_or_create_kernel(
            "ubuntu/noble", "amd64/generic", "generic"
        )

        assert kernel.id == existing.id

    async def test_get_latest_version(
        self, repository: BootResourcesRepository, fixture: Fixture
    ) -> None:
        resource = await create_test_bootresource_entry(
            fixture,
            rtype=BootResourceType.UPLOADED,
            name="ubuntu/jammy",
            architecture="amd64/generic",
            bootloader_type="custom",
        )
        await create_test_bootresourceset_entry(
            fixture,
            version="20250101",
            label="uploaded",
            resource_id=resource.id,
        )
        latest = await create_test_bootresourceset_entry(
            fixture,
            version="20250102",
            label="uploaded",
            resource_id=resource.id,
        )

        observed = await repository.get_latest_version(resource.id)

        assert observed is not None
        assert observed.id == latest.id
        assert observed.version == latest.version

    async def test_get_bootloader_for_architecture(
        self, repository: BootResourcesRepository, fixture: Fixture
    ) -> None:
        expected = await create_test_bootresource_entry(
            fixture,
            rtype=BootResourceType.UPLOADED,
            name="ubuntu/jammy",
            architecture="amd64/generic",
            bootloader_type="custom",
        )
        await create_test_bootresource_entry(
            fixture,
            rtype=BootResourceType.UPLOADED,
            name="ubuntu/jammy",
            architecture="arm64/generic",
            bootloader_type="custom",
        )

        observed = await repository.get_bootloader_for_architecture(
            "ubuntu/jammy", "amd64/generic"
        )

        assert observed is not None
        assert observed.id == expected.id

    async def test_get_bootloader_file_for_set(
        self, repository: BootResourcesRepository, fixture: Fixture
    ) -> None:
        resource = await create_test_bootresource_entry(
            fixture,
            rtype=BootResourceType.UPLOADED,
            name="ubuntu/jammy",
            architecture="amd64/generic",
            bootloader_type="custom",
        )
        resource_set = await create_test_bootresourceset_entry(
            fixture,
            version="20250101",
            label="uploaded",
            resource_id=resource.id,
        )
        expected = await create_test_bootresourcefile_entry(
            fixture,
            filename="bootloader.tar.gz",
            filetype=BootResourceFileType.BOOTLOADER_TARBALL,
            sha256="a" * 64,
            size=1024,
            filename_on_disk="abcdef1234",
            resource_set_id=resource_set.id,
        )

        observed = await repository.get_bootloader_file_for_set(
            resource_set.id
        )

        assert observed is not None
        assert observed.id == expected.id
        assert observed.filename == expected.filename
