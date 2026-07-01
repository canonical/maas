# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
import datetime
import io
import random
import tarfile
from unittest.mock import AsyncMock, Mock

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
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.models.bootresources import BootResource
from maasservicelayer.models.bootresourcesets import BootResourceSet
from maasservicelayer.services.bootresourcefiles import (
    BootResourceFilesService,
)
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
            boot_resource_files_service=Mock(BootResourceFilesService),
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
    def mock_boot_resource_files_service(self) -> Mock:
        mock = Mock(BootResourceFilesService)
        mock.create_uploaded_file = AsyncMock(return_value=Mock())
        return mock

    @pytest.fixture
    def service(
        self,
        mock_repository: Mock,
        mock_boot_resource_sets_service: Mock,
        mock_boot_resource_files_service: Mock,
    ) -> BootResourceService:
        return BootResourceService(
            context=Context(),
            repository=mock_repository,
            boot_resource_sets_service=mock_boot_resource_sets_service,
            boot_resource_files_service=mock_boot_resource_files_service,
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
                    version=str(random.randint(20200618, 20250827)),
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
                    version=str(random.randint(20200618, 20250827)),
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
                        version=str(random.randint(20200618, 20250827)),
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

    @staticmethod
    def make_bootloader_tarball(files: dict[str, bytes]) -> bytes:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
            for name, content in files.items():
                info = tarfile.TarInfo(name=name)
                info.size = len(content)
                tar.addfile(info, io.BytesIO(content))
        return buffer.getvalue()

    async def test_upload_bootloader(
        self,
        mock_repository: Mock,
        mock_boot_resource_sets_service: Mock,
        mock_boot_resource_files_service: Mock,
        service: BootResourceService,
    ) -> None:
        mock_repository.find_or_create_bootloader.return_value = (
            TEST_BOOT_RESOURCE
        )
        mock_boot_resource_sets_service.create.return_value = BootResourceSet(
            id=99,
            created=utcnow(),
            updated=utcnow(),
            version="20250718",
            label="uploaded",
            resource_id=TEST_BOOT_RESOURCE.id,
        )
        service.get_next_version_name = AsyncMock(return_value="20250718")

        resource, version = await service.upload_bootloader(
            name="ubuntu/jammy",
            architecture="amd64/generic",
            sha256="a" * 64,
            primary_file="grubx64.efi",
            filename_on_disk="ab/cdef",
            size=1024,
        )

        assert resource == TEST_BOOT_RESOURCE
        assert version == "20250718"
        mock_repository.find_or_create_bootloader.assert_awaited_once_with(
            "ubuntu/jammy", "amd64/generic"
        )
        assert mock_boot_resource_files_service.create.await_count == 1

    async def test_upload_bootloader_duplicate_identity_versions(
        self,
        mock_repository: Mock,
        mock_boot_resource_sets_service: Mock,
        service: BootResourceService,
    ) -> None:
        mock_repository.find_or_create_bootloader.return_value = (
            TEST_BOOT_RESOURCE
        )
        mock_boot_resource_sets_service.create.return_value = BootResourceSet(
            id=100,
            created=utcnow(),
            updated=utcnow(),
            version="20250718.1",
            label="uploaded",
            resource_id=TEST_BOOT_RESOURCE.id,
        )
        service.get_next_version_name = AsyncMock(return_value="20250718.1")

        _, version = await service.upload_bootloader(
            name="ubuntu/jammy",
            architecture="amd64/generic",
            sha256="a" * 64,
            primary_file="grubx64.efi",
            filename_on_disk="ab/cdef",
            size=1024,
        )

        assert version == "20250718.1"

    async def test_upload_kernel(
        self,
        mock_repository: Mock,
        mock_boot_resource_sets_service: Mock,
        mock_boot_resource_files_service: Mock,
        service: BootResourceService,
    ) -> None:
        mock_repository.find_or_create_kernel.return_value = TEST_BOOT_RESOURCE
        mock_boot_resource_sets_service.create.return_value = BootResourceSet(
            id=101,
            created=utcnow(),
            updated=utcnow(),
            version="20250718",
            label="uploaded",
            resource_id=TEST_BOOT_RESOURCE.id,
        )
        service.get_next_version_name = AsyncMock(return_value="20250718")

        resource, version = await service.upload_kernel(
            name="ubuntu/noble",
            architecture="amd64/generic",
            kflavor="generic",
            sha256="a" * 64,
            filename_on_disk="aa/kernel",
            size=512,
        )

        assert resource == TEST_BOOT_RESOURCE
        assert version == "20250718"
        assert mock_boot_resource_files_service.create.await_count == 1

    async def test_upload_kernel_initrd(
        self,
        mock_boot_resource_sets_service: Mock,
        mock_boot_resource_files_service: Mock,
        service: BootResourceService,
    ) -> None:
        resource_set = BootResourceSet(
            id=101,
            created=utcnow(),
            updated=utcnow(),
            version="20250718",
            label="uploaded",
            resource_id=TEST_BOOT_RESOURCE.id,
        )
        service.get_one = AsyncMock(return_value=TEST_BOOT_RESOURCE)
        mock_boot_resource_sets_service.get_many = AsyncMock(
            return_value=[resource_set]
        )

        boot_resource, version = await service.upload_kernel_initrd(
            resource_id=TEST_BOOT_RESOURCE.id,
            sha256="b" * 64,
            filename_on_disk="bb/initrd",
            size=1024,
        )

        assert boot_resource == TEST_BOOT_RESOURCE
        assert version == "20250718"
        mock_boot_resource_files_service.create.assert_awaited_once()
        call_kwargs = mock_boot_resource_files_service.create.call_args[0][0]
        assert call_kwargs.filetype == BootResourceFileType.BOOT_INITRD

    async def test_upload_kernel_initrd_resource_not_found(
        self,
        service: BootResourceService,
    ) -> None:
        service.get_one = AsyncMock(return_value=None)

        with pytest.raises(NotFoundException):
            await service.upload_kernel_initrd(
                resource_id=TEST_BOOT_RESOURCE.id,
                sha256="b" * 64,
                filename_on_disk="bb/initrd",
                size=1024,
            )

    async def test_resolve_boot_asset_for_deployment(
        self, mock_repository: Mock, service: BootResourceService
    ) -> None:
        expected = BootResourceSet(
            id=102,
            created=utcnow(),
            updated=utcnow(),
            version="20250718",
            label="uploaded",
            resource_id=TEST_BOOT_RESOURCE.id,
        )
        mock_repository.get_bootloader_for_architecture.return_value = (
            TEST_BOOT_RESOURCE
        )
        mock_repository.get_latest_version.return_value = expected

        observed = await service.resolve_boot_asset_for_deployment(
            name="ubuntu/jammy",
            architecture="amd64/generic",
            asset_type="bootloader",
        )

        assert observed == expected

    async def test_resolve_boot_asset_for_deployment_raises_not_found(
        self, mock_repository: Mock, service: BootResourceService
    ) -> None:
        mock_repository.get_bootloader_for_architecture.return_value = None

        with pytest.raises(NotFoundException):
            await service.resolve_boot_asset_for_deployment(
                name="ubuntu/jammy",
                architecture="amd64/generic",
                asset_type="bootloader",
            )

    async def test_resolve_bootloader_for_deployment(
        self, service: BootResourceService
    ) -> None:
        expected = BootResourceSet(
            id=103,
            created=utcnow(),
            updated=utcnow(),
            version="20250718",
            label="uploaded",
            resource_id=TEST_BOOT_RESOURCE.id,
        )
        service.resolve_boot_asset_for_deployment = AsyncMock(
            return_value=expected
        )

        observed = await service.resolve_bootloader_for_deployment(
            bootloader_name="ubuntu/jammy",
            architecture="amd64/generic",
        )

        assert observed == expected
        service.resolve_boot_asset_for_deployment.assert_called_once_with(
            name="ubuntu/jammy",
            architecture="amd64/generic",
            asset_type="bootloader",
        )
