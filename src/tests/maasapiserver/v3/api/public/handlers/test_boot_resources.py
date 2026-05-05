# Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import hashlib
from io import BytesIO
from typing import Callable
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from aiofiles.threadpool.binary import AsyncBufferedIOBase
from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.responses.boot_images_common import (
    ImageListResponse,
    ImageResponse,
    ImageStatisticListResponse,
    ImageStatisticResponse,
    ImageStatusListResponse,
)
from maasapiserver.v3.api.public.models.responses.boot_resources import (
    BootAssetUploadResponse,
    BootloaderListResponse,
    BootloaderResponse,
    KernelListResponse,
    KernelResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.boot_resources import (
    BootResourceFileType,
    BootResourceType,
    ImageStatus,
)
from maascommon.enums.node import NodeStatus, NodeTypeEnum
from maascommon.enums.power import PowerState
from maascommon.openfga.base import MAASResourceEntitlement
from maascommon.workflows.bootresource import (
    ResourceDownloadParam,
    short_sha,
    SYNC_BOOTRESOURCES_WORKFLOW_NAME,
    SyncRequestParam,
)
from maasservicelayer.builders.bootresources import BootResourceBuilder
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootresources import (
    BootResourceClauseFactory,
)
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    NotFoundException,
    PreconditionFailedException,
    ValidationException,
)
from maasservicelayer.exceptions.constants import (
    ETAG_PRECONDITION_VIOLATION_TYPE,
    INVALID_ARGUMENT_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.bootresourcefiles import BootResourceFile
from maasservicelayer.models.bootresources import (
    BootResource,
    CustomBootResourceStatistic,
    CustomBootResourceStatus,
)
from maasservicelayer.models.bootresourcesets import BootResourceSet
from maasservicelayer.models.nodes import Node
from maasservicelayer.services import (
    BootSourceCacheService,
    ServiceCollectionV3,
)
from maasservicelayer.services.bootresourcefiles import (
    BootResourceFilesService,
)
from maasservicelayer.services.bootresourcefilesync import (
    BootResourceFileSyncService,
)
from maasservicelayer.services.bootresources import BootResourceService
from maasservicelayer.services.bootresourcesets import BootResourceSetsService
from maasservicelayer.services.nodes import NodesService
from maasservicelayer.services.temporal import TemporalService
from maasservicelayer.utils.date import utcnow
from maastesting.factory import factory
from tests.fixtures import AsyncContextManagerMock
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)


class MockTemporaryFile:
    """Mock async temporary file for testing without real disk I/O."""

    def __init__(self, name: str = "test-tmp-file.txt"):
        self._written_data = b""
        self._name = name

    async def write(self, chunk) -> int:
        self._written_data += chunk
        return len(chunk)

    async def tell(self) -> int:
        return len(self._written_data)

    @property
    def name(self) -> str:
        return self._name

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


# Pytest Fixtures


@pytest.fixture
def test_boot_resource_1() -> BootResource:
    """Standard custom boot resource for testing."""
    return BootResource(
        id=1,
        created=utcnow(),
        updated=utcnow(),
        rtype=BootResourceType.UPLOADED,
        name="custom/noble-image",
        architecture="amd64/generic",
        rolling=False,
        base_image="",
        extra={},
    )


@pytest.fixture
def test_boot_resource_2() -> BootResource:
    """Standard synced boot resource for testing."""
    return BootResource(
        id=1,
        created=utcnow(),
        updated=utcnow(),
        rtype=BootResourceType.SYNCED,
        name="ubuntu/noble",
        architecture="amd64/generic",
        extra={},
        kflavor=None,
        bootloader_type=None,
        rolling=False,
        base_image="ubuntu/noble",
        alias=None,
        last_deployed=None,
    )


@pytest.fixture
def test_bootloader_resource() -> BootResource:
    """Standard bootloader resource for testing."""
    return BootResource(
        id=10,
        created=utcnow(),
        updated=utcnow(),
        rtype=BootResourceType.UPLOADED,
        name="grub-efi/uefi",
        architecture="amd64/generic",
        rolling=False,
        base_image="",
        extra={},
        kflavor=None,
        bootloader_type="uefi",
        alias=None,
        last_deployed=None,
    )


@pytest.fixture
def test_kernel_resource() -> BootResource:
    """Standard kernel resource for testing."""
    return BootResource(
        id=11,
        created=utcnow(),
        updated=utcnow(),
        rtype=BootResourceType.UPLOADED,
        name="ubuntu/noble",
        architecture="amd64/generic",
        rolling=False,
        base_image="",
        extra={},
        kflavor="generic",
        bootloader_type=None,
        alias=None,
        last_deployed=None,
    )


@pytest.fixture
def test_boot_resource_set() -> BootResourceSet:
    """Standard boot resource set for testing."""
    return BootResourceSet(
        id=1,
        created=utcnow(),
        updated=utcnow(),
        version="20250829",
        label="uploaded",
        resource_id=1,
    )


@pytest.fixture
def test_boot_resource_file() -> BootResourceFile:
    """Standard boot resource file for testing."""
    return BootResourceFile(
        id=1,
        created=utcnow(),
        updated=utcnow(),
        filename="test.bin",
        filetype=BootResourceFileType.ROOT_TGZ,
        extra={},
        sha256="",
        size=1024,
        filename_on_disk="test.bin",
        resource_set_id=1,
    )


class TestCustomImagesApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/custom_images"

    @pytest.fixture
    def endpoints_with_authorization(self) -> list[Endpoint]:
        return [
            Endpoint(
                method="GET",
                path=self.BASE_PATH,
                permission=MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
            ),
            Endpoint(
                method="GET",
                path=f"{self.BASE_PATH}/1",
                permission=MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
            ),
            Endpoint(
                method="POST",
                path=self.BASE_PATH,
                permission=MAASResourceEntitlement.CAN_EDIT_BOOT_ENTITIES,
            ),
            Endpoint(
                method="POST",
                path=f"{V3_API_PREFIX}/boot_assets/bootloaders",
                permission=MAASResourceEntitlement.CAN_EDIT_BOOT_ENTITIES,
            ),
            Endpoint(
                method="POST",
                path=f"{V3_API_PREFIX}/boot_assets/kernels",
                permission=MAASResourceEntitlement.CAN_EDIT_BOOT_ENTITIES,
            ),
            Endpoint(
                method="DELETE",
                path=f"{self.BASE_PATH}?id=1",
                permission=MAASResourceEntitlement.CAN_EDIT_BOOT_ENTITIES,
            ),
            Endpoint(
                method="DELETE",
                path=f"{self.BASE_PATH}/1",
                permission=MAASResourceEntitlement.CAN_EDIT_BOOT_ENTITIES,
            ),
        ]

    def create_dummy_binary_upload_file(
        self,
        name: str | None = "test_upload_file.bin",
        size_in_bytes: int = 1024,
    ) -> BytesIO:
        assert size_in_bytes >= 0, "Size of dummy file must be positive"
        file_bytes = BytesIO()
        file_bytes.name = name
        file_bytes.write(b"0" * size_in_bytes)
        file_bytes.seek(0)
        return file_bytes

    @patch("maasapiserver.v3.api.public.handlers.boot_resources.MAAS_ID")
    @patch(
        "maasservicelayer.utils.image_local_files.AsyncLocalBootResourceFile"
    )
    @patch(
        "maasapiserver.v3.api.public.handlers.boot_resources.BootResourceCreateRequest.to_builder"
    )
    async def test_upload_custom_image(
        self,
        request_to_builder_mock: MagicMock,
        async_local_file_mock: MagicMock,
        maas_id_mock: MagicMock,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
        test_boot_resource_1: BootResource,
        test_boot_resource_set: BootResourceSet,
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_BOOT_ENTITIES,
        )
        file_name = "test.bin"
        file_size = 1024
        file_data = self.create_dummy_binary_upload_file(
            name=file_name, size_in_bytes=file_size
        )

        sha256 = hashlib.sha256()
        sha256.update(file_data.read())
        sha256_str = sha256.hexdigest()
        file_data.seek(0)

        resource_file = Mock(BootResourceFile)
        resource_file.id = 1
        resource_file.sha256 = sha256_str
        resource_file.filename_on_disk = file_name
        resource_file.size = file_size

        request_to_builder_mock.return_value = BootResourceBuilder(
            name=test_boot_resource_1.name,
            architecture=test_boot_resource_1.architecture,
            base_image=test_boot_resource_1.base_image,
            rtype=BootResourceType.UPLOADED,
            extra={},
            alias="",
            bootloader_type=None,
            kflavor=None,
            rolling=False,
            last_deployed=None,
            created=utcnow(),
            updated=utcnow(),
        )

        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.upload_custom_image.return_value = (
            test_boot_resource_1,
            resource_file,
        )

        services_mock.boot_resource_files = Mock(BootResourceFilesService)
        services_mock.boot_resource_files.calculate_filename_on_disk.return_value = file_name

        maas_id_mock.get.return_value = "abc1de"

        node_mock = Mock(Node)
        node_mock.id = 1

        services_mock.nodes = Mock(NodesService)
        services_mock.nodes.get_one.return_value = node_mock

        services_mock.boot_resource_file_sync = Mock(
            BootResourceFileSyncService
        )
        services_mock.boot_resource_file_sync.get_or_create.return_value = (
            None,
            True,
        )

        services_mock.temporal = Mock(TemporalService)
        services_mock.temporal.register_or_update_workflow_call.return_value = None

        async_local_file_mock.store.return_value = AsyncContextManagerMock(
            Mock(AsyncBufferedIOBase)
        )

        headers = {
            "name": "my-image",
            "sha256": sha256_str,
            "architecture": "amd64/generic",
            "Content-Type": "application/octet-stream",
        }

        raw_data = file_data.read()
        response = await client.post(
            url=f"{self.BASE_PATH}",
            headers=headers,
            content=raw_data,
        )

        assert response.status_code == 201

        boot_resource_response = ImageResponse(**response.json())

        assert (
            boot_resource_response.os
            == test_boot_resource_1.name.split("/")[0]
        )
        assert (
            boot_resource_response.release
            == test_boot_resource_1.name.split("/")[1]
        )
        assert (
            boot_resource_response.architecture
            == test_boot_resource_1.split_arch()[0]
        )

        services_mock.boot_resource_file_sync.get_or_create.assert_called_once()

        services_mock.temporal.register_or_update_workflow_call.assert_called_once_with(
            SYNC_BOOTRESOURCES_WORKFLOW_NAME,
            SyncRequestParam(
                resource=ResourceDownloadParam(
                    rfile_ids=[resource_file.id],
                    source_list=[],
                    sha256=sha256_str,
                    filename_on_disk=file_name,
                    total_size=file_size,
                ),
            ),
            workflow_id=f"sync-bootresources:{short_sha(resource_file.sha256)}",
            wait=False,
        )

    @patch(
        "maasservicelayer.utils.image_local_files.AsyncLocalBootResourceFile"
    )
    @patch(
        "maasapiserver.v3.api.public.handlers.boot_resources.BootResourceCreateRequest.to_builder"
    )
    async def test_upload_custom_image_400_sha_does_not_match(
        self,
        request_to_builder_mock: MagicMock,
        async_local_file_mock: MagicMock,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
        test_boot_resource_1: BootResource,
        test_boot_resource_set: BootResourceSet,
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_BOOT_ENTITIES,
        )
        file_name = "test.bin"
        file_size = 1024
        file_data = self.create_dummy_binary_upload_file(
            name=file_name, size_in_bytes=file_size
        )

        request_to_builder_mock.return_value = None

        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.create.return_value = test_boot_resource_1
        services_mock.boot_resources.get_next_version_name.return_value = (
            test_boot_resource_set.version
        )

        services_mock.boot_resource_sets = Mock(BootResourceSetsService)
        services_mock.boot_resource_sets.create.return_value = (
            test_boot_resource_set
        )

        services_mock.boot_resource_files = Mock(BootResourceFilesService)
        services_mock.boot_resource_files.calculate_filename_on_disk.return_value = file_name

        async_local_file_mock.return_value = AsyncContextManagerMock(
            MockTemporaryFile()
        )

        headers = {
            "name": "my-image",
            "sha256": factory.make_hex_string(size=16),
            "architecture": "amd64/generic",
            "Content-Type": "application/octet-stream",
        }

        raw_data = file_data.read()
        response = await client.post(
            url=f"{self.BASE_PATH}",
            headers=headers,
            content=raw_data,
        )

        assert response.status_code == 400

        error_response = ErrorBodyResponse(**response.json())

        assert error_response.code == 400
        assert error_response.kind == "Error"
        assert (
            error_response.details[0].type == INVALID_ARGUMENT_VIOLATION_TYPE  # pyright: ignore[reportOptionalSubscript]
        )
        assert "SHA256" in error_response.details[0].message  # pyright: ignore[reportOptionalSubscript]

    @patch("maasservicelayer.utils.image_local_files.aiofiles.os.statvfs")
    @patch(
        "maasapiserver.v3.api.public.handlers.boot_resources.BootResourceCreateRequest.to_builder"
    )
    async def test_upload_custom_image_507_insufficient_disk_space(
        self,
        request_to_builder_mock: MagicMock,
        statvfs_mock: MagicMock,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
        test_boot_resource_1: BootResource,
        test_boot_resource_set: BootResourceSet,
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_BOOT_ENTITIES,
        )
        request_to_builder_mock.return_value = None

        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.create.return_value = test_boot_resource_1
        services_mock.boot_resources.get_next_version_name.return_value = (
            test_boot_resource_set.version
        )

        services_mock.boot_resource_sets = Mock(BootResourceSetsService)
        services_mock.boot_resource_sets.create.return_value = (
            test_boot_resource_set
        )

        services_mock.boot_resource_files = Mock(BootResourceFilesService)
        services_mock.boot_resource_files.calculate_filename_on_disk.return_value = "file.bin"

        statvfs_result = Mock()
        statvfs_result.f_bavail = 0
        statvfs_result.f_frsize = 4096
        statvfs_mock.return_value = statvfs_result

        content = b"a" * 100

        headers = {
            "name": "my-image",
            "sha256": str(hashlib.sha256(content).hexdigest()),
            "architecture": "amd64/generic",
            "Content-Type": "application/octet-stream",
        }

        response = await client.post(
            url=f"{self.BASE_PATH}",
            headers=headers,
            content=content,
        )

        assert response.status_code == 507

        error_response = ErrorBodyResponse(**response.json())

        assert error_response.code == 507
        assert error_response.kind == "Error"

    @patch(
        "maasapiserver.v3.api.public.handlers.boot_resources.validate_boot_asset_name",
        new_callable=AsyncMock,
    )
    @patch("maasapiserver.v3.api.public.handlers.boot_resources.MAAS_ID")
    @patch(
        "maasapiserver.v3.api.public.handlers.boot_resources.AsyncLocalBootResourceFile"
    )
    async def test_upload_bootloader(
        self,
        async_local_file_mock: MagicMock,
        maas_id_mock: MagicMock,
        validate_name_mock: AsyncMock,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
        test_bootloader_resource: BootResource,
        test_boot_resource_set: BootResourceSet,
    ) -> None:
        validate_name_mock.return_value = test_bootloader_resource.name
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_BOOT_ENTITIES,
        )
        file_content = b"bootloader archive"
        fake_filename_on_disk = "ab/cdef1234"

        # Mock the store context manager so no real disk I/O happens.
        store_mock = MagicMock()
        store_mock.__aenter__ = AsyncMock(
            return_value=MagicMock(write=AsyncMock())
        )
        store_mock.__aexit__ = AsyncMock(return_value=False)
        async_local_file_mock.return_value.store.return_value = store_mock

        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_usable_architectures.return_value = [
            test_bootloader_resource.architecture
        ]
        services_mock.boot_resources.upload_bootloader.return_value = (
            test_bootloader_resource,
            test_boot_resource_set.version,
        )

        services_mock.boot_resource_sets = Mock(BootResourceSetsService)
        services_mock.boot_resource_sets.get_one.return_value = (
            test_boot_resource_set
        )

        bootloader_files = [
            BootResourceFile(
                id=2,
                created=utcnow(),
                updated=utcnow(),
                filename="grubx64.efi",
                filetype=BootResourceFileType.ARCHIVE_TAR_XZ,
                extra={},
                sha256="a" * 64,
                size=1024,
                filename_on_disk="1/grubx64.efi",
                resource_set_id=test_boot_resource_set.id,
            )
        ]
        services_mock.boot_resource_files = Mock(BootResourceFilesService)
        services_mock.boot_resource_files.calculate_filename_on_disk = (
            AsyncMock(return_value=fake_filename_on_disk)
        )
        services_mock.boot_resource_files.get_files_in_resource_set.return_value = bootloader_files

        maas_id_mock.get.return_value = "abc1de"

        node_mock = Mock(Node)
        node_mock.id = 1

        services_mock.nodes = Mock(NodesService)
        services_mock.nodes.get_one.return_value = node_mock

        services_mock.boot_resource_file_sync = Mock(
            BootResourceFileSyncService
        )
        services_mock.boot_resource_file_sync.get_or_create.return_value = (
            None,
            True,
        )

        services_mock.temporal = Mock(TemporalService)
        services_mock.temporal.register_or_update_workflow_call.return_value = None

        file_content = b"bootloader tarball bytes"

        response = await client.post(
            f"{V3_API_PREFIX}/boot_assets/bootloaders",
            content=file_content,
            headers={
                "Content-Type": "application/octet-stream",
                "x-name": test_bootloader_resource.name,
                "x-architecture": test_bootloader_resource.architecture,
                "x-sha256": "b" * 64,
                "x-primary-file": "grubx64.efi",
            },
        )

        assert response.status_code == 201
        upload_response = BootAssetUploadResponse(**response.json())
        assert upload_response.id == test_bootloader_resource.id
        assert upload_response.version == test_boot_resource_set.version
        assert upload_response.bootloader_type == "uefi"
        assert len(upload_response.files) == 1
        assert upload_response.files[0].filename == "grubx64.efi"

        services_mock.boot_resources.upload_bootloader.assert_awaited_once_with(
            name=test_bootloader_resource.name,
            architecture=test_bootloader_resource.architecture,
            sha256="b" * 64,
            primary_file="grubx64.efi",
            filename_on_disk=fake_filename_on_disk,
            size=len(file_content),
        )

        services_mock.boot_resource_file_sync.get_or_create.assert_called_once()
        services_mock.temporal.register_or_update_workflow_call.assert_called_once_with(
            SYNC_BOOTRESOURCES_WORKFLOW_NAME,
            SyncRequestParam(
                resource=ResourceDownloadParam(
                    rfile_ids=[bootloader_files[0].id],
                    source_list=[],
                    sha256=bootloader_files[0].sha256,
                    filename_on_disk=bootloader_files[0].filename_on_disk,
                    total_size=bootloader_files[0].size,
                ),
            ),
            workflow_id=f"sync-bootresources:{short_sha(bootloader_files[0].sha256)}",
            wait=False,
        )

    async def test_upload_bootloader_permission_denied(
        self,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
        test_bootloader_resource: BootResource,
    ) -> None:
        client = mocked_api_client_user_with_permissions()

        response = await client.post(
            f"{V3_API_PREFIX}/boot_assets/bootloaders",
            content=b"archive",
            headers={
                "Content-Type": "application/octet-stream",
                "x-name": test_bootloader_resource.name,
                "x-architecture": test_bootloader_resource.architecture,
                "x-sha256": "b" * 64,
            },
        )

        assert response.status_code == 403

    @patch(
        "maasapiserver.v3.api.public.handlers.boot_resources.validate_boot_asset_name",
        new_callable=AsyncMock,
    )
    async def test_upload_bootloader_invalid_architecture(
        self,
        validate_name_mock: AsyncMock,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
        test_bootloader_resource: BootResource,
    ) -> None:
        validate_name_mock.return_value = test_bootloader_resource.name
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_BOOT_ENTITIES,
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_usable_architectures.return_value = [
            "amd64/generic"
        ]

        response = await client.post(
            f"{V3_API_PREFIX}/boot_assets/bootloaders",
            content=b"archive",
            headers={
                "Content-Type": "application/octet-stream",
                "x-name": test_bootloader_resource.name,
                "x-architecture": "not/a/valid/arch",
                "x-sha256": "b" * 64,
                "x-primary-file": "shimx64.efi",
            },
        )

        assert response.status_code == 422
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.details[0].field == "architecture"  # pyright: ignore[reportOptionalSubscript]

    @patch(
        "maasapiserver.v3.api.public.handlers.boot_resources.validate_boot_asset_name",
        new_callable=AsyncMock,
    )
    @patch("maasapiserver.v3.api.public.handlers.boot_resources.MAAS_ID")
    @patch(
        "maasapiserver.v3.api.public.handlers.boot_resources.AsyncLocalBootResourceFile"
    )
    async def test_upload_kernel(
        self,
        async_local_file_mock: MagicMock,
        maas_id_mock: MagicMock,
        validate_name_mock: AsyncMock,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
        test_kernel_resource: BootResource,
        test_boot_resource_set: BootResourceSet,
    ) -> None:
        validate_name_mock.return_value = test_kernel_resource.name
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_BOOT_ENTITIES,
        )
        kernel_content = b"kernel-bytes"
        kernel_fod = "aa/kernel"

        # Mock the store context manager so no real disk I/O happens.
        store_mock = MagicMock()
        store_mock.__aenter__ = AsyncMock(
            return_value=MagicMock(write=AsyncMock())
        )
        store_mock.__aexit__ = AsyncMock(return_value=False)
        async_local_file_mock.return_value.store.return_value = store_mock

        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_usable_architectures.return_value = [
            test_kernel_resource.architecture
        ]
        services_mock.boot_resources.upload_kernel.return_value = (
            test_kernel_resource,
            test_boot_resource_set.version,
        )

        services_mock.boot_resource_sets = Mock(BootResourceSetsService)
        services_mock.boot_resource_sets.get_one.return_value = (
            test_boot_resource_set
        )

        kernel_files = [
            BootResourceFile(
                id=3,
                created=utcnow(),
                updated=utcnow(),
                filename="kernel",
                filetype=BootResourceFileType.BOOT_KERNEL,
                extra={},
                sha256="c" * 64,
                size=len(kernel_content),
                filename_on_disk="1/kernel",
                resource_set_id=test_boot_resource_set.id,
            ),
        ]
        services_mock.boot_resource_files = Mock(BootResourceFilesService)
        services_mock.boot_resource_files.calculate_filename_on_disk = (
            AsyncMock(return_value=kernel_fod)
        )
        services_mock.boot_resource_files.get_files_in_resource_set.return_value = kernel_files

        maas_id_mock.get.return_value = "abc1de"

        node_mock = Mock(Node)
        node_mock.id = 1

        services_mock.nodes = Mock(NodesService)
        services_mock.nodes.get_one.return_value = node_mock

        services_mock.boot_resource_file_sync = Mock(
            BootResourceFileSyncService
        )
        services_mock.boot_resource_file_sync.get_or_create.return_value = (
            None,
            True,
        )

        services_mock.temporal = Mock(TemporalService)
        services_mock.temporal.register_or_update_workflow_call.return_value = None

        response = await client.post(
            f"{V3_API_PREFIX}/boot_assets/kernels",
            content=kernel_content,
            headers={
                "Content-Type": "application/octet-stream",
                "x-name": test_kernel_resource.name,
                "x-architecture": test_kernel_resource.architecture,
                "x-kflavor": "generic",
                "x-sha256": "e" * 64,
            },
        )

        assert response.status_code == 201
        upload_response = BootAssetUploadResponse(**response.json())
        assert upload_response.id == test_kernel_resource.id
        assert upload_response.version == test_boot_resource_set.version
        assert upload_response.kflavor == test_kernel_resource.kflavor
        assert len(upload_response.files) == 1

        services_mock.boot_resources.upload_kernel.assert_awaited_once_with(
            name=test_kernel_resource.name,
            architecture=test_kernel_resource.architecture,
            kflavor="generic",
            sha256="e" * 64,
            filename_on_disk=kernel_fod,
            size=len(kernel_content),
        )

        services_mock.boot_resource_file_sync.get_or_create.assert_called_once()
        services_mock.temporal.register_or_update_workflow_call.assert_called_once_with(
            SYNC_BOOTRESOURCES_WORKFLOW_NAME,
            SyncRequestParam(
                resource=ResourceDownloadParam(
                    rfile_ids=[kernel_files[0].id],
                    source_list=[],
                    sha256=kernel_files[0].sha256,
                    filename_on_disk=kernel_files[0].filename_on_disk,
                    total_size=kernel_files[0].size,
                ),
            ),
            workflow_id=f"sync-bootresources:{short_sha(kernel_files[0].sha256)}",
            wait=False,
        )

    @patch("maasapiserver.v3.api.public.handlers.boot_resources.MAAS_ID")
    @patch(
        "maasapiserver.v3.api.public.handlers.boot_resources.AsyncLocalBootResourceFile"
    )
    async def test_upload_kernel_initrd(
        self,
        async_local_file_mock: MagicMock,
        maas_id_mock: MagicMock,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
        test_kernel_resource: BootResource,
        test_boot_resource_set: BootResourceSet,
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_BOOT_ENTITIES,
        )
        resource_id = test_kernel_resource.id
        initrd_content = b"initrd-bytes"
        initrd_fod = "bb/initrd"

        # Mock the store context manager so no real disk I/O happens.
        store_mock = MagicMock()
        store_mock.__aenter__ = AsyncMock(
            return_value=MagicMock(write=AsyncMock())
        )
        store_mock.__aexit__ = AsyncMock(return_value=False)
        async_local_file_mock.return_value.store.return_value = store_mock

        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.upload_kernel_initrd.return_value = (
            test_kernel_resource,
            test_boot_resource_set.version,
        )

        services_mock.boot_resource_sets = Mock(BootResourceSetsService)
        services_mock.boot_resource_sets.get_one.return_value = (
            test_boot_resource_set
        )

        initrd_files = [
            BootResourceFile(
                id=4,
                created=utcnow(),
                updated=utcnow(),
                filename="initrd",
                filetype=BootResourceFileType.BOOT_INITRD,
                extra={},
                sha256="d" * 64,
                size=len(initrd_content),
                filename_on_disk="1/initrd",
                resource_set_id=test_boot_resource_set.id,
            ),
        ]
        services_mock.boot_resource_files = Mock(BootResourceFilesService)
        services_mock.boot_resource_files.calculate_filename_on_disk = (
            AsyncMock(return_value=initrd_fod)
        )
        services_mock.boot_resource_files.get_files_in_resource_set.return_value = initrd_files

        maas_id_mock.get.return_value = "abc1de"

        node_mock = Mock(Node)
        node_mock.id = 1

        services_mock.nodes = Mock(NodesService)
        services_mock.nodes.get_one.return_value = node_mock

        services_mock.boot_resource_file_sync = Mock(
            BootResourceFileSyncService
        )
        services_mock.boot_resource_file_sync.get_or_create.return_value = (
            None,
            True,
        )

        services_mock.temporal = Mock(TemporalService)
        services_mock.temporal.register_or_update_workflow_call.return_value = None

        response = await client.post(
            f"{V3_API_PREFIX}/boot_assets/kernels/{resource_id}/initrd",
            content=initrd_content,
            headers={
                "Content-Type": "application/octet-stream",
                "x-sha256": "f" * 64,
            },
        )

        assert response.status_code == 201
        upload_response = BootAssetUploadResponse(**response.json())
        assert upload_response.id == test_kernel_resource.id

        services_mock.boot_resources.upload_kernel_initrd.assert_awaited_once_with(
            resource_id=resource_id,
            sha256="f" * 64,
            filename_on_disk=initrd_fod,
            size=len(initrd_content),
        )

        # Missing x-sha256 should return 400.
        response_no_sha = await client.post(
            f"{V3_API_PREFIX}/boot_assets/kernels/{resource_id}/initrd",
            content=initrd_content,
            headers={"Content-Type": "application/octet-stream"},
        )
        assert response_no_sha.status_code == 400

    async def test_upload_kernel_permission_denied(
        self,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
        test_kernel_resource: BootResource,
    ) -> None:
        client = mocked_api_client_user_with_permissions()

        response = await client.post(
            f"{V3_API_PREFIX}/boot_assets/kernels",
            content=b"kernel-bytes",
            headers={
                "Content-Type": "application/octet-stream",
                "x-name": test_kernel_resource.name,
                "x-architecture": test_kernel_resource.architecture,
                "x-kflavor": "generic",
                "x-sha256": "e" * 64,
            },
        )

        assert response.status_code == 403

    @patch(
        "maasapiserver.v3.api.public.handlers.boot_resources.validate_boot_asset_name",
        new_callable=AsyncMock,
    )
    async def test_upload_kernel_invalid_architecture(
        self,
        validate_name_mock: AsyncMock,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
        test_kernel_resource: BootResource,
    ) -> None:
        validate_name_mock.return_value = test_kernel_resource.name
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_BOOT_ENTITIES,
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_usable_architectures.return_value = [
            "amd64/generic"
        ]

        response = await client.post(
            f"{V3_API_PREFIX}/boot_assets/kernels",
            content=b"kernel-bytes",
            headers={
                "Content-Type": "application/octet-stream",
                "x-name": test_kernel_resource.name,
                "x-architecture": "not/a/valid/arch",
                "x-kflavor": "generic",
                "x-sha256": "e" * 64,
            },
        )

        assert response.status_code == 422
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.details[0].field == "architecture"  # pyright: ignore[reportOptionalSubscript]

    async def test_list_custom_images_filters_by_kernel_type(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
        test_kernel_resource: BootResource,
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.list.return_value = ListResult[
            BootResource
        ](items=[test_kernel_resource], total=1)

        response = await client.get(f"{self.BASE_PATH}?size=10&type=kernel")

        assert response.status_code == 200
        boot_resources_response = ImageListResponse(**response.json())
        assert [item.id for item in boot_resources_response.items] == [
            test_kernel_resource.id
        ]
        services_mock.boot_resources.list.assert_awaited_once_with(
            page=1,
            size=10,
            query=QuerySpec(
                where=BootResourceClauseFactory.with_asset_type_kernel()
            ),
        )

    async def test_list_custom_images_filters_by_image_type(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
        test_boot_resource_1: BootResource,
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.list.return_value = ListResult[
            BootResource
        ](items=[test_boot_resource_1], total=1)

        response = await client.get(f"{self.BASE_PATH}?size=10&type=image")

        assert response.status_code == 200
        boot_resources_response = ImageListResponse(**response.json())
        assert [item.id for item in boot_resources_response.items] == [
            test_boot_resource_1.id
        ]
        services_mock.boot_resources.list.assert_awaited_once_with(
            page=1,
            size=10,
            query=QuerySpec(
                where=BootResourceClauseFactory.with_asset_type_image()
            ),
        )

    async def test_list_custom_images_invalid_type_returns_422(
        self,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
        )

        response = await client.get(f"{self.BASE_PATH}?type=invalid")

        assert response.status_code == 422
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.code == 422

    async def test_list_custom_images_200_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
        test_boot_resource_1: BootResource,
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.list.return_value = ListResult[
            BootResource
        ](items=[test_boot_resource_1], total=1)

        response = await client.get(f"{self.BASE_PATH}?size=1")

        assert response.status_code == 200

        boot_sources_response = ImageListResponse(**response.json())

        assert len(boot_sources_response.items) == 1
        assert boot_sources_response.total == 1
        assert boot_sources_response.next is None
        services_mock.boot_resources.list.assert_awaited_once_with(
            page=1,
            size=1,
            query=QuerySpec(
                where=BootResourceClauseFactory.with_uploaded_type()
            ),
        )

    async def test_list_custom_images_200_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
        test_boot_resource_1: BootResource,
        test_boot_resource_2: BootResource,
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.list.return_value = ListResult[
            BootResource
        ](items=[test_boot_resource_1, test_boot_resource_2], total=2)

        response = await client.get(f"{self.BASE_PATH}?size=1")

        assert response.status_code == 200

        boot_resources_response = ImageListResponse(**response.json())

        assert len(boot_resources_response.items) == 2
        assert boot_resources_response.total == 2
        assert (
            boot_resources_response.next == f"{self.BASE_PATH}?page=2&size=1"
        )

    async def test_list_custom_images_filters_by_type(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
        test_bootloader_resource: BootResource,
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.list.return_value = ListResult[
            BootResource
        ](items=[test_bootloader_resource], total=2)

        response = await client.get(f"{self.BASE_PATH}?size=1&type=bootloader")

        assert response.status_code == 200
        boot_resources_response = ImageListResponse(**response.json())
        assert len(boot_resources_response.items) == 1
        assert boot_resources_response.total == 2
        assert (
            boot_resources_response.next
            == f"{self.BASE_PATH}?page=2&size=1&type=bootloader"
        )
        services_mock.boot_resources.list.assert_awaited_once_with(
            page=1,
            size=1,
            query=QuerySpec(
                where=BootResourceClauseFactory.with_asset_type_bootloader()
            ),
        )

    async def test_get_custom_image_by_id_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
        test_boot_resource_1: BootResource,
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_one.return_value = (
            test_boot_resource_1
        )

        response = await client.get(f"{self.BASE_PATH}/1")

        assert response.status_code == 200
        assert "ETag" in response.headers

        boot_resource_response = ImageResponse(**response.json())

        assert boot_resource_response.id == 1

    async def test_get_custom_image_by_id_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_one.return_value = None

        response = await client.get(f"{self.BASE_PATH}/3")

        assert response.status_code == 404
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404

    async def test_delete_custom_images_204(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
        test_boot_resource_2: BootResource,
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_BOOT_ENTITIES,
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.delete_one.return_value = (
            test_boot_resource_2
        )

        response = await client.delete(f"{self.BASE_PATH}/1")

        assert response.status_code == 204

        services_mock.boot_resources.delete_one.assert_called_once_with(
            query=QuerySpec(
                where=BootResourceClauseFactory.and_clauses(
                    [
                        BootResourceClauseFactory.with_id(1),
                        BootResourceClauseFactory.with_rtype(
                            BootResourceType.UPLOADED
                        ),
                    ]
                )
            ),
            etag_if_match=None,
        )

    async def test_delete_custom_images_204_by_etag(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
        test_boot_resource_2: BootResource,
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_BOOT_ENTITIES,
        )
        correct_etag = "correct_etag"

        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.delete_one.return_value = (
            test_boot_resource_2
        )

        response = await client.delete(
            f"{self.BASE_PATH}/1",
            headers={"if-match": correct_etag},
        )

        assert response.status_code == 204

        services_mock.boot_resources.delete_one.assert_called_once_with(
            query=QuerySpec(
                where=BootResourceClauseFactory.and_clauses(
                    [
                        BootResourceClauseFactory.with_id(1),
                        BootResourceClauseFactory.with_rtype(
                            BootResourceType.UPLOADED
                        ),
                    ]
                )
            ),
            etag_if_match=correct_etag,
        )

    async def test_delete_custom_images_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
        test_boot_resource_2: BootResource,
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_BOOT_ENTITIES,
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.delete_one.side_effect = (
            NotFoundException()
        )

        response = await client.delete(f"{self.BASE_PATH}/2")

        assert response.status_code == 404
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())

        assert error_response.kind == "Error"
        assert error_response.code == 404

        services_mock.boot_resources.delete_one.assert_called_once_with(
            query=QuerySpec(
                where=BootResourceClauseFactory.and_clauses(
                    [
                        BootResourceClauseFactory.with_id(2),
                        BootResourceClauseFactory.with_rtype(
                            BootResourceType.UPLOADED
                        ),
                    ]
                )
            ),
            etag_if_match=None,
        )

    async def test_delete_custom_images_412_wrong_etag(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_BOOT_ENTITIES,
        )
        wrong_etag = "wrong_etag"
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.delete_one.side_effect = PreconditionFailedException(
            details=[
                BaseExceptionDetail(
                    type=ETAG_PRECONDITION_VIOLATION_TYPE,
                    message=f"The resource etag '{wrong_etag}' did not match 'my_etag'.",
                )
            ]
        )

        response = await client.delete(
            f"{self.BASE_PATH}/2",
            headers={"if-match": wrong_etag},
        )

        assert response.status_code == 412

        error_response = ErrorBodyResponse(**response.json())

        assert error_response.code == 412
        assert error_response.message == "A precondition has failed."
        assert (
            error_response.details[0].type == ETAG_PRECONDITION_VIOLATION_TYPE  # pyright: ignore[reportOptionalSubscript]
        )

        services_mock.boot_resources.delete_one.assert_called_once_with(
            query=QuerySpec(
                where=BootResourceClauseFactory.and_clauses(
                    [
                        BootResourceClauseFactory.with_id(2),
                        BootResourceClauseFactory.with_rtype(
                            BootResourceType.UPLOADED
                        ),
                    ]
                )
            ),
            etag_if_match=wrong_etag,
        )

    async def test_bulk_delete_custom_images(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_BOOT_ENTITIES,
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.delete_many.return_value = None

        response = await client.delete(f"{self.BASE_PATH}?id=1&id=2")
        assert response.status_code == 204
        services_mock.boot_resources.delete_many.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceClauseFactory.and_clauses(
                    [
                        BootResourceClauseFactory.with_ids([1, 2]),
                        BootResourceClauseFactory.with_rtype(
                            BootResourceType.UPLOADED
                        ),
                    ]
                )
            )
        )


class TestCustomImageStatusApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/custom_images/statuses"

    @pytest.fixture
    def endpoints_with_authorization(self) -> list[Endpoint]:
        return [
            Endpoint(
                method="GET",
                path=self.BASE_PATH,
                permission=MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
            ),
            Endpoint(
                method="GET",
                path=f"{self.BASE_PATH}/1",
                permission=MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
            ),
        ]

    async def test_list_custom_images_status_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.list_custom_images_status.return_value = (
            ListResult[CustomBootResourceStatus](
                items=[
                    CustomBootResourceStatus(
                        id=1,
                        sync_percentage=100.0,
                        status=ImageStatus.READY,
                    )
                ],
                total=2,
            )
        )

        response = await client.get(f"{self.BASE_PATH}?size=1")

        assert response.status_code == 200

        custom_images_status_response = ImageStatusListResponse(
            **response.json()
        )

        assert custom_images_status_response.total == 2
        assert len(custom_images_status_response.items) == 1
        assert (
            custom_images_status_response.next
            == f"{self.BASE_PATH}?page=2&size=1"
        )

    async def test_list_custom_images_status_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.list_custom_images_status.return_value = (
            ListResult[CustomBootResourceStatus](
                items=[
                    CustomBootResourceStatus(
                        id=1,
                        sync_percentage=100.0,
                        status=ImageStatus.READY,
                    )
                ],
                total=1,
            )
        )

        response = await client.get(f"{self.BASE_PATH}?size=1")

        assert response.status_code == 200

        custom_images_status_response = ImageStatusListResponse(
            **response.json()
        )

        assert custom_images_status_response.total == 1
        assert len(custom_images_status_response.items) == 1
        assert custom_images_status_response.next is None


class TestCustomImageStatisticsApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/custom_images/statistics"

    @pytest.fixture
    def endpoints_with_authorization(self) -> list[Endpoint]:
        return [
            Endpoint(
                method="GET",
                path=self.BASE_PATH,
                permission=MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
            ),
            Endpoint(
                method="GET",
                path=f"{self.BASE_PATH}/1",
                permission=MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
            ),
        ]

    async def test_list_custom_images_statistics_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.list_custom_images_statistics.return_value = ListResult[
            CustomBootResourceStatistic
        ](
            items=[
                CustomBootResourceStatistic(
                    id=1,
                    last_updated=utcnow(),
                    last_deployed=None,
                    size=1024,
                    deploy_to_memory=True,
                    node_count=2,
                )
            ],
            total=2,
        )

        response = await client.get(f"{self.BASE_PATH}?size=1")

        assert response.status_code == 200

        custom_images_statistics_response = ImageStatisticListResponse(
            **response.json()
        )

        assert custom_images_statistics_response.total == 2
        assert len(custom_images_statistics_response.items) == 1
        assert (
            custom_images_statistics_response.next
            == f"{self.BASE_PATH}?page=2&size=1"
        )

    async def test_list_custom_images_statistics_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.list_custom_images_statistics.return_value = ListResult[
            CustomBootResourceStatistic
        ](
            items=[
                CustomBootResourceStatistic(
                    id=1,
                    last_updated=utcnow(),
                    last_deployed=None,
                    size=1024,
                    deploy_to_memory=True,
                    node_count=2,
                )
            ],
            total=1,
        )

        response = await client.get(f"{self.BASE_PATH}?size=1")

        assert response.status_code == 200

        custom_images_statistics_response = ImageStatisticListResponse(
            **response.json()
        )

        assert custom_images_statistics_response.total == 1
        assert len(custom_images_statistics_response.items) == 1
        assert custom_images_statistics_response.next is None

    async def test_list_custom_images_statistics_filters(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.list_custom_images_statistics.return_value = ListResult[
            CustomBootResourceStatistic
        ](
            items=[
                CustomBootResourceStatistic(
                    id=1,
                    last_updated=utcnow(),
                    last_deployed=None,
                    size=1024,
                    deploy_to_memory=True,
                    node_count=2,
                )
            ],
            total=2,
        )

        response = await client.get(f"{self.BASE_PATH}?size=1&id=1&id=2")
        assert response.status_code == 200

        custom_images_statistics_response = ImageStatisticListResponse(
            **response.json()
        )

        assert custom_images_statistics_response.total == 2
        assert len(custom_images_statistics_response.items) == 1
        assert custom_images_statistics_response.next is not None
        assert (
            custom_images_statistics_response.next
            == f"{self.BASE_PATH}?page=2&size=1&id=1&id=2"
        )

    async def test_get_custom_image_statistic_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_custom_image_statistic_by_id.return_value = CustomBootResourceStatistic(
            id=1,
            last_updated=utcnow(),
            last_deployed=None,
            size=1024,
            deploy_to_memory=True,
            node_count=2,
        )

        response = await client.get(f"{self.BASE_PATH}/1")

        assert response.status_code == 200
        stat_response = ImageStatisticResponse(**response.json())
        assert stat_response.id == 1

    async def test_get_custom_image_statistic_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_custom_image_statistic_by_id.return_value = None

        response = await client.get(f"{self.BASE_PATH}/1")

        assert response.status_code == 404
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404


class TestONIEImageUpload(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/custom_images"

    @pytest.fixture
    def endpoints_with_authorization(self) -> list[Endpoint]:
        return [
            Endpoint(
                method="POST",
                path=self.BASE_PATH,
                permission=MAASResourceEntitlement.CAN_EDIT_BOOT_ENTITIES,
            ),
        ]

    @staticmethod
    def create_onie_installer_binary(size_in_bytes: int = 1024) -> bytes:
        return b"ONIE_INSTALLER_MOCK_DATA" * (size_in_bytes // 24)

    @patch(
        "maasservicelayer.utils.image_local_files.AsyncLocalBootResourceFile"
    )
    @patch("maasapiserver.v3.api.public.handlers.boot_resources.MAAS_ID")
    @patch(
        "maasapiserver.v3.api.public.handlers.boot_resources.BootResourceCreateRequest.to_builder"
    )
    async def test_upload_onie_image_success(
        self,
        to_builder_mock: MagicMock,
        maas_id_mock: MagicMock,
        async_file_mock: MagicMock,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_BOOT_ENTITIES,
        )
        file_data = self.create_onie_installer_binary(size_in_bytes=102400)
        sha256_hash = hashlib.sha256(file_data).hexdigest()

        onie_boot_resource = BootResource(
            id=1,
            rtype=BootResourceType.UPLOADED,
            name="onie/mellanox-3.8.0",
            architecture="amd64/generic",
            extra={"title": "Mellanox ONIE 3.8.0", "subarches": "generic"},
            rolling=False,
            base_image="",
        )

        to_builder_mock.return_value = BootResourceBuilder(
            name="onie/mellanox-3.8.0",
            architecture="amd64/generic",
            base_image="",
            rtype=BootResourceType.UPLOADED,
            extra={"title": "Mellanox ONIE 3.8.0", "subarches": "generic"},
            alias="",
            bootloader_type=None,
            kflavor=None,
            rolling=False,
            last_deployed=None,
            created=utcnow(),
            updated=utcnow(),
        )

        services_mock.boot_resources = Mock(BootResourceService)
        resource_file_mock = Mock(
            id=1,
            sha256=sha256_hash,
            size=len(file_data),
            filename_on_disk="test.bin",
        )
        services_mock.boot_resources.upload_custom_image.return_value = (
            onie_boot_resource,
            resource_file_mock,
        )

        services_mock.boot_resource_files = Mock(BootResourceFilesService)
        services_mock.boot_resource_files.calculate_filename_on_disk.return_value = "test.bin"

        services_mock.boot_resource_file_sync = Mock(
            BootResourceFileSyncService
        )
        services_mock.boot_resource_file_sync.get_or_create.return_value = (
            Mock(),
            True,
        )

        services_mock.temporal = Mock(TemporalService)
        services_mock.temporal.register_or_update_workflow_call.return_value = None

        services_mock.nodes = Mock(NodesService)
        services_mock.nodes.get_one.return_value = Node(
            id=1,
            system_id="test-region",
            hostname="test-region",
            status=NodeStatus.NEW,
            node_type=NodeTypeEnum.REGION_CONTROLLER,
            power_state=PowerState.UNKNOWN,
            power_state_updated=None,
        )

        async_file_mock.return_value = AsyncContextManagerMock(
            MockTemporaryFile()
        )
        maas_id_mock.get.return_value = "test-region"

        headers = {
            "name": "onie/mellanox-3.8.0",
            "sha256": sha256_hash,
            "architecture": "amd64/generic",
            "file_type": "tgz",
            "title": "Mellanox ONIE 3.8.0",
            "Content-Type": "application/octet-stream",
        }

        response = await client.post(
            self.BASE_PATH,
            headers=headers,
            content=file_data,
        )

        assert response.status_code == 201
        image = ImageResponse(**response.json())
        assert image.os == "onie"
        assert image.release == "mellanox-3.8.0"
        assert image.title == "Mellanox ONIE 3.8.0"
        assert image.architecture == "amd64"

    @patch(
        "maasservicelayer.utils.image_local_files.AsyncLocalBootResourceFile"
    )
    @patch("maasapiserver.v3.api.public.handlers.boot_resources.MAAS_ID")
    @patch(
        "maasapiserver.v3.api.public.handlers.boot_resources.BootResourceCreateRequest.to_builder"
    )
    async def test_upload_onie_image_invalid_name(
        self,
        to_builder_mock: MagicMock,
        maas_id_mock: MagicMock,
        async_file_mock: MagicMock,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_BOOT_ENTITIES,
        )
        file_data = self.create_onie_installer_binary(size_in_bytes=1024)
        sha256_hash = hashlib.sha256(file_data).hexdigest()

        services_mock.boot_source_cache = Mock(BootSourceCacheService)
        services_mock.boot_source_cache.get_unique_os_releases.return_value = []
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_usable_architectures.return_value = [
            "amd64/generic"
        ]

        to_builder_mock.side_effect = ValidationException.build_for_field(
            field="name",
            message="Invalid ONIE image name format",
            location="header",
        )

        headers = {
            "name": "onie/invalid_format",
            "sha256": sha256_hash,
            "architecture": "amd64/generic",
            "Content-Type": "application/octet-stream",
        }

        response = await client.post(
            self.BASE_PATH,
            headers=headers,
            content=file_data,
        )

        assert response.status_code == 422
        error_response = ErrorBodyResponse(**response.json())
        assert "name" in str(error_response.details[0].field)

    @patch(
        "maasservicelayer.utils.image_local_files.AsyncLocalBootResourceFile"
    )
    @patch("maasapiserver.v3.api.public.handlers.boot_resources.MAAS_ID")
    @patch(
        "maasapiserver.v3.api.public.handlers.boot_resources.BootResourceCreateRequest.to_builder"
    )
    async def test_upload_onie_image_with_self_extracting_type(
        self,
        to_builder_mock: MagicMock,
        maas_id_mock: MagicMock,
        async_file_mock: MagicMock,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        """Test uploading an ONIE image with self-extracting file type."""
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_BOOT_ENTITIES,
        )

        file_data = self.create_onie_installer_binary(size_in_bytes=102400)
        sha256_hash = hashlib.sha256(file_data).hexdigest()

        onie_boot_resource = BootResource(
            id=1,
            rtype=BootResourceType.UPLOADED,
            name="onie/mellanox-3.8.0",
            architecture="amd64/generic",
            extra={"title": "Mellanox ONIE 3.8.0", "subarches": "generic"},
            rolling=False,
            base_image="",
        )

        to_builder_mock.return_value = BootResourceBuilder(
            name="onie/mellanox-3.8.0",
            architecture="amd64/generic",
            base_image="",
            rtype=BootResourceType.UPLOADED,
            extra={"title": "Mellanox ONIE 3.8.0", "subarches": "generic"},
            alias="",
            bootloader_type=None,
            kflavor=None,
            rolling=False,
            last_deployed=None,
            created=utcnow(),
            updated=utcnow(),
        )

        services_mock.boot_resources = Mock(BootResourceService)
        resource_file_mock = Mock(
            id=1,
            sha256=sha256_hash,
            size=len(file_data),
            filename_on_disk="test.bin",
            filetype=BootResourceFileType.SELF_EXTRACTING,
            filename="installer.bin",
        )
        services_mock.boot_resources.upload_custom_image.return_value = (
            onie_boot_resource,
            resource_file_mock,
        )

        services_mock.boot_resource_files = Mock(BootResourceFilesService)
        services_mock.boot_resource_files.calculate_filename_on_disk.return_value = "test.bin"

        services_mock.boot_resource_file_sync = Mock(
            BootResourceFileSyncService
        )
        services_mock.boot_resource_file_sync.get_or_create.return_value = (
            Mock(),
            True,
        )

        services_mock.temporal = Mock(TemporalService)
        services_mock.temporal.register_or_update_workflow_call.return_value = None

        services_mock.nodes = Mock(NodesService)
        services_mock.nodes.get_one.return_value = Node(
            id=1,
            system_id="test-region",
            hostname="test-region",
            status=NodeStatus.NEW,
            node_type=NodeTypeEnum.REGION_CONTROLLER,
            power_state=PowerState.UNKNOWN,
            power_state_updated=None,
        )

        async_file_mock.return_value = AsyncContextManagerMock(
            MockTemporaryFile()
        )
        maas_id_mock.get.return_value = "test-region"

        headers = {
            "name": "onie/mellanox-3.8.0",
            "sha256": sha256_hash,
            "architecture": "amd64/generic",
            "file-type": "self-extracting",
            "Content-Type": "application/octet-stream",
        }

        response = await client.post(
            self.BASE_PATH,
            headers=headers,
            content=file_data,
        )

        assert response.status_code == 201
        call_kwargs = (
            services_mock.boot_resources.upload_custom_image.call_args[1]
        )
        assert call_kwargs["filetype"] == BootResourceFileType.SELF_EXTRACTING
        assert call_kwargs["filename"] == "installer.bin"


class TestBootloadersApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/bootloaders"

    @pytest.fixture
    def endpoints_with_authorization(self) -> list[Endpoint]:
        return [
            Endpoint(
                method="GET",
                path=self.BASE_PATH,
                permission=MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
            ),
            Endpoint(
                method="GET",
                path=f"{self.BASE_PATH}/1",
                permission=MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
            ),
        ]

    @pytest.fixture
    def bootloader(self) -> BootResource:
        now = utcnow()
        return BootResource(
            id=1,
            created=now,
            updated=now,
            name="grub-efi/uefi",
            architecture="amd64/generic",
            extra={},
            rtype=BootResourceType.UPLOADED,
            rolling=False,
            base_image="",
            kflavor=None,
            bootloader_type="uefi",
            alias=None,
            last_deployed=None,
        )

    async def test_list_bootloaders_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
        bootloader: BootResource,
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.list.return_value = ListResult[
            BootResource
        ](
            items=[bootloader],
            total=2,
        )

        response = await client.get(f"{self.BASE_PATH}?size=1")

        assert response.status_code == 200

        bootloaders_response = BootloaderListResponse(**response.json())

        assert bootloaders_response.total == 2
        assert len(bootloaders_response.items) == 1
        assert bootloaders_response.next == f"{self.BASE_PATH}?page=2&size=1"

        services_mock.boot_resources.list.assert_awaited_once_with(
            page=1,
            size=1,
            query=QuerySpec(
                where=BootResourceClauseFactory.not_clause(
                    BootResourceClauseFactory.with_bootloader_type(None)
                )
            ),
        )

    async def test_list_bootloaders_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
        bootloader: BootResource,
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.list.return_value = ListResult[
            BootResource
        ](
            items=[bootloader],
            total=1,
        )

        response = await client.get(f"{self.BASE_PATH}?size=1")

        assert response.status_code == 200

        bootloaders_response = BootloaderListResponse(**response.json())

        assert bootloaders_response.total == 1
        assert len(bootloaders_response.items) == 1
        assert bootloaders_response.next is None

    async def test_get_bootloader_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
        bootloader: BootResource,
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_one.return_value = bootloader

        response = await client.get(f"{self.BASE_PATH}/1")

        assert response.status_code == 200
        stat_response = BootloaderResponse(**response.json())
        assert stat_response.id == 1
        services_mock.boot_resources.get_one.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceClauseFactory.and_clauses(
                    [
                        BootResourceClauseFactory.not_clause(
                            BootResourceClauseFactory.with_bootloader_type(
                                None
                            )
                        ),
                        BootResourceClauseFactory.with_id(1),
                    ]
                )
            )
        )

    async def test_get_bootloader_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_one.return_value = None

        response = await client.get(f"{self.BASE_PATH}/1")

        assert response.status_code == 404
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404


class TestKernelsApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/kernels"

    @pytest.fixture
    def endpoints_with_authorization(self) -> list[Endpoint]:
        return [
            Endpoint(
                method="GET",
                path=self.BASE_PATH,
                permission=MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
            ),
            Endpoint(
                method="GET",
                path=f"{self.BASE_PATH}/1",
                permission=MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
            ),
        ]

    @pytest.fixture
    def kernel(self) -> BootResource:
        now = utcnow()
        return BootResource(
            id=1,
            created=now,
            updated=now,
            name="myos/noble",
            architecture="amd64/generic",
            extra={},
            rtype=BootResourceType.UPLOADED,
            rolling=False,
            base_image="",
            kflavor="generic",
            bootloader_type=None,
            alias=None,
            last_deployed=None,
        )

    async def test_list_kernels_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
        kernel: BootResource,
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.list.return_value = ListResult[
            BootResource
        ](
            items=[kernel],
            total=2,
        )

        response = await client.get(f"{self.BASE_PATH}?size=1")

        assert response.status_code == 200

        kernels_response = KernelListResponse(**response.json())

        assert kernels_response.total == 2
        assert len(kernels_response.items) == 1
        assert kernels_response.next == f"{self.BASE_PATH}?page=2&size=1"

    async def test_list_kernels_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
        kernel: BootResource,
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.list.return_value = ListResult[
            BootResource
        ](
            items=[kernel],
            total=1,
        )

        response = await client.get(f"{self.BASE_PATH}?size=1")

        assert response.status_code == 200

        kernels_response = KernelListResponse(**response.json())

        assert kernels_response.total == 1
        assert len(kernels_response.items) == 1
        assert kernels_response.next is None

        services_mock.boot_resources.list.assert_awaited_once_with(
            page=1,
            size=1,
            query=QuerySpec(
                where=BootResourceClauseFactory.with_asset_type_kernel()
            ),
        )

    async def test_list_kernels_filters(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
        kernel: BootResource,
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.list.return_value = ListResult[
            BootResource
        ](
            items=[kernel],
            total=2,
        )

        response = await client.get(f"{self.BASE_PATH}?size=1&kflavor=generic")

        assert response.status_code == 200

        kernels_response = KernelListResponse(**response.json())
        assert kernels_response.total == 2
        assert kernels_response.next is not None
        assert "&kflavor=generic" in kernels_response.next

        services_mock.boot_resources.list.assert_awaited_once_with(
            page=1,
            size=1,
            query=QuerySpec(
                where=BootResourceClauseFactory.and_clauses(
                    [
                        BootResourceClauseFactory.with_asset_type_kernel(),
                        BootResourceClauseFactory.with_kflavor("generic"),
                    ]
                )
            ),
        )

    async def test_get_kernel_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
        kernel: BootResource,
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_one.return_value = kernel

        response = await client.get(f"{self.BASE_PATH}/1")

        assert response.status_code == 200
        assert "ETag" in response.headers
        kernel_response = KernelResponse(**response.json())
        assert kernel_response.id == 1

        services_mock.boot_resources.get_one.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceClauseFactory.and_clauses(
                    [
                        BootResourceClauseFactory.with_asset_type_kernel(),
                        BootResourceClauseFactory.with_id(1),
                    ]
                )
            )
        )

    async def test_get_kernel_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_one.return_value = None

        response = await client.get(f"{self.BASE_PATH}/1")

        assert response.status_code == 404
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404
