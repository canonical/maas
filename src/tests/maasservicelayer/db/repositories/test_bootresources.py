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
from maasservicelayer.db.repositories.bootresources import (
    BootResourcesRepository,
)
from maasservicelayer.filters.bootresources import (
    BootResourceFilters,
    BootResourceOrdering,
)
from maasservicelayer.filters.query import OrderBy, QuerySpec
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
from tests.fixtures.factories.bootsourceselections import (
    create_test_bootsourceselection_entry,
)
from tests.fixtures.factories.node import (
    create_test_machine_entry,
    create_test_region_controller_entry,
)
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


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
            region_controllers=[region_controller],
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

    async def test_get_custom_image_status_by_id__multiple_regions(
        self,
        repository: BootResourcesRepository,
        fixture: Fixture,
    ):
        region_controllers = [
            await create_test_region_controller_entry(fixture)
            for _ in range(3)
        ]
        resource_ready = await create_test_custom_bootresource_status_entry(
            fixture,
            name="custom-image-1",
            architecture="amd64/generic",
            region_controllers=region_controllers,
        )
        fetched = await repository.get_custom_image_status_by_id(
            resource_ready.id
        )
        assert fetched == resource_ready

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
            region_controllers=[region_controller],
        )

        resource_downloading = (
            await create_test_custom_bootresource_status_entry(
                fixture,
                name="custom-image-2",
                architecture="amd64/generic",
                region_controllers=[region_controller],
                sync_size=512,
            )
        )

        resource_waiting = await create_test_custom_bootresource_status_entry(
            fixture,
            name="custom-image-3",
            architecture="amd64/generic",
            region_controllers=[region_controller],
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
            region_controllers=[region_controller],
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
            region_controllers=[region_controller],
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
                where=BootResourceFilters.and_filters(
                    [
                        BootResourceFilters.with_rtype(
                            BootResourceType.UPLOADED
                        ),
                        BootResourceFilters.with_filetype(
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
                where=BootResourceFilters.and_filters(
                    [
                        BootResourceFilters.with_rtype(
                            BootResourceType.UPLOADED
                        ),
                        BootResourceFilters.with_filetype(
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

    async def test_domain_architecture_and_source_filters(
        self, repository, fixture
    ):
        selection = await create_test_bootsourceselection_entry(
            fixture,
            os="ubuntu",
            release="jammy",
            arch="amd64",
            boot_source_id=1,
        )
        selected = await create_test_bootresource_entry(
            fixture,
            rtype=BootResourceType.SYNCED,
            name="ubuntu/jammy",
            architecture="amd64/generic",
            selection_id=selection.id,
        )
        await create_test_bootresource_entry(
            fixture,
            rtype=BootResourceType.SYNCED,
            name="ubuntu/jammy",
            architecture="arm64/generic",
            selection_id=selection.id,
        )
        result = await repository.get_many(
            QuerySpec(
                where=BootResourceFilters.and_filters(
                    [
                        BootResourceFilters.with_selection_id(selection.id),
                        BootResourceFilters.with_architecture_starting_with(
                            "amd64"
                        ),
                        BootResourceFilters.with_selection_boot_source_id(1),
                    ]
                ),
            )
        )
        assert result == [selected]

    @pytest.mark.parametrize("descending", [False, True])
    async def test_domain_name_priority_ordering(
        self, repository, fixture, descending
    ):
        names = ["custom/first", "custom/second", "custom/unlisted"]
        for name in names:
            await create_test_bootresource_entry(
                fixture,
                rtype=BootResourceType.UPLOADED,
                name=name,
                architecture="amd64/generic",
            )
        order = BootResourceOrdering.by_name_with_priority(names[:2])
        if descending:
            order = BootResourceOrdering.desc(order)
        result = await repository.get_many(
            QuerySpec(
                where=BootResourceFilters.with_names(names),
                order_by=(order,),
            )
        )
        expected = list(reversed(names)) if descending else names
        assert [resource.name for resource in result] == expected

    @pytest.mark.parametrize(
        "method",
        ["list_custom_images_status", "list_custom_images_statistics"],
    )
    async def test_custom_image_lists_accept_domain_filters(
        self, repository, fixture, method
    ):
        selected = await create_test_custom_bootresource_status_entry(
            fixture,
            name="custom/selected",
            architecture="amd64/generic",
        )
        await create_test_custom_bootresource_status_entry(
            fixture,
            name="custom/other",
            architecture="amd64/generic",
        )
        result = await getattr(repository, method)(
            page=1,
            size=10,
            query=QuerySpec(
                where=BootResourceFilters.with_id(selected.id),
                order_by=(OrderBy(BootResource, "name"),),
            ),
        )
        assert result.total == 1
        assert [image.id for image in result.items] == [selected.id]

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
                where=BootResourceFilters.and_filters(
                    [
                        BootResourceFilters.with_rtype(
                            BootResourceType.UPLOADED
                        ),
                        BootResourceFilters.with_filetype(
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
                where=BootResourceFilters.and_filters(
                    [
                        BootResourceFilters.with_rtype(
                            BootResourceType.UPLOADED
                        ),
                        BootResourceFilters.with_ids(target_ids),
                        BootResourceFilters.with_filetype(
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
