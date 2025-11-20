# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from base64 import b64decode, b64encode
from unittest.mock import Mock

from fastapi.encoders import jsonable_encoder
from httpx import AsyncClient
import pytest
from temporalio.client import Client, WorkflowExecutionStatus, WorkflowHandle

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.requests.boot_sources import (
    BootSourceFetchRequest,
)
from maasapiserver.v3.api.public.models.responses.boot_source_selections import (
    BootSourceSelectionListResponse,
    BootSourceSelectionResponse,
)
from maasapiserver.v3.api.public.models.responses.boot_sources import (
    BootSourceAvailableImageListResponse,
    BootSourceResponse,
    BootSourcesListResponse,
    UISourceAvailableImageListResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.workflows.bootresource import (
    SYNC_SELECTION_WORKFLOW_NAME,
    SyncSelectionParam,
)
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootsourceselections import (
    BootSourceSelectionClauseFactory,
)
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    BaseExceptionDetail,
    NotFoundException,
)
from maasservicelayer.exceptions.constants import (
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
    UNIQUE_CONSTRAINT_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.bootsources import (
    BootSource,
    BootSourceAvailableImage,
)
from maasservicelayer.models.bootsourceselections import BootSourceSelection
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.boot_sources import BootSourcesService
from maasservicelayer.services.bootsourcecache import BootSourceCacheService
from maasservicelayer.services.bootsourceselections import (
    BootSourceSelectionsService,
)
from maasservicelayer.services.image_manifests import ImageManifestsService
from maasservicelayer.services.temporal import TemporalService
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

TEST_BOOTSOURCE_1 = BootSource(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    url="http://example.com/v1/",
    keyring_filename="/path/to/keyring.gpg",
    keyring_data="",
    priority=10,
    skip_keyring_verification=False,
)

TEST_BOOTSOURCE_2 = BootSource(
    id=2,
    created=utcnow(),
    updated=utcnow(),
    url="http://example.com/v2/",
    keyring_filename="/path/to/keyring.gpg",
    keyring_data="",
    priority=10,
    skip_keyring_verification=False,
)

TEST_BOOTSOURCESELECTION = BootSourceSelection(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    os="ubuntu",
    release="noble",
    arch="amd64",
    boot_source_id=12,
)


class TestBootSourcesApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/boot_sources"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=self.BASE_PATH),
            Endpoint(method="GET", path=f"{self.BASE_PATH}/1"),
            Endpoint(method="POST", path=f"{self.BASE_PATH}:fetch"),
            Endpoint(
                method="GET", path=f"{self.BASE_PATH}/1/available_images"
            ),
            Endpoint(method="GET", path=f"{V3_API_PREFIX}/available_images"),
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="POST", path=f"{self.BASE_PATH}"),
            Endpoint(method="PUT", path=f"{self.BASE_PATH}/1"),
            Endpoint(method="DELETE", path=f"{self.BASE_PATH}/1"),
        ]

    async def test_list_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.list.return_value = ListResult[BootSource](
            items=[TEST_BOOTSOURCE_1], total=1
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        boot_sources_response = BootSourcesListResponse(**response.json())
        assert len(boot_sources_response.items) == 1
        assert boot_sources_response.total == 1
        assert boot_sources_response.next is None

    async def test_list_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.list.return_value = ListResult[BootSource](
            items=[TEST_BOOTSOURCE_1, TEST_BOOTSOURCE_2], total=2
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        boot_sources_response = BootSourcesListResponse(**response.json())
        assert len(boot_sources_response.items) == 2
        assert boot_sources_response.total == 2
        assert boot_sources_response.next == f"{self.BASE_PATH}?page=2&size=1"

    async def test_get_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.get_by_id.return_value = TEST_BOOTSOURCE_1
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/{TEST_BOOTSOURCE_1.id}"
        )
        assert response.status_code == 200
        assert response.headers["ETag"]
        boot_source_response = BootSourceResponse(**response.json())
        assert boot_source_response.id == TEST_BOOTSOURCE_1.id

    async def test_get_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.get_by_id.return_value = None
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/101")
        assert response.status_code == 404
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404

    async def test_put_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.get_by_id.return_value = TEST_BOOTSOURCE_1
        updated = TEST_BOOTSOURCE_1.copy()
        updated.url = "http://example.com/v2/"
        updated.priority = 15
        services_mock.boot_sources.update_by_id.return_value = updated

        update_request = {
            "url": "http://example.com/v2/",
            "keyring_filename": "/path/to/keyring.gpg",
            "keyring_data": "",
            "priority": 15,
            "skip_keyring_verification": False,
        }
        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/1",
            json=jsonable_encoder(update_request),
        )

        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0

        updated_boot_source_response = BootSourceResponse(**response.json())
        assert updated_boot_source_response.id == updated.id
        assert updated_boot_source_response.url == updated.url
        assert updated_boot_source_response.priority == updated.priority

    async def test_put_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.update_by_id.side_effect = NotFoundException(
            details=[
                BaseExceptionDetail(
                    type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                    message="Resource with such identifiers does not exist.",
                )
            ]
        )

        update_request = {
            "url": "http://example.com/v2/",
            "keyring_filename": "/path/to/keyring.gpg",
            "keyring_data": "",
            "priority": 15,
            "skip_keyring_verification": False,
        }
        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/1",
            json=jsonable_encoder(update_request),
        )
        assert response.status_code == 404
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404

    async def test_post_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.create.return_value = TEST_BOOTSOURCE_1

        create_request = {
            "url": TEST_BOOTSOURCE_1.url,
            "keyring_filename": TEST_BOOTSOURCE_1.keyring_filename,
            "priority": TEST_BOOTSOURCE_1.priority,
            "skip_keyring_verification": TEST_BOOTSOURCE_1.skip_keyring_verification,
        }
        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=jsonable_encoder(create_request)
        )
        assert response.status_code == 201
        assert response.headers["ETag"]
        boot_source_response = BootSourceResponse(**response.json())

        assert boot_source_response.url == TEST_BOOTSOURCE_1.url
        assert (
            boot_source_response.keyring_filename
            == TEST_BOOTSOURCE_1.keyring_filename
        )
        assert boot_source_response.priority == TEST_BOOTSOURCE_1.priority
        assert not boot_source_response.skip_keyring_verification
        assert (
            boot_source_response.hal_links.self.href
            == f"{self.BASE_PATH}/{boot_source_response.id}"
        )

    async def test_post_409(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.create.side_effect = AlreadyExistsException(
            details=[
                BaseExceptionDetail(
                    type=UNIQUE_CONSTRAINT_VIOLATION_TYPE,
                    message="A resource with such identifiers already exist.",
                )
            ]
        )
        create_request = {
            "url": TEST_BOOTSOURCE_1.url,
            "keyring_filename": TEST_BOOTSOURCE_1.keyring_filename,
            "priority": TEST_BOOTSOURCE_1.priority,
            "skip_keyring_verification": TEST_BOOTSOURCE_1.skip_keyring_verification,
        }
        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=jsonable_encoder(create_request)
        )
        assert response.status_code == 409

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 409

    async def test_delete_resource(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.delete_by_id.side_effect = None
        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/100"
        )
        assert response.status_code == 204

    async def test_fetch_boot_sources(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.image_manifests = Mock(ImageManifestsService)
        services_mock.image_manifests.fetch_image_metadata.return_value = []

        request = BootSourceFetchRequest(
            url="https://path/to/images/server",
            keyring_path="/path/to/keyring",
        )

        response = await mocked_api_client_user.post(
            f"{self.BASE_PATH}:fetch", json=jsonable_encoder(request)
        )

        assert response.status_code == 200

        services_mock.image_manifests.fetch_image_metadata.assert_called_once_with(
            source_url=request.url,
            keyring_path=request.keyring_path,
            keyring_data=None,
        )

    async def test_fetch_encodes_keyring_data(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        images_server_url = "https://path/to/images/server"
        keyring_data_str = b64encode(b"keyring_data")

        expected_bytes = b64decode(keyring_data_str)

        services_mock.image_manifests = Mock(ImageManifestsService)
        services_mock.image_manifests.fetch_image_metadata.return_value = []

        request = BootSourceFetchRequest(
            url=images_server_url,
            keyring_data=keyring_data_str,
        )

        response = await mocked_api_client_user.post(
            url=f"{self.BASE_PATH}:fetch",
            json=jsonable_encoder(request),
        )

        assert response.status_code == 200

        services_mock.image_manifests.fetch_image_metadata.assert_called_once_with(
            source_url=images_server_url,
            keyring_path=None,
            keyring_data=expected_bytes,
        )

    async def test_get_all_available_images_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        boot_source_id_1 = 1
        boot_source_id_2 = 2

        services_mock.boot_source_cache = Mock(BootSourceCacheService)
        services_mock.boot_source_cache.get_all_available_images.return_value = [
            BootSourceAvailableImage(
                os="Ubuntu",
                release="Noble",
                release_title="24.04 LTS",
                arch="amd64",
                boot_source_id=boot_source_id_1,
            ),
            BootSourceAvailableImage(
                os="Ubuntu",
                release="Plucky",
                release_title="25.04",
                arch="amd64",
                boot_source_id=boot_source_id_2,
            ),
        ]

        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.get_by_id.side_effect = [
            TEST_BOOTSOURCE_1,
            TEST_BOOTSOURCE_2,
        ]

        response = await mocked_api_client_user.get(
            url=f"{V3_API_PREFIX}/available_images",
        )

        assert response.status_code == 200

        sources_response = UISourceAvailableImageListResponse(
            **response.json()
        )

        assert len(sources_response.items) == 2

        assert sources_response.items[0].source_id == TEST_BOOTSOURCE_1.id
        assert sources_response.items[1].source_id == TEST_BOOTSOURCE_2.id

    async def test_get_all_available_images_200_empty_when_no_sources(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.boot_source_cache = Mock(BootSourceCacheService)
        services_mock.boot_source_cache.get_all_available_images.return_value = []

        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.get_by_id.side_effect = []

        response = await mocked_api_client_user.get(
            url=f"{V3_API_PREFIX}/available_images",
        )

        assert response.status_code == 200

        sources_response = UISourceAvailableImageListResponse(
            **response.json()
        )

        assert len(sources_response.items) == 0

    async def test_get_boot_source_available_images_200_list_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        boot_source_id = 1

        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.get_by_id.return_value = TEST_BOOTSOURCE_1

        services_mock.boot_source_cache = Mock(BootSourceCacheService)
        services_mock.boot_source_cache.list_boot_source_cache_available_images.return_value = ListResult[
            BootSourceAvailableImage
        ](
            items=[
                BootSourceAvailableImage(
                    os="Ubuntu",
                    release="Noble",
                    release_title="24.04 LTS",
                    arch="amd64",
                    boot_source_id=boot_source_id,
                ),
                BootSourceAvailableImage(
                    os="Ubuntu",
                    release="Plucky",
                    release_title="25.04",
                    arch="amd64",
                    boot_source_id=boot_source_id,
                ),
            ],
            total=2,
        )

        response = await mocked_api_client_user.get(
            url=f"{self.BASE_PATH}/{boot_source_id}/available_images?size=2",
        )

        assert response.status_code == 200

        boot_source_images_response = BootSourceAvailableImageListResponse(
            **response.json()
        )

        assert len(boot_source_images_response.items) == 2
        assert boot_source_images_response.total == 2
        assert boot_source_images_response.next is None

    async def test_get_boot_source_available_images_200_list_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        boot_source_id = 1

        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.get_by_id.return_value = TEST_BOOTSOURCE_1

        services_mock.boot_source_cache = Mock(BootSourceCacheService)
        services_mock.boot_source_cache.list_boot_source_cache_available_images.return_value = ListResult[
            BootSourceAvailableImage
        ](
            items=[
                BootSourceAvailableImage(
                    os="Ubuntu",
                    release="Noble",
                    release_title="24.04 LTS",
                    arch="amd64",
                    boot_source_id=boot_source_id,
                ),
                BootSourceAvailableImage(
                    os="Ubuntu",
                    release="Plucky",
                    release_title="25.04",
                    arch="amd64",
                    boot_source_id=boot_source_id,
                ),
            ],
            total=2,
        )

        response = await mocked_api_client_user.get(
            url=f"{self.BASE_PATH}/{boot_source_id}/available_images?size=1",
        )

        assert response.status_code == 200

        boot_source_images_response = BootSourceAvailableImageListResponse(
            **response.json()
        )

        assert len(boot_source_images_response.items) == 2
        assert boot_source_images_response.total == 2
        assert (
            boot_source_images_response.next
            == f"{self.BASE_PATH}/{boot_source_id}/available_images?page=2&size=1"
        )

    async def test_get_boot_source_available_images_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.get_by_id.side_effect = NotFoundException(
            details=[
                BaseExceptionDetail(
                    type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                    message="Resource with such identifiers does not exist.",
                )
            ]
        )

        response = await mocked_api_client_user.get(
            url=f"{self.BASE_PATH}/1/available_images",
        )

        assert response.status_code == 404


class TestBootSourceSelectionsApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/boot_sources"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=f"{self.BASE_PATH}/1/selections"),
            Endpoint(method="GET", path=f"{self.BASE_PATH}/1/selections/10"),
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="POST", path=f"{self.BASE_PATH}/1/selections"),
            Endpoint(method="PUT", path=f"{self.BASE_PATH}/1/selections/10"),
            Endpoint(
                method="DELETE", path=f"{self.BASE_PATH}/1/selections/10"
            ),
        ]

    async def test_list_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )
        services_mock.boot_source_selections.list.return_value = ListResult[
            BootSourceSelection
        ](items=[TEST_BOOTSOURCESELECTION], total=1)
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/{TEST_BOOTSOURCESELECTION.boot_source_id}/selections?page=1&size=1"
        )
        assert response.status_code == 200
        boot_source_selections_response = BootSourceSelectionListResponse(
            **response.json()
        )
        assert len(boot_source_selections_response.items) == 1
        assert boot_source_selections_response.total == 1
        assert boot_source_selections_response.next is None

    async def test_list_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )
        services_mock.boot_source_selections.list.return_value = ListResult[
            BootSourceSelection
        ](items=[TEST_BOOTSOURCESELECTION] * 2, total=2)

        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.list.return_value = ListResult[BootSource](
            items=[TEST_BOOTSOURCE_1, TEST_BOOTSOURCE_2], total=2
        )
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/{TEST_BOOTSOURCE_1.id}/selections?page=1&size=1"
        )
        assert response.status_code == 200
        boot_sources_response = BootSourceSelectionListResponse(
            **response.json()
        )
        assert len(boot_sources_response.items) == 2
        assert boot_sources_response.total == 2
        assert (
            boot_sources_response.next
            == f"{self.BASE_PATH}/{TEST_BOOTSOURCE_1.id}/selections?page=2&size=1"
        )

    async def test_get_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )
        services_mock.boot_source_selections.get_one.return_value = (
            TEST_BOOTSOURCESELECTION
        )

        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/{TEST_BOOTSOURCESELECTION.boot_source_id}/selections/{TEST_BOOTSOURCESELECTION.id}"
        )
        assert response.status_code == 200
        assert response.headers["ETag"]
        boot_source_selection_response = BootSourceSelectionResponse(
            **response.json()
        )
        assert boot_source_selection_response.id == TEST_BOOTSOURCESELECTION.id
        assert boot_source_selection_response.os == "ubuntu"
        assert boot_source_selection_response.release == "noble"
        assert boot_source_selection_response.arch == "amd64"
        assert boot_source_selection_response.boot_source_id == 12

    async def test_get_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )
        services_mock.boot_source_selections.get_one.return_value = None

        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/{TEST_BOOTSOURCESELECTION.boot_source_id}/selections/459"
        )
        assert response.status_code == 404
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404

    async def test_post_201(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.get_one.return_value = TEST_BOOTSOURCE_1

        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )
        services_mock.boot_source_selections.create.return_value = (
            TEST_BOOTSOURCESELECTION
        )
        create_request = {"os": "ubuntu", "release": "noble", "arch": "amd64"}
        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}/{TEST_BOOTSOURCE_1.id}/selections",
            json=jsonable_encoder(create_request),
        )
        assert response.status_code == 201
        response = BootSourceSelectionResponse(**response.json())
        assert response.os == "ubuntu"
        assert response.release == "noble"
        assert response.arch == "amd64"

    async def test_put_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ):
        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.get_by_id.return_value = TEST_BOOTSOURCE_1

        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )
        services_mock.boot_source_selections.get_by_id.return_value = (
            TEST_BOOTSOURCESELECTION
        )

        updated = TEST_BOOTSOURCESELECTION.copy()
        updated.arch = "arm64"
        services_mock.boot_source_selections.update_by_id.return_value = (
            updated
        )

        update_request = {"os": "ubuntu", "release": "noble", "arch": "arm64"}

        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/{TEST_BOOTSOURCE_1.id}/selections/{TEST_BOOTSOURCESELECTION.id}",
            json=jsonable_encoder(update_request),
        )

        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0

        updated_boot_source_selection_response = BootSourceSelectionResponse(
            **response.json()
        )
        assert updated_boot_source_selection_response.os == updated.os
        assert (
            updated_boot_source_selection_response.release == updated.release
        )
        assert updated_boot_source_selection_response.arch == updated.arch

    async def test_put_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ):
        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.get_by_id.return_value = TEST_BOOTSOURCE_1

        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )
        services_mock.boot_source_selections.get_by_id.return_value = (
            TEST_BOOTSOURCESELECTION
        )

        services_mock.boot_source_selections.update_by_id.side_effect = (
            NotFoundException()
        )

        update_request = {"os": "ubuntu", "release": "noble", "arch": "amd64"}

        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/{TEST_BOOTSOURCE_1.id}/selections/{TEST_BOOTSOURCESELECTION.id}",
            json=jsonable_encoder(update_request),
        )

        assert response.status_code == 404
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404

    async def test_delete_204(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )
        services_mock.boot_source_selections.delete_one.return_value = (
            TEST_BOOTSOURCESELECTION
        )
        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/{TEST_BOOTSOURCESELECTION.boot_source_id}/selections/{TEST_BOOTSOURCESELECTION.id}",
        )
        assert response.status_code == 204

    async def test_delete_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        boot_source_id = 196
        boot_source_selection_id = 10

        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )
        services_mock.boot_source_selections.delete_one.side_effect = (
            NotFoundException()
        )

        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/{boot_source_id}/selections/{boot_source_selection_id}",
        )
        assert response.status_code == 404
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())

        assert error_response.kind == "Error"
        assert error_response.code == 404

        services_mock.boot_source_selections.delete_one.assert_called_once_with(
            query=QuerySpec(
                where=BootSourceSelectionClauseFactory.and_clauses(
                    [
                        BootSourceSelectionClauseFactory.with_id(
                            boot_source_selection_id
                        ),
                        BootSourceSelectionClauseFactory.with_boot_source_id(
                            boot_source_id
                        ),
                    ]
                )
            ),
            etag_if_match=None,
        )

    async def test_sync_selection_starts_workflow(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )
        services_mock.boot_source_selections.get_one.return_value = (
            TEST_BOOTSOURCESELECTION
        )

        services_mock.temporal = Mock(TemporalService)
        services_mock.temporal.workflow_status.return_value = (
            WorkflowExecutionStatus.TERMINATED
        )

        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}/1/selections/1:sync",
        )

        assert response.status_code == 202

        json_response = response.json()
        assert json_response["monitor_url"] == (
            f"{self.BASE_PATH}/1/selections/1:status"
        )

        services_mock.temporal.workflow_status.assert_called_once_with(
            f"{SYNC_SELECTION_WORKFLOW_NAME}:1"
        )
        services_mock.temporal.register_workflow_call.assert_called_once_with(
            workflow_name=SYNC_SELECTION_WORKFLOW_NAME,
            workflow_id=f"{SYNC_SELECTION_WORKFLOW_NAME}:1",
            parameter=SyncSelectionParam(1),
            wait=False,
        )

    async def test_sync_selection_workflow_already_running(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )
        services_mock.boot_source_selections.get_one.return_value = (
            TEST_BOOTSOURCESELECTION
        )

        services_mock.temporal = Mock(TemporalService)
        services_mock.temporal.workflow_status.return_value = (
            WorkflowExecutionStatus.RUNNING
        )

        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}/1/selections/1:sync",
        )

        assert response.status_code == 303
        assert response.headers["Location"] == (
            f"{self.BASE_PATH}/1/selections/1:status"
        )

        services_mock.temporal.workflow_status.assert_called_once_with(
            f"{SYNC_SELECTION_WORKFLOW_NAME}:1"
        )
        services_mock.temporal.register_workflow_call.assert_not_called()

    async def test_stop_sync_selection_stops_workflow(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )
        services_mock.boot_source_selections.get_one.return_value = (
            TEST_BOOTSOURCESELECTION
        )

        temporal_client = Mock(Client)
        mock_handle = Mock(WorkflowHandle)
        temporal_client.get_workflow_handle.return_value = mock_handle
        services_mock.temporal = Mock(TemporalService)
        services_mock.temporal.workflow_status.return_value = (
            WorkflowExecutionStatus.RUNNING
        )
        services_mock.temporal.get_temporal_client.return_value = (
            temporal_client
        )

        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}/1/selections/1:stop_sync",
        )

        assert response.status_code == 202

        mock_handle.cancel.assert_awaited_once()

    async def test_stop_sync_selection_workflow_not_running(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )
        services_mock.boot_source_selections.get_one.return_value = (
            TEST_BOOTSOURCESELECTION
        )

        temporal_client = Mock(Client)
        services_mock.temporal = Mock(TemporalService)
        services_mock.temporal.workflow_status.return_value = (
            WorkflowExecutionStatus.COMPLETED
        )
        services_mock.temporal.get_temporal_client.return_value = (
            temporal_client
        )

        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}/1/selections/1:stop_sync",
        )

        assert response.status_code == 409
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.details[0].message == (
            "Selection is not being synchronized."
        )
        services_mock.temporal.get_temporal_client.assert_not_called()
