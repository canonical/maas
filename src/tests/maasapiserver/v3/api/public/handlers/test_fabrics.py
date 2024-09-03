#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

from fastapi.exceptions import RequestValidationError
from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.requests.query import (
    TokenPaginationParams,
)
from maasapiserver.v3.api.public.models.responses.fabrics import (
    FabricsListResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.fabrics import Fabric
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.fabrics import FabricsService
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

TEST_FABRIC = Fabric(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    name="test_fabric",
    description="test_description",
    class_type=None,
)
TEST_FABRIC_2 = Fabric(
    id=2,
    created=utcnow(),
    updated=utcnow(),
    name="test_fabric_2",
    description="test_description_2",
    class_type=None,
)


class TestFabricsApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/fabrics"

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
        services_mock.fabrics = Mock(FabricsService)
        services_mock.fabrics.list = AsyncMock(
            return_value=ListResult[Fabric](
                items=[TEST_FABRIC], next_token=None
            )
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        fabrics_response = FabricsListResponse(**response.json())
        assert len(fabrics_response.items) == 1
        assert fabrics_response.next is None

    async def test_list_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.fabrics = Mock(FabricsService)
        services_mock.fabrics.list = AsyncMock(
            return_value=ListResult[Fabric](
                items=[TEST_FABRIC_2], next_token=str(TEST_FABRIC.id)
            )
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        fabrics_response = FabricsListResponse(**response.json())
        assert len(fabrics_response.items) == 1
        assert (
            fabrics_response.next
            == f"{self.BASE_PATH}?{TokenPaginationParams.to_href_format(token=str(TEST_FABRIC.id), size='1')}"
        )

    # GET /fabric/{ID}
    async def test_get_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.fabrics = Mock(FabricsService)
        services_mock.fabrics.get_by_id = AsyncMock(return_value=TEST_FABRIC)
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/{TEST_FABRIC.id}"
        )
        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0
        assert response.json() == {
            "kind": "Fabric",
            "id": TEST_FABRIC.id,
            "name": TEST_FABRIC.name,
            "description": TEST_FABRIC.description,
            "class_type": TEST_FABRIC.class_type,
            # TODO: FastAPI response_model_exclude_none not working. We need to fix this before making the api public
            "_embedded": None,
            "vlans": {
                "href": f"{V3_API_PREFIX}/vlans?filter=fabric_id eq {TEST_FABRIC.id}"
            },
            "_links": {"self": {"href": f"{self.BASE_PATH}/{TEST_FABRIC.id}"}},
        }

    async def test_get_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.fabrics = Mock(FabricsService)
        services_mock.fabrics.get_by_id = AsyncMock(return_value=None)
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/100")
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
        services_mock.fabrics = Mock(FabricsService)
        services_mock.fabrics.get_by_id = AsyncMock(
            side_effect=RequestValidationError(errors=[])
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/xyz")
        assert response.status_code == 422
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422
