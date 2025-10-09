#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
import asyncio
import hashlib
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

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
    LocalSyncRequestParam,
    ResourceDownloadParam,
    SpaceRequirementParam,
    SYNC_LOCAL_BOOTRESOURCES_WORKFLOW_NAME,
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
    MISSING_FILE_CONTENT_VIOLATION_TYPE,
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
from maasservicelayer.utils.image_local_files import LocalBootResourceFile
from maastesting.factory import factory
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

    @patch(
        "maasapiserver.v3.api.public.handlers.boot_resources.BootResourcesHandler._get_maas_id"
    )
    @patch(
        "maasapiserver.v3.api.public.handlers.boot_resources.NamedTemporaryFile"
    )
    @patch(
        "maasapiserver.v3.api.public.handlers.boot_resources.BootResourceCreateRequest.to_builder"
    )
    async def test_upload_boot_resource(
        self,
        request_to_builder_mock: MagicMock,
        named_temp_file_mock: MagicMock,
        get_maas_id_mock: MagicMock,
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

        local_file_path_mock = Mock(Path)
        # Set to true to skip mocking the hard link
        local_file_path_mock.exists.return_value = True

        local_file_mock = Mock(LocalBootResourceFile)
        local_file_mock.path.return_value = local_file_path_mock

        resource_file.create_local_file.return_value = local_file_mock

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

        get_maas_id_mock.return_value = "abc1de"

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

        async def fake_write(d: bytes):
            await asyncio.sleep(0)
            return len(d)

        async def fake_tell():
            await asyncio.sleep(0)
            return file_size

        named_temp_file_mock.return_value.__aenter__.return_value.write = (
            fake_write
        )
        named_temp_file_mock.return_value.__aenter__.return_value.name = (
            "test-tmp-file.txt"
        )
        named_temp_file_mock.return_value.__aenter__.return_value.tell = (
            fake_tell
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
            SYNC_LOCAL_BOOTRESOURCES_WORKFLOW_NAME,
            LocalSyncRequestParam(
                resource=ResourceDownloadParam(
                    rfile_ids=[resource_file.id],
                    source_list=[],
                    sha256=sha256_str,
                    filename_on_disk=file_name,
                    total_size=file_size,
                ),
                space_requirement=SpaceRequirementParam(
                    total_resources_size=file_size,
                ),
            ),
            wait=False,
        )

    @patch(
        "maasapiserver.v3.api.public.handlers.boot_resources.NamedTemporaryFile"
    )
    @patch(
        "maasapiserver.v3.api.public.handlers.boot_resources.BootResourceCreateRequest.to_builder"
    )
    async def test_upload_boot_resource_400_sha_does_not_match(
        self,
        request_to_builder_mock: MagicMock,
        named_temp_file_mock: MagicMock,
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

        async def fake_write(d: bytes):
            await asyncio.sleep(0)
            return len(d)

        async def fake_tell():
            await asyncio.sleep(0)
            return file_size

        named_temp_file_mock.return_value.__aenter__.return_value.write = (
            fake_write
        )
        named_temp_file_mock.return_value.__aenter__.return_value.name = (
            "test-tmp-file.txt"
        )
        named_temp_file_mock.return_value.__aenter__.return_value.tell = (
            fake_tell
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
        "maasapiserver.v3.api.public.handlers.boot_resources.NamedTemporaryFile"
    )
    @patch(
        "maasapiserver.v3.api.public.handlers.boot_resources.BootResourceCreateRequest.to_builder"
    )
    async def test_upload_boot_resource_400_size_does_not_match(
        self,
        request_to_builder_mock: MagicMock,
        named_temp_file_mock: MagicMock,
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

        async def fake_write(d: bytes):
            await asyncio.sleep(0)
            return len(d)

        named_temp_file_mock.return_value.__aenter__.return_value.write = (
            fake_write
        )

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

    @patch(
        "maasapiserver.v3.api.public.handlers.boot_resources.NamedTemporaryFile"
    )
    @patch(
        "maasapiserver.v3.api.public.handlers.boot_resources.BootResourceCreateRequest.to_builder"
    )
    async def test_upload_boot_resource_400_no_content(
        self,
        request_to_builder_mock: MagicMock,
        named_temp_file_mock: MagicMock,
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

        async def fake_write(_: bytes):
            await asyncio.sleep(0)
            return 0

        named_temp_file_mock.return_value.__aenter__.return_value.write = (
            fake_write
        )

        headers = {
            "name": "my-image",
            "sha256": factory.make_hex_string(size=16),
            "size": str(0),
            "architecture": "amd64/generic",
            "Content-Type": "application/octet-stream",
        }

        response = await mocked_api_client_admin.post(
            url=f"{self.BASE_PATH}",
            headers=headers,
            content=bytes(),
        )

        assert response.status_code == 400

        error_response = ErrorBodyResponse(**response.json())

        assert error_response.code == 400
        assert error_response.kind == "Error"
        assert (
            error_response.details[0].type  # pyright: ignore[reportOptionalSubscript]
            == MISSING_FILE_CONTENT_VIOLATION_TYPE
        )

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
