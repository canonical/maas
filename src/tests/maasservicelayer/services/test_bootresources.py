# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
import datetime
import random
from unittest.mock import Mock

import pytest

from maascommon.enums.boot_resources import (
    BootResourceFileType,
    BootResourceType,
)
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootresources import (
    BootResourceClauseFactory,
    BootResourcesRepository,
)
from maasservicelayer.db.repositories.bootresourcesets import (
    BootResourceSetClauseFactory,
)
from maasservicelayer.models.bootresources import BootResource
from maasservicelayer.models.bootresourcesets import BootResourceSet
from maasservicelayer.services.bootresources import BootResourceService
from maasservicelayer.services.bootresourcesets import BootResourceSetsService
from maasservicelayer.utils.date import utcnow
from maastesting.factory import factory
from tests.fixtures.factories.bootresourcefiles import (
    create_test_bootresourcefile_entry,
)
from tests.fixtures.factories.bootresources import (
    create_test_bootresource_entry,
)
from tests.fixtures.factories.bootresourcesets import (
    create_test_bootresourceset_entry,
)
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.services.base import ServiceCommonTests

TEST_BOOT_RESOURCE = BootResource(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    rtype=BootResourceType.SYNCED,
    name="ubuntu/noble",
    architecture="amd64/generic",
    rolling=False,
    base_image="",
    extra={},
)


class TestCommonBootResourceService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BootResourceService:
        return BootResourceService(
            context=Context(),
            repository=Mock(BootResourcesRepository),
            boot_resource_sets_service=Mock(BootResourceSetsService),
        )

    @pytest.fixture
    def test_instance(self) -> BootResource:
        return TEST_BOOT_RESOURCE


class TestBootResourceService:
    @pytest.fixture
    def mock_repository(self) -> Mock:
        return Mock(BootResourcesRepository)

    @pytest.fixture
    def mock_boot_resource_sets_service(self) -> Mock:
        return Mock(BootResourceSetsService)

    @pytest.fixture
    def service(
        self, mock_repository: Mock, mock_boot_resource_sets_service: Mock
    ) -> BootResourceService:
        return BootResourceService(
            context=Context(),
            repository=mock_repository,
            boot_resource_sets_service=mock_boot_resource_sets_service,
        )

    async def make_incomplete_boot_resource(
        self,
        architecture: str,
        fixture: Fixture,
    ) -> None:
        await create_test_bootresource_entry(
            fixture=fixture,
            rtype=BootResourceType.UPLOADED,
            name="",
            architecture=architecture,
        )

    async def make_usable_boot_resource(
        self,
        architecture: str,
        fixture: Fixture,
        version: str = "",
        label: str = "",
        image_filetype: BootResourceFileType = BootResourceFileType.SQUASHFS_IMAGE,
    ) -> tuple[BootResource, BootResourceSet]:
        boot_resource = await create_test_bootresource_entry(
            fixture=fixture,
            rtype=BootResourceType.UPLOADED,
            name="test-name",
            architecture=architecture,
        )

        boot_resource_set = await create_test_bootresourceset_entry(
            fixture=fixture,
            version=version,
            label=label,
            resource_id=boot_resource.id,
        )

        filetypes = {
            BootResourceFileType.BOOT_KERNEL,
            BootResourceFileType.BOOT_INITRD,
        }
        filetypes.add(image_filetype)

        for filetype in filetypes:
            await self.make_boot_resource_file_with_content(
                fixture=fixture,
                resource_set=boot_resource_set,
                filetype=filetype,
            )

        return (boot_resource, boot_resource_set)

    async def make_boot_resource_file_with_content(
        self,
        fixture: Fixture,
        resource_set: BootResourceSet,
        filetype: BootResourceFileType,
    ) -> None:
        await create_test_bootresourcefile_entry(
            fixture=fixture,
            filename=factory.make_name(),
            filename_on_disk=factory.make_name(),
            filetype=filetype,
            sha256=factory.make_hex_string(size=16),
            size=random.randint(100, 1024),
            resource_set_id=resource_set.id,
        )

    async def test_pre_delete_hook(
        self,
        mock_repository: Mock,
        mock_boot_resource_sets_service: Mock,
        service: BootResourceService,
    ) -> None:
        mock_repository.get_by_id.return_value = TEST_BOOT_RESOURCE
        await service.delete_by_id(TEST_BOOT_RESOURCE.id)
        mock_boot_resource_sets_service.delete_many.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceSetClauseFactory.with_resource_id(
                    TEST_BOOT_RESOURCE.id
                )
            )
        )

    async def test_pre_delete_many_hook(
        self,
        mock_repository: Mock,
        mock_boot_resource_sets_service: Mock,
        service: BootResourceService,
    ) -> None:
        mock_repository.get_many.return_value = [TEST_BOOT_RESOURCE]
        await service.delete_many(query=QuerySpec())
        mock_boot_resource_sets_service.delete_many.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceSetClauseFactory.with_resource_ids(
                    [TEST_BOOT_RESOURCE.id]
                )
            )
        )

    async def test_delete_all_without_sets(
        self,
        mock_repository: Mock,
        mock_boot_resource_sets_service: Mock,
        service: BootResourceService,
    ) -> None:
        mock_boot_resource_sets_service.get_many.return_value = [
            BootResourceSet(
                id=1,
                created=utcnow(),
                updated=utcnow(),
                version="20250618",
                label="stable",
                resource_id=TEST_BOOT_RESOURCE.id,
            ),
        ]

        await service.delete_all_without_sets(query=QuerySpec())

        mock_repository.delete_many.assert_awaited_once_with(
            query=QuerySpec(where=BootResourceClauseFactory.with_ids(set()))
        )

    async def test_delete_all_without_sets_delete_all_boot_resources(
        self,
        mock_repository: Mock,
        mock_boot_resource_sets_service: Mock,
        service: BootResourceService,
    ) -> None:
        mock_repository.get_many.return_value = [TEST_BOOT_RESOURCE]
        mock_boot_resource_sets_service.get_many.return_value = []

        await service.delete_all_without_sets(query=QuerySpec())

        mock_repository.delete_many.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceClauseFactory.with_ids(
                    {TEST_BOOT_RESOURCE.id}
                )
            )
        )

    async def test_get_usable_architectures(
        self,
        service: BootResourceService,
        mock_repository: Mock,
        mock_boot_resource_sets_service: Mock,
    ) -> None:
        num_archs = 3
        architectures = []
        for _ in range(1, num_archs + 1):
            architectures.append(
                f"{factory.make_name('arch')}/{factory.make_name('subarch')}"
            )

        # Create several usable resources
        resources = []
        complete_sets = []
        for i in range(1, num_archs + 1):
            resources.append(
                BootResource(
                    id=i,
                    created=utcnow(),
                    updated=utcnow(),
                    rtype=BootResourceType.UPLOADED,
                    name=f"ubuntu/{factory.make_name()}",
                    architecture=architectures[i - 1],
                    rolling=False,
                    base_image="",
                    extra={},
                )
            )
            complete_sets.append(
                BootResourceSet(
                    id=i,
                    resource_id=i,
                    version=random.randint(20200618, 20250827),
                    label=factory.make_name(),
                )
            )
        # ...and an incomplete one
        resources.append(
            BootResource(
                id=num_archs + 1,
                created=utcnow(),
                updated=utcnow(),
                rtype=BootResourceType.UPLOADED,
                name=f"ubuntu/{factory.make_name()}",
                architecture=architectures[-1],
                rolling=False,
                base_image="",
                extra={},
            ),
        )
        complete_sets.append(
            None,
        )

        mock_repository.get_many.return_value = resources
        mock_boot_resource_sets_service.get_latest_complete_set_for_boot_resource.side_effects = complete_sets
        mock_boot_resource_sets_service.is_usable.return_value = True
        mock_boot_resource_sets_service.is_xinstallable.return_value = True

        usable_architectures = await service.get_usable_architectures()

        assert len(usable_architectures) == num_archs

    async def test_get_usable_architectures_combines_subarches(
        self,
        service: BootResourceService,
        mock_repository: Mock,
        mock_boot_resource_sets_service: Mock,
    ) -> None:
        resources = []
        complete_sets = []

        num_archs = 3
        architectures = []
        for i in range(1, num_archs + 1):
            arch = factory.make_name("arch")
            subarches = [factory.make_name("subarch") for _ in range(3)]
            architecture = f"{arch}/{subarches[0]}"
            for subarch in subarches:
                architectures.append(f"{arch}/{subarch}")

            resources.append(
                BootResource(
                    id=i,
                    created=utcnow(),
                    updated=utcnow(),
                    rtype=BootResourceType.UPLOADED,
                    name=f"ubuntu/{factory.make_name()}",
                    architecture=architecture,
                    rolling=False,
                    base_image="",
                    extra={"subarches": ",".join(subarches)},
                )
            )
            complete_sets.append(
                BootResourceSet(
                    id=i,
                    resource_id=i,
                    version=random.randint(20200618, 20250827),
                    label=factory.make_name(),
                )
            )

        mock_repository.get_many.return_value = resources
        mock_boot_resource_sets_service.get_latest_complete_set_for_boot_resource.side_effects = complete_sets
        mock_boot_resource_sets_service.is_usable.return_value = True
        mock_boot_resource_sets_service.is_xinstallable.return_value = True

        usable_architectures = await service.get_usable_architectures()

        assert len(usable_architectures) == len(architectures)

    async def test_get_usable_architectures_combines_platforms(
        self,
        service: BootResourceService,
        mock_repository: Mock,
        mock_boot_resource_sets_service: Mock,
    ) -> None:
        resources = []
        complete_sets = []

        num_archs = 3
        architectures = []
        for i in range(1, num_archs + 1):
            arch = factory.make_name("arch")
            platforms = [factory.make_name("platform") for _ in range(3)]
            for i, platform in enumerate(platforms):
                architectures.append(f"{arch}/{platform}")
                architectures.append(f"{arch}/{platform}-supported")
                architectures.append(f"{arch}/{platform}-also-supported")

                resources.append(
                    BootResource(
                        id=i,
                        created=utcnow(),
                        updated=utcnow(),
                        rtype=BootResourceType.UPLOADED,
                        name=f"ubuntu/{factory.make_name()}",
                        architecture=f"{arch}/hwe-{i}",
                        rolling=False,
                        base_image="",
                        extra={
                            "platform": platform,
                            "supported_platforms": f"{platform}-supported,{platform}-also-supported",
                        },
                    )
                )
                complete_sets.append(
                    BootResourceSet(
                        id=i,
                        resource_id=i,
                        version=random.randint(20200618, 20250827),
                        label=factory.make_name(),
                    )
                )

        mock_repository.get_many.return_value = resources
        mock_boot_resource_sets_service.get_latest_complete_set_for_boot_resource.side_effects = complete_sets
        mock_boot_resource_sets_service.is_usable.return_value = True
        mock_boot_resource_sets_service.is_xinstallable.return_value = True

        usable_architectures = await service.get_usable_architectures()

        assert len(usable_architectures) == len(architectures)

    async def test_get_next_version_name_returns_current_date(
        self,
        mock_boot_resource_sets_service: Mock,
        service: BootResourceService,
    ) -> None:
        boot_resource_id = 42

        mock_boot_resource_sets_service.get_many.return_value = []

        version_name = await service.get_next_version_name(boot_resource_id)

        expected_version_name = datetime.datetime.today().strftime("%Y%m%d")

        assert version_name == expected_version_name

    async def test_get_next_version_name_returns_first_revision(
        self,
        mock_boot_resource_sets_service: Mock,
        service: BootResourceService,
    ) -> None:
        boot_resource_id = 42

        mock_boot_resource_sets_service.get_many.return_value = [
            BootResourceSet(
                id=0,
                version="",
                label="",
                resource_id=boot_resource_id,
            )
        ]

        version_name = await service.get_next_version_name(boot_resource_id)

        current_date_string = datetime.datetime.today().strftime("%Y%m%d")
        expected_version_name = f"{current_date_string}.1"

        assert version_name == expected_version_name

    async def test_get_next_version_name_returns_latest_revision(
        self,
        mock_boot_resource_sets_service: Mock,
        service: BootResourceService,
    ) -> None:
        boot_resource_id = 42
        current_date_string = datetime.datetime.today().strftime("%Y%m%d")

        set_count = random.randint(2, 4)
        test_sets_to_return = []
        for set_id in range(set_count):
            version_str = current_date_string
            if set_id > 0:
                version_str = f"{current_date_string}.{set_id}"
            test_sets_to_return.append(
                BootResourceSet(
                    id=set_id,
                    version=version_str,
                    label="",
                    resource_id=boot_resource_id,
                )
            )
        mock_boot_resource_sets_service.get_many.return_value = (
            test_sets_to_return
        )

        version_name = await service.get_next_version_name(boot_resource_id)

        expected_version_name = f"{current_date_string}.{set_count}"

        assert version_name == expected_version_name

    async def test_get_custom_image_status_by_id(
        self,
        mock_repository: Mock,
        service: BootResourceService,
    ) -> None:
        mock_repository.get_custom_image_status_by_id.return_value = None

        await service.get_custom_image_status_by_id(1)

        mock_repository.get_custom_image_status_by_id.assert_awaited_once()

    async def test_list_custom_images_status(
        self,
        mock_repository: Mock,
        service: BootResourceService,
    ) -> None:
        mock_repository.list_custom_images_status.return_value = []

        await service.list_custom_images_status(page=1, size=10)

        mock_repository.list_custom_images_status.assert_awaited_once()

    async def test_get_custom_image_statistic_by_id(
        self,
        mock_repository: Mock,
        service: BootResourceService,
    ) -> None:
        await service.get_custom_image_statistic_by_id(1)
        mock_repository.get_custom_image_statistic_by_id.assert_awaited_once_with(
            1
        )

    async def test_list_custom_images_statistic(
        self,
        mock_repository: Mock,
        service: BootResourceService,
    ) -> None:
        await service.list_custom_images_statistics(page=1, size=10)
        mock_repository.list_custom_images_statistics.assert_awaited_once_with(
            page=1, size=10, query=None
        )
