# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from base64 import b64decode, b64encode
from unittest.mock import Mock

from fastapi.encoders import jsonable_encoder
from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.requests.boot_sources import (
    BootSourceFetchRequest,
)
from maasapiserver.v3.api.public.models.responses.boot_source_selections import (
    BootSourceSelectionListResponse,
    BootSourceSelectionResponse,
)
from maasapiserver.v3.api.public.models.responses.boot_sources import (
    BootSourceFetchListResponse,
    BootSourceFetchResponse,
    BootSourceResponse,
    BootSourcesListResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
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
from maasservicelayer.models.bootsources import BootSource
from maasservicelayer.models.bootsourceselections import BootSourceSelection
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.boot_sources import BootSourcesService
from maasservicelayer.services.bootsourceselections import (
    BootSourceSelectionsService,
)
from maasservicelayer.utils.date import utcnow
from maasservicelayer.utils.images.boot_image_mapping import BootImageMapping
from maasservicelayer.utils.images.helpers import ImageSpec
from tests.fixtures.factories.boot_sources import set_resource
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

IMAGE_DESC_1 = {
    "content_id": "com.ubuntu.maas:stable:v3:download",
    "product_name": "com.ubuntu.maas.stable:v3:boot:16.04:s390x:ga-16.04",
    "version_name": "20210928",
    "path": "xenial/s390x/20210928/ga-16.04/generic/boot-initrd",
    "subarches": "generic,hwe-p,hwe-q,hwe-r,hwe-s,hwe-t,hwe-u,hwe-v,hwe-w,ga-16.04",
    "release_codename": "Xenial Xerus",
    "release_title": "16.04 LTS",
    "support_eol": "2021-04-21",
    "kflavor": "generic",
}
IMAGE_DESC_2 = {
    "content_id": "com.ubuntu.maas:stable:v3:download",
    "product_name": "com.ubuntu.maas.stable:v3:boot:24.10:s390x:ga-24.10",
    "version_name": "20250430",
    "path": "oracular/s390x/20250430/ga-24.10/generic/boot-initrd",
    "subarches": "generic,hwe-p,hwe-q,hwe-r,hwe-s,hwe-t,hwe-u,hwe-v,hwe-w,ga-16.04,ga-16.10,ga-17.04,ga-17.10,ga-18.04,ga-18.10,ga-19.04,ga-19.10,ga-20.04,ga-20.10,ga-21.04,ga-21.10,ga-22.04,ga-22.10,ga-23.04,ga-23.10,ga-24.04,ga-24.10",
    "release_codename": "Oracular Oriole",
    "release_title": "24.10",
    "support_eol": "2025-07-10",
    "kflavor": "generic",
}
IMAGE_DESC_3 = {
    "content_id": "com.ubuntu.maas:stable:v3:download",
    "product_name": "com.ubuntu.maas.stable:v3:boot:24.04:s390x:ga-24.04",
    "version_name": "20250424",
    "path": "noble/s390x/20250424/ga-24.04/generic/boot-initrd",
    "subarches": "generic,hwe-p,hwe-q,hwe-r,hwe-s,hwe-t,hwe-u,hwe-v,hwe-w,ga-16.04,ga-16.10,ga-17.04,ga-17.10,ga-18.04,ga-18.10,ga-19.04,ga-19.10,ga-20.04,ga-20.10,ga-21.04,ga-21.10,ga-22.04,ga-22.10,ga-23.04,ga-23.10,ga-24.04",
    "release_codename": "Noble Numbat",
    "release_title": "24.04 LTS",
    "support_eol": "2029-05-31",
    "kflavor": "generic",
}

TEST_BOOTSOURCESELECTION = BootSourceSelection(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    os="ubuntu",
    release="noble",
    arches=["amd64", "arm64"],
    subarches=["*"],
    labels=["*"],
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
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return []

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
        # Construct a BootImageMapping with some fake image specs.
        mapping = BootImageMapping()

        image_specs = [
            ImageSpec(
                os="ubuntu",
                arch="s390x",
                subarch="hwe-w",
                kflavor="generic",
                release="xenial",
                label="stable",
            ),
            ImageSpec(
                os="ubuntu",
                arch="s390x",
                subarch="hwe-w",
                kflavor="generic",
                release="oracular",
                label="stable",
            ),
            ImageSpec(
                os="ubuntu",
                arch="s390x",
                subarch="hwe-w",
                kflavor="generic",
                release="noble",
                label="stable",
            ),
        ]
        descriptions = [
            IMAGE_DESC_1,
            IMAGE_DESC_2,
            IMAGE_DESC_3,
        ]
        for spec, desc in zip(image_specs, descriptions):
            set_resource(mapping, spec, desc)

        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.fetch.return_value = mapping

        request = BootSourceFetchRequest(
            url="https://path/to/images/server",
        )

        response = await mocked_api_client_user.post(
            f"{self.BASE_PATH}:fetch", json=jsonable_encoder(request)
        )

        assert response.status_code == 200

        actual_response = BootSourceFetchListResponse(**response.json())

        expected_items = [
            BootSourceFetchResponse.from_model((spec, desc))
            for spec, desc in zip(image_specs, descriptions)
        ]

        for resp in actual_response.items:
            assert resp in expected_items

    async def test_fetch_encodes_keyring_data(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        images_server_url = "https://path/to/images/server"
        keyring_data_str = b64encode(b"keyring_data")

        expected_bytes = b64decode(keyring_data_str)

        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.fetch.return_value = BootImageMapping()

        request = BootSourceFetchRequest(
            url=images_server_url,
            keyring_data=keyring_data_str,
        )

        response = await mocked_api_client_user.post(
            url=f"{self.BASE_PATH}:fetch",
            json=jsonable_encoder(request),
        )

        assert response.status_code == 200

        services_mock.boot_sources.fetch.assert_called_once_with(
            images_server_url,
            keyring_path=None,
            keyring_data=expected_bytes,
            validate_products=True,
        )

    async def test_get_list_boot_source_selection_given_a_boot_source(
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
        assert not boot_source_selections_response.next

    async def test_get_boot_source_selection_given_a_boot_source(
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
        assert sorted(boot_source_selection_response.arches) == [
            "amd64",
            "arm64",
        ]
        assert boot_source_selection_response.subarches == ["*"]
        assert boot_source_selection_response.labels == ["*"]
        assert boot_source_selection_response.boot_source_id == 12
