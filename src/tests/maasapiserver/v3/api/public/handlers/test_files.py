#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from base64 import b64encode
from io import BytesIO
from typing import List
from unittest.mock import ANY, AsyncMock, Mock

from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.responses.files import (
    FileListResponse,
    FileResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.filestorage import (
    FileStorageClauseFactory,
)
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    NotFoundException,
)
from maasservicelayer.exceptions.constants import (
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
)
from maasservicelayer.models.filestorage import FileStorage
from maasservicelayer.services import FileStorageService, ServiceCollectionV3
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

# Simulated files as returned from the service layer
FILE_1 = FileStorage(
    id=1, filename="a.sh", content=b"file-1_content", key="abc", owner_id=0
)
FILE_2 = FileStorage(
    id=2, filename="b.sh", content=b"file-2_content", key="def", owner_id=0
)
FILE_3 = FileStorage(
    id=3,
    filename="maas_c.sh",
    content=b"file-3_content",
    key="ghi",
    owner_id=0,
)
FILE_4 = FileStorage(
    id=4, filename="d.sh", content=b"file-4_content", key="jkl", owner_id=1
)


class TestFilesApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/files"

    @pytest.fixture
    def user_endpoints(self) -> List[Endpoint]:
        return [
            Endpoint(method="GET", path=f"{self.BASE_PATH}"),
            Endpoint(method="GET", path=f"{self.BASE_PATH}:get"),
            Endpoint(method="GET", path=f"{self.BASE_PATH}/{FILE_2.key}"),
            Endpoint(method="PUT", path=f"{self.BASE_PATH}"),
            Endpoint(method="DELETE", path=f"{self.BASE_PATH}"),
        ]

    @pytest.fixture
    def admin_endpoints(self) -> List[Endpoint]:
        return []

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

    async def test_list_files(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.filestorage = Mock(FileStorageService)
        services_mock.filestorage.get_many.return_value = [
            FILE_1,
            FILE_2,
            FILE_3,
        ]

        response = await mocked_api_client_user.get(f"{self.BASE_PATH}")

        assert response.status_code == 200

        files_response = FileListResponse(**response.json())

        assert len(files_response.items) == 3

        # Make sure they don't have content, i.e. they're FileListItemResponse
        for item in files_response.items:
            assert "content" not in item.__dict__

    async def test_list_files_with_prefix(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.filestorage = Mock(FileStorageService)
        services_mock.filestorage.get_many.return_value = [FILE_3]

        response = await mocked_api_client_user.get(
            url=f"{self.BASE_PATH}",
            params={"prefix": "maas_"},
        )

        assert response.status_code == 200

        files_response = FileListResponse(**response.json())

        assert len(files_response.items) == 1

    async def test_get_file(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.filestorage = Mock(FileStorageService)
        services_mock.filestorage.get_one.return_value = FILE_1

        response = await mocked_api_client_user.get(
            url=f"{self.BASE_PATH}:get",
            params={"filename": FILE_1.filename},
        )

        assert response.status_code == 200

        file_response = FileResponse(**response.json())

        assert file_response.id == FILE_1.id
        assert file_response.filename == FILE_1.filename
        assert file_response.content == b64encode(FILE_1.content).decode()
        assert file_response.key == FILE_1.key
        assert file_response.owner_id == FILE_1.owner_id

    async def test_get_file_fails_when_no_match(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.filestorage = Mock(FileStorageService)
        services_mock.filestorage.get_one.return_value = None

        response = await mocked_api_client_user.get(
            url=f"{self.BASE_PATH}:get",
            params={"filename": FILE_1.filename},
        )

        assert response.status_code == 404

        error_response = ErrorBodyResponse(**response.json())

        assert error_response.code == 404
        assert error_response.kind == "Error"

    async def test_get_file_attaches_header_on_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.filestorage = Mock(FileStorageService)
        services_mock.filestorage.get_one.return_value = None

        response = await mocked_api_client_user.get(
            url=f"{self.BASE_PATH}:get",
            params={"filename": FILE_1.filename},
        )

        assert response.status_code == 404

        assert "Workaround" in response.headers
        assert response.headers["Workaround"] == "bug1123986"

        error_response = ErrorBodyResponse(**response.json())

        assert error_response.code == 404
        assert error_response.kind == "Error"

    async def test_get_file_by_key(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        # If `key_to_get` is None, then there's no way to disambiguate
        # `/files/{key}` and `/files`
        key_to_get = FILE_2.key
        services_mock.filestorage = Mock(FileStorageService)
        services_mock.filestorage.get_one.return_value = FILE_2

        response = await mocked_api_client_user.get(
            url=f"{self.BASE_PATH}/{key_to_get}",
        )

        assert response.status_code == 200

        file_response = FileResponse(**response.json())

        assert file_response.id == FILE_2.id
        assert file_response.filename == FILE_2.filename
        assert file_response.content == b64encode(FILE_2.content).decode()
        assert file_response.key == FILE_2.key
        assert file_response.owner_id == FILE_2.owner_id

        services_mock.filestorage.get_one.assert_called_once_with(
            query=QuerySpec(
                where=FileStorageClauseFactory.and_clauses(
                    [
                        FileStorageClauseFactory.with_key(key_to_get),
                        FileStorageClauseFactory.with_owner_id(0),
                    ]
                )
            )
        )

    async def test_get_file_by_key_not_found(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.filestorage = Mock(FileStorageService)
        services_mock.filestorage.get_one.return_value = None

        response = await mocked_api_client_user.get(
            url=f"{self.BASE_PATH}/abc",
        )

        assert response.status_code == 404

        error_response = ErrorBodyResponse(**response.json())

        assert error_response.code == 404
        assert error_response.kind == "Error"

    async def test_create_or_replace_file(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        file_name = "test.bin"
        file_data = self.create_dummy_binary_upload_file(file_name)

        file_to_return = FileStorage(
            id=0,
            filename=file_name,
            content=file_data.read(),
            key="test_key",
            owner_id=0,
        )
        file_data.seek(0)

        services_mock.filestorage = AsyncMock(FileStorageService)
        services_mock.filestorage.create_or_update.return_value = (
            file_to_return
        )

        response = await mocked_api_client_user.put(
            url=f"{self.BASE_PATH}",
            data={
                "filename": file_name,
            },
            files={
                "file": file_data,
            },
        )

        assert response.status_code == 201

        file_response = FileResponse(**response.json())

        assert file_response.filename == file_to_return.filename
        assert (
            file_response.content == b64encode(file_to_return.content).decode()
        )
        assert file_response.key == file_to_return.key
        assert file_response.owner_id == file_to_return.owner_id

    async def test_create_or_replace_file_when_filename_contains_slashes(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        file_name = "this/is/a/test.bin"
        file_data = self.create_dummy_binary_upload_file(file_name)

        file_to_return = FileStorage(
            id=0,
            filename=file_name,
            content=file_data.read(),
            key="test_key",
            owner_id=0,
        )
        file_data.seek(0)

        services_mock.filestorage = Mock(FileStorageService)
        services_mock.filestorage.create_or_update.return_value = (
            file_to_return
        )

        response = await mocked_api_client_user.put(
            url=f"{self.BASE_PATH}",
            data={
                "filename": file_name,
            },
            files={
                "file": file_data,
            },
        )

        assert response.status_code == 201

        file_response = FileResponse(**response.json())

        assert file_response.filename == file_name
        assert (
            file_response.content == b64encode(file_to_return.content).decode()
        )
        assert file_response.key == file_to_return.key
        assert file_response.owner_id == file_to_return.owner_id

    async def test_create_or_replace_file_overwrites_existing_file_with_same_name(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        file_name = "test.bin"
        file_data = self.create_dummy_binary_upload_file(file_name)

        file_to_return = FileStorage(
            id=0,
            filename=file_name,
            content=file_data.read(),
            key="test_key",
            owner_id=0,
        )
        file_data.seek(0)

        services_mock.filestorage = AsyncMock(FileStorageService)
        services_mock.filestorage.create_or_update.return_value = (
            file_to_return
        )

        response = await mocked_api_client_user.put(
            url=f"{self.BASE_PATH}",
            data={
                "filename": file_name,
            },
            files={
                "file": file_data,
            },
        )

        assert response.status_code == 201

        file_response = FileResponse(**response.json())

        assert file_response.filename == file_to_return.filename
        assert (
            file_response.content == b64encode(file_to_return.content).decode()
        )
        assert file_response.key == file_to_return.key
        assert file_response.owner_id == file_to_return.owner_id

    async def test_create_or_replace_file_empty_file(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        file_name = "test.bin"
        file_data = self.create_dummy_binary_upload_file(
            name=file_name, size_in_bytes=0
        )

        file_to_return = FileStorage(
            id=0,
            filename=file_name,
            content=b"",
            key="test_key",
            owner_id=0,
        )

        services_mock.filestorage = Mock(FileStorageService)
        services_mock.filestorage.create_or_update.return_value = (
            file_to_return
        )

        response = await mocked_api_client_user.put(
            url=f"{self.BASE_PATH}",
            data={
                "filename": file_name,
            },
            files={
                "file": file_data,
            },
        )

        assert response.status_code == 201

    async def test_delete_file(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        expected_user_id = 0

        services_mock.filestorage = Mock(FileStorageService)
        services_mock.filestorage.delete_one.return_value = FILE_1

        response = await mocked_api_client_user.delete(
            url=f"{self.BASE_PATH}",
            params={"filename": FILE_1.filename},
        )

        assert response.status_code == 204

        # Make sure it only looks at the files the authenticated user owns
        services_mock.filestorage.delete_one.assert_called_once_with(
            query=QuerySpec(
                where=FileStorageClauseFactory.and_clauses(
                    [
                        FileStorageClauseFactory.with_filename(
                            FILE_1.filename
                        ),
                        FileStorageClauseFactory.with_owner_id(
                            expected_user_id
                        ),
                    ]
                )
            ),
            etag_if_match=ANY,
        )

    async def test_delete_file_with_etag(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.filestorage = Mock(FileStorageService)
        services_mock.filestorage.delete_one.return_value = FILE_1

        response = await mocked_api_client_user.delete(
            url=f"{self.BASE_PATH}",
            params={"filename": FILE_1.filename},
            headers={"if-match": "my_etag"},
        )

        assert response.status_code == 204

        # Ensure that the query filters by files owned by the requesting user
        services_mock.filestorage.delete_one.assert_called_with(
            query=QuerySpec(
                where=FileStorageClauseFactory.and_clauses(
                    [
                        FileStorageClauseFactory.with_filename(
                            FILE_1.filename
                        ),
                        FileStorageClauseFactory.with_owner_id(0),
                    ]
                )
            ),
            etag_if_match="my_etag",
        )

    async def test_delete_file_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        """
        This test covers two scenarios:
        1. The file with `filename` doesn't exist in the database.
        2. The file `filename` might exist but the requesting user doesn't own it.
        """
        filename_to_delete = FILE_4.filename

        services_mock.filestorage = Mock(FileStorageService)
        services_mock.filestorage.delete_one.side_effect = NotFoundException(
            details=[
                BaseExceptionDetail(
                    type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                    message=f"File with filename {filename_to_delete} does not exist.",
                )
            ]
        )

        response = await mocked_api_client_user.delete(
            url=f"{self.BASE_PATH}",
            params={"filename": filename_to_delete},
        )

        assert response.status_code == 404
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())

        assert error_response.kind == "Error"
        assert error_response.code == 404

        # Ensure that the query filters by files owned by the requesting user
        services_mock.filestorage.delete_one.assert_called_with(
            query=QuerySpec(
                where=FileStorageClauseFactory.and_clauses(
                    [
                        FileStorageClauseFactory.with_filename(
                            filename_to_delete
                        ),
                        FileStorageClauseFactory.with_owner_id(0),
                    ]
                )
            ),
            etag_if_match=None,
        )
