# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

from fastapi.encoders import jsonable_encoder
from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.responses.racks import (
    RackListResponse,
    RackResponse,
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
from maasservicelayer.models.racks import Rack
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.racks import RacksService
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

TEST_RACK_1 = Rack(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    name="rack-001",
)
TEST_RACK_2 = Rack(
    id=2,
    created=utcnow(),
    updated=utcnow(),
    name="rack-002",
)


class TestRacksApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/racks"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=self.BASE_PATH),
            Endpoint(method="GET", path=f"{self.BASE_PATH}/1"),
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
        services_mock.racks = Mock(RacksService)
        services_mock.racks.list.return_value = ListResult[Rack](
            items=[TEST_RACK_1], total=1
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        racks_response = RackListResponse(**response.json())
        assert len(racks_response.items) == 1
        assert racks_response.total == 1
        assert racks_response.next is None

    async def test_list_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.racks = Mock(RacksService)
        services_mock.racks.list.return_value = ListResult[Rack](
            items=[TEST_RACK_1, TEST_RACK_2], total=2
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        racks_response = RackListResponse(**response.json())
        assert len(racks_response.items) == 2
        assert racks_response.total == 2
        assert racks_response.next == f"{self.BASE_PATH}?page=2&size=1"

    async def test_get_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ):
        services_mock.racks = Mock(RacksService)
        services_mock.racks.get_by_id.return_value = TEST_RACK_1
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/{TEST_RACK_1.id}"
        )
        assert response.status_code == 200
        assert response.headers["ETag"]
        rack_response = RackResponse(**response.json())
        assert rack_response.id == TEST_RACK_1.id

    async def test_get_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.racks = Mock(RacksService)
        services_mock.racks.get_by_id.return_value = None
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
        services_mock.racks = Mock(RacksService)
        services_mock.racks.get_by_id.return_value = TEST_RACK_1
        updated = TEST_RACK_1.copy()
        updated.name = "rack-1"
        services_mock.racks.update_by_id.return_value = updated

        update_request = {"name": "rack-1"}
        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/1",
            json=jsonable_encoder(update_request),
        )

        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0

        updated_rack_response = RackResponse(**response.json())
        assert updated_rack_response.name == updated.name

    async def test_put_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.racks = Mock(RacksService)
        services_mock.racks.update_by_id.side_effect = NotFoundException(
            details=[
                BaseExceptionDetail(
                    type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                    message="Resource with such identifiers does not exist.",
                )
            ]
        )

        update_request = {"name": "rack-1"}
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
        services_mock.racks = Mock(RacksService)
        services_mock.racks.create.return_value = TEST_RACK_1

        create_request = {
            "name": TEST_RACK_1.name,
        }
        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=jsonable_encoder(create_request)
        )
        assert response.status_code == 201
        assert response.headers["ETag"]
        rack_response = RackResponse(**response.json())

        assert rack_response.name == TEST_RACK_1.name
        assert (
            rack_response.hal_links.self.href
            == f"{self.BASE_PATH}/{rack_response.id}"
        )

    async def test_post_409(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.racks = Mock(RacksService)
        services_mock.racks.create.side_effect = AlreadyExistsException(
            details=[
                BaseExceptionDetail(
                    type=UNIQUE_CONSTRAINT_VIOLATION_TYPE,
                    message="A resource with such identifiers already exist.",
                )
            ]
        )
        create_request = {
            "name": TEST_RACK_1.name,
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
        services_mock.racks = Mock(RacksService)
        services_mock.racks.delete_by_id.side_effect = None
        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/100"
        )
        assert response.status_code == 204
