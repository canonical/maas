# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import hashlib
from io import BytesIO
from unittest.mock import MagicMock, Mock, patch

from aiofiles.threadpool.binary import AsyncBufferedIOBase
from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.responses.boot_resources import (
    BootResourceListResponse,
    BootResourceResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.boot_resources import (
    BootResourceFileType,
    BootResourceType,
)
from maascommon.workflows.bootresource import (
    ResourceDownloadParam,
    short_sha,
    SYNC_BOOTRESOURCES_WORKFLOW_NAME,
    SyncRequestParam,
)
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootresources import (
    BootResourceClauseFactory,
)
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    NotFoundException,
    PreconditionFailedException,
)
from maasservicelayer.exceptions.constants import (
    ETAG_PRECONDITION_VIOLATION_TYPE,
    INVALID_ARGUMENT_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.bootresourcefiles import BootResourceFile
from maasservicelayer.models.bootresources import BootResource
from maasservicelayer.models.bootresourcesets import BootResourceSet
from maasservicelayer.models.nodes import Node
from maasservicelayer.services import ServiceCollectionV3
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
from maasservicelayer.utils.image_local_files import LocalStoreFileSizeMismatch
from maastesting.factory import factory
from tests.fixtures import AsyncContextManagerMock
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

TEST_BOOT_RESOURCE_1 = BootResource(
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

TEST_BOOT_RESOURCE_2 = BootResource(
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

TEST_BOOT_RESOURCE_SET = BootResourceSet(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    version="20250829",
    label="uploaded",
    resource_id=1,
)

TEST_BOOT_RESOURCE_FILE = BootResourceFile(
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


class MockTemporaryFile:
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


class TestBootResourcesApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/boot_resources"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=self.BASE_PATH),
            Endpoint(method="GET", path=f"{self.BASE_PATH}/1"),
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="POST", path=self.BASE_PATH),
            Endpoint(method="DELETE", path=f"{self.BASE_PATH}/1"),
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
    async def test_upload_boot_resource(
        self,
        request_to_builder_mock: MagicMock,
        async_local_file_mock: MagicMock,
        maas_id_mock: MagicMock,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
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

        request_to_builder_mock.return_value = None

        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.create.return_value = TEST_BOOT_RESOURCE_1
        services_mock.boot_resources.get_next_version_name.return_value = (
            TEST_BOOT_RESOURCE_SET.version
        )

        services_mock.boot_resource_sets = Mock(BootResourceSetsService)
        services_mock.boot_resource_sets.create.return_value = (
            TEST_BOOT_RESOURCE_SET
        )

        services_mock.boot_resource_files = Mock(BootResourceFilesService)
        services_mock.boot_resource_files.create.return_value = resource_file
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
            "size": str(file_size),
            "architecture": "amd64/generic",
            "Content-Type": "application/octet-stream",
        }

        raw_data = file_data.read()
        response = await mocked_api_client_admin.post(
            url=f"{self.BASE_PATH}",
            headers=headers,
            content=raw_data,
        )

        assert response.status_code == 201

        boot_resource_response = BootResourceResponse(**response.json())

        assert boot_resource_response.type == "Uploaded"
        assert boot_resource_response.name == TEST_BOOT_RESOURCE_1.name
        assert (
            boot_resource_response.architecture
            == TEST_BOOT_RESOURCE_1.architecture
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
    async def test_upload_boot_resource_400_sha_does_not_match(
        self,
        request_to_builder_mock: MagicMock,
        async_local_file_mock: MagicMock,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        file_name = "test.bin"
        file_size = 1024
        file_data = self.create_dummy_binary_upload_file(
            name=file_name, size_in_bytes=file_size
        )

        request_to_builder_mock.return_value = None

        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.create.return_value = TEST_BOOT_RESOURCE_1
        services_mock.boot_resources.get_next_version_name.return_value = (
            TEST_BOOT_RESOURCE_SET.version
        )

        services_mock.boot_resource_sets = Mock(BootResourceSetsService)
        services_mock.boot_resource_sets.create.return_value = (
            TEST_BOOT_RESOURCE_SET
        )

        services_mock.boot_resource_files = Mock(BootResourceFilesService)
        services_mock.boot_resource_files.calculate_filename_on_disk.return_value = file_name

        async_local_file_mock.return_value = AsyncContextManagerMock(
            MockTemporaryFile()
        )

        headers = {
            "name": "my-image",
            "sha256": factory.make_hex_string(size=16),
            "size": str(file_size),
            "architecture": "amd64/generic",
            "Content-Type": "application/octet-stream",
        }

        raw_data = file_data.read()
        response = await mocked_api_client_admin.post(
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

    @patch(
        "maasservicelayer.utils.image_local_files.AsyncLocalBootResourceFile"
    )
    @patch(
        "maasapiserver.v3.api.public.handlers.boot_resources.BootResourceCreateRequest.to_builder"
    )
    async def test_upload_boot_resource_400_size_does_not_match(
        self,
        request_to_builder_mock: MagicMock,
        async_local_file_mock: MagicMock,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        file_name = "test.bin"
        file_size = 1024
        file_data = self.create_dummy_binary_upload_file(
            name=file_name, size_in_bytes=file_size
        )

        request_to_builder_mock.return_value = None

        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.create.return_value = TEST_BOOT_RESOURCE_1
        services_mock.boot_resources.get_next_version_name.return_value = (
            TEST_BOOT_RESOURCE_SET.version
        )

        services_mock.boot_resource_sets = Mock(BootResourceSetsService)
        services_mock.boot_resource_sets.create.return_value = (
            TEST_BOOT_RESOURCE_SET
        )

        services_mock.boot_resource_files = Mock(BootResourceFilesService)
        services_mock.boot_resource_files.calculate_filename_on_disk.return_value = file_name

        async_local_file_mock.store.side_effect = LocalStoreFileSizeMismatch()

        headers = {
            "name": "my-image",
            "sha256": factory.make_hex_string(size=16),
            "size": str(123456),
            "architecture": "amd64/generic",
            "Content-Type": "application/octet-stream",
        }

        raw_data = file_data.read()
        response = await mocked_api_client_admin.post(
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

        assert "size" in error_response.details[0].message

    @patch("maasservicelayer.utils.image_local_files.aiofiles.os.statvfs")
    @patch(
        "maasapiserver.v3.api.public.handlers.boot_resources.BootResourceCreateRequest.to_builder"
    )
    async def test_upload_boot_resource_507_insufficient_disk_space(
        self,
        request_to_builder_mock: MagicMock,
        statvfs_mock: MagicMock,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        request_to_builder_mock.return_value = None

        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.create.return_value = TEST_BOOT_RESOURCE_1
        services_mock.boot_resources.get_next_version_name.return_value = (
            TEST_BOOT_RESOURCE_SET.version
        )

        services_mock.boot_resource_sets = Mock(BootResourceSetsService)
        services_mock.boot_resource_sets.create.return_value = (
            TEST_BOOT_RESOURCE_SET
        )

        services_mock.boot_resource_files = Mock(BootResourceFilesService)
        services_mock.boot_resource_files.calculate_filename_on_disk.return_value = "file.bin"

        statvfs_result = Mock()
        statvfs_result.f_bavail = 0
        statvfs_result.f_frsize = 4096
        statvfs_mock.return_value = statvfs_result

        headers = {
            "name": "my-image",
            "sha256": factory.make_hex_string(size=16),
            "size": str(12345),
            "architecture": "amd64/generic",
            "Content-Type": "application/octet-stream",
        }

        response = await mocked_api_client_admin.post(
            url=f"{self.BASE_PATH}",
            headers=headers,
            content=bytes(),
        )

        assert response.status_code == 507

        error_response = ErrorBodyResponse(**response.json())

        assert error_response.code == 507
        assert error_response.kind == "Error"

    async def test_list_boot_resources_200_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.list.return_value = ListResult[
            BootResource
        ](items=[TEST_BOOT_RESOURCE_1], total=1)

        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")

        assert response.status_code == 200

        boot_sources_response = BootResourceListResponse(**response.json())

        assert len(boot_sources_response.items) == 1
        assert boot_sources_response.total == 1
        assert boot_sources_response.next is None

    async def test_list_boot_resources_200_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.list.return_value = ListResult[
            BootResource
        ](items=[TEST_BOOT_RESOURCE_1, TEST_BOOT_RESOURCE_2], total=2)

        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")

        assert response.status_code == 200

        boot_resources_response = BootResourceListResponse(**response.json())

        assert len(boot_resources_response.items) == 2
        assert boot_resources_response.total == 2
        assert (
            boot_resources_response.next == f"{self.BASE_PATH}?page=2&size=1"
        )

    async def test_list_boot_resources_200_with_type_has_items(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.list.return_value = ListResult[
            BootResource
        ](items=[TEST_BOOT_RESOURCE_2], total=1)

        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}?type=uploaded&size=1"
        )

        assert response.status_code == 200

        boot_resource_list_response = BootResourceListResponse(
            **response.json()
        )

        assert len(boot_resource_list_response.items) == 1
        assert boot_resource_list_response.total == 1
        assert boot_resource_list_response.next is None

        services_mock.boot_resources.list.assert_called_once_with(
            page=1,
            size=1,
            query=QuerySpec(
                where=BootResourceClauseFactory.with_rtype(
                    BootResourceType.UPLOADED
                ),
            ),
        )

    async def test_list_boot_resources_200_with_type_no_items(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.list.return_value = ListResult[
            BootResource
        ](items=[], total=0)

        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}?type=synced&size=1"
        )

        assert response.status_code == 200

        boot_resource_list_response = BootResourceListResponse(
            **response.json()
        )

        assert len(boot_resource_list_response.items) == 0
        assert boot_resource_list_response.total == 0
        assert boot_resource_list_response.next is None

        services_mock.boot_resources.list.assert_called_once_with(
            page=1,
            size=1,
            query=QuerySpec(
                where=BootResourceClauseFactory.with_rtype(
                    BootResourceType.SYNCED
                ),
            ),
        )

    async def test_get_boot_resource_by_id_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_by_id.return_value = (
            TEST_BOOT_RESOURCE_1
        )

        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/1")

        assert response.status_code == 200
        assert "ETag" in response.headers

        boot_resource_response = BootResourceResponse(**response.json())

        assert boot_resource_response.id == 1

    async def test_get_boot_resource_by_id_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_by_id.return_value = None

        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/3")

        assert response.status_code == 404
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404

    async def test_delete_boot_resources_204(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_by_id.return_value = (
            TEST_BOOT_RESOURCE_2
        )
        services_mock.boot_resources.delete_by_id.return_value = (
            TEST_BOOT_RESOURCE_2
        )

        response = await mocked_api_client_admin.delete(f"{self.BASE_PATH}/1")

        assert response.status_code == 204

        services_mock.boot_resources.delete_by_id.assert_called_once_with(
            id=1,
            etag_if_match=None,
        )

    async def test_delete_boot_resources_204_by_etag(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        correct_etag = "correct_etag"

        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_by_id.return_value = (
            TEST_BOOT_RESOURCE_2
        )
        services_mock.boot_resources.delete_by_id.return_value = (
            TEST_BOOT_RESOURCE_2
        )

        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/1",
            headers={"if-match": correct_etag},
        )

        assert response.status_code == 204

        services_mock.boot_resources.delete_by_id.assert_called_once_with(
            id=1,
            etag_if_match=correct_etag,
        )

    async def test_delete_boot_resources_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_by_id.return_value = None
        services_mock.boot_resources.delete_by_id.side_effect = (
            NotFoundException()
        )

        response = await mocked_api_client_admin.delete(f"{self.BASE_PATH}/2")

        assert response.status_code == 404
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())

        assert error_response.kind == "Error"
        assert error_response.code == 404

        services_mock.boot_resources.delete_by_id.assert_called_once_with(
            id=2,
            etag_if_match=None,
        )

    async def test_delete_boot_resources_412_wrong_etag(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        wrong_etag = "wrong_etag"
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_by_id.return_value = (
            TEST_BOOT_RESOURCE_2
        )
        services_mock.boot_resources.delete_by_id.side_effect = PreconditionFailedException(
            details=[
                BaseExceptionDetail(
                    type=ETAG_PRECONDITION_VIOLATION_TYPE,
                    message=f"The resource etag '{wrong_etag}' did not match 'my_etag'.",
                )
            ]
        )

        response = await mocked_api_client_admin.delete(
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

        services_mock.boot_resources.delete_by_id.assert_called_once_with(
            id=2,
            etag_if_match=wrong_etag,
        )
