# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

from fastapi.exceptions import RequestValidationError
from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.common.utils.date import utcnow
from maasapiserver.v3.api.models.requests.query import TokenPaginationParams
from maasapiserver.v3.api.models.responses.spaces import SpacesListResponse
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.spaces import Space
from maasapiserver.v3.services import ServiceCollectionV3
from maasapiserver.v3.services.spaces import SpacesService
from tests.maasapiserver.v3.api.base import ApiCommonTests, Endpoint

TEST_SPACE = Space(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    name="test_space",
    description="test_description",
)

TEST_SPACE_2 = Space(
    id=2,
    created=utcnow(),
    updated=utcnow(),
    name="test_space_2",
    description="test_description_2",
)


class TestSpaceApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/spaces"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=self.BASE_PATH),
            Endpoint(method="GET", path=f"{self.BASE_PATH}/1"),
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return []

    async def test_list_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.spaces = Mock(SpacesService)
        services_mock.spaces.list = AsyncMock(
            return_value=ListResult[Space](items=[TEST_SPACE], next_token=None)
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        spaces_response = SpacesListResponse(**response.json())
        assert len(spaces_response.items) == 1
        assert spaces_response.next is None

    async def test_list_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.spaces = Mock(SpacesService)
        services_mock.spaces.list = AsyncMock(
            return_value=ListResult[Space](
                items=[TEST_SPACE_2], next_token=str(TEST_SPACE.id)
            )
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        spaces_response = SpacesListResponse(**response.json())
        assert len(spaces_response.items) == 1
        assert (
            spaces_response.next
            == f"{self.BASE_PATH}?{TokenPaginationParams.to_href_format(token=str(TEST_SPACE.id), size='1')}"
        )

    # GET /spaces/{space_id}
    async def test_get_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.spaces = Mock(SpacesService)
        services_mock.spaces.get_by_id = AsyncMock(return_value=TEST_SPACE)
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/{TEST_SPACE.id}"
        )
        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0
        assert response.json() == {
            "kind": "Space",
            "id": TEST_SPACE.id,
            "name": TEST_SPACE.name,
            "description": TEST_SPACE.description,
            # TODO: FastAPI response_model_exclude_none not working. We need to fix this before making the api public
            "_embedded": None,
            "vlans": {
                "href": f"{V3_API_PREFIX}/vlans?filter=space_id eq {TEST_SPACE.id}"
            },
            "subnets": {
                "href": f"{V3_API_PREFIX}/subnets?filter=space_id eq {TEST_SPACE.id}"
            },
            "_links": {"self": {"href": f"{self.BASE_PATH}/{TEST_SPACE.id}"}},
        }

    async def test_get_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.spaces = Mock(SpacesService)
        services_mock.spaces.get_by_id = AsyncMock(return_value=None)
        response = await mocked_api_client_user.get(
            f"{V3_API_PREFIX}/spaces/100"
        )
        assert response.status_code == 404
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404

    async def test_get_422(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.spaces = Mock(SpacesService)
        services_mock.spaces.get_by_id = AsyncMock(
            return_value=RequestValidationError(errors=[])
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/xyz")
        assert response.status_code == 422
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422
