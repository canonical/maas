#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.requests.fabrics import FabricRequest
from maasapiserver.v3.api.public.models.responses.fabrics import (
    FabricResponse,
    FabricsListResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    BadRequestException,
    BaseExceptionDetail,
    NotFoundException,
    PreconditionFailedException,
)
from maasservicelayer.exceptions.constants import (
    CANNOT_DELETE_DEFAULT_FABRIC_VIOLATION_TYPE,
    ETAG_PRECONDITION_VIOLATION_TYPE,
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
    UNIQUE_CONSTRAINT_VIOLATION_TYPE,
)
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
        return [
            Endpoint(method="POST", path=self.BASE_PATH),
            Endpoint(method="PUT", path=f"{self.BASE_PATH}/1"),
            Endpoint(method="DELETE", path=f"{self.BASE_PATH}/1"),
        ]

    async def test_list_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.fabrics = Mock(FabricsService)
        services_mock.fabrics.list.return_value = ListResult[Fabric](
            items=[TEST_FABRIC], total=1
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        fabrics_response = FabricsListResponse(**response.json())
        assert len(fabrics_response.items) == 1
        assert fabrics_response.total == 1
        assert fabrics_response.next is None

    async def test_list_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.fabrics = Mock(FabricsService)
        services_mock.fabrics.list.return_value = ListResult[Fabric](
            items=[TEST_FABRIC_2], total=2
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        fabrics_response = FabricsListResponse(**response.json())
        assert len(fabrics_response.items) == 1
        assert fabrics_response.next == f"{self.BASE_PATH}?page=2&size=1"

    # GET /fabric/{ID}
    async def test_get_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.fabrics = Mock(FabricsService)
        services_mock.fabrics.get_by_id.return_value = TEST_FABRIC
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
            "vlans": {
                "href": f"{V3_API_PREFIX}/fabrics/{TEST_FABRIC.id}/vlans"
            },
            "_links": {"self": {"href": f"{self.BASE_PATH}/{TEST_FABRIC.id}"}},
        }

    async def test_get_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.fabrics = Mock(FabricsService)
        services_mock.fabrics.get_by_id.return_value = None
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
        services_mock.fabrics.get_by_id.side_effect = RequestValidationError(
            errors=[]
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/xyz")
        assert response.status_code == 422
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422

    # POST /fabric
    async def test_post_201(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        new_fabric = Fabric(
            id=1,
            name="new_fabric",
            description="new_description",
            class_type="new_class_type",
        )
        new_fabric_request = FabricRequest(
            name="new_fabric",
            description="new_description",
            class_type="new_class_type",
        )

        services_mock.fabrics = Mock(FabricsService)
        services_mock.fabrics.create.return_value = new_fabric

        response = await mocked_api_client_admin.post(
            self.BASE_PATH,
            json=jsonable_encoder(new_fabric_request),
        )

        assert response.status_code == 201
        assert len(response.headers["ETag"]) > 0

        fabric_response = FabricResponse(**response.json())

        assert fabric_response.id == new_fabric.id
        assert fabric_response.name == new_fabric.name
        assert fabric_response.description == new_fabric.description
        assert fabric_response.class_type == new_fabric.class_type

    async def test_post_409(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        new_fabric = Fabric(
            id=1,
            name="new_fabric",
            description="new_description",
            class_type="new_class_type",
        )
        new_fabric_request = FabricRequest(
            name="new_fabric",
            description="new_description",
            class_type="new_class_type",
        )

        services_mock.fabrics = Mock(FabricsService)
        services_mock.fabrics.create.side_effect = [
            new_fabric,
            AlreadyExistsException(
                details=[
                    BaseExceptionDetail(
                        type=UNIQUE_CONSTRAINT_VIOLATION_TYPE,
                        message="A resource with such identifiers already exist.",
                    )
                ]
            ),
        ]

        response = await mocked_api_client_admin.post(
            self.BASE_PATH,
            json=jsonable_encoder(new_fabric_request),
        )
        assert response.status_code == 201

        response = await mocked_api_client_admin.post(
            self.BASE_PATH,
            json=jsonable_encoder(new_fabric_request),
        )
        assert response.status_code == 409

        error_response = ErrorBodyResponse(**response.json())

        assert error_response.kind == "Error"
        assert error_response.code == 409

    async def test_post_422(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        new_fabric_request = {"name": None}

        services_mock.fabrics = Mock(FabricsService)
        services_mock.fabrics.create.return_value = None

        response = await mocked_api_client_admin.post(
            self.BASE_PATH,
            json=jsonable_encoder(new_fabric_request),
        )

        assert response.status_code == 422

        error_response = ErrorBodyResponse(**response.json())

        assert error_response.kind == "Error"
        assert error_response.code == 422

    # PUT /fabric/{fabric_id}
    async def test_put_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        updated_fabric = TEST_FABRIC
        updated_fabric.name = "updated_name"
        updated_fabric.description = "updated_description"
        updated_fabric.class_type = "updated_class_type"

        update_fabric_request = FabricRequest(
            name="updated_name",
            description="updated_description",
            class_type="updated_class_type",
        )

        services_mock.fabrics = Mock(FabricsService)
        services_mock.fabrics.update_by_id.return_value = updated_fabric

        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/{str(TEST_FABRIC.id)}",
            json=jsonable_encoder(update_fabric_request),
        )

        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0

        updated_fabric_response = FabricResponse(**response.json())

        assert updated_fabric_response.id == updated_fabric.id
        assert updated_fabric_response.name == updated_fabric.name
        assert (
            updated_fabric_response.description == updated_fabric.description
        )
        assert updated_fabric_response.class_type == updated_fabric.class_type

    async def test_put_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        update_fabric_request = FabricRequest(
            name="updated_name",
            description="updated_description",
            class_type="updated_class_type",
        )

        services_mock.fabrics = Mock(FabricsService)
        services_mock.fabrics.update_by_id.side_effect = NotFoundException(
            details=[
                BaseExceptionDetail(
                    type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                    message="Fabric with id 99 does not exist.",
                )
            ]
        )

        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/99",
            json=jsonable_encoder(update_fabric_request),
        )

        assert response.status_code == 404
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())

        assert error_response.kind == "Error"
        assert error_response.code == 404

    @pytest.mark.parametrize(
        "update_fabric_request",
        [
            {"name": None},
            {"name": "xyz$123"},
        ],
    )
    async def test_put_422(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
        update_fabric_request: dict[str, str],
    ) -> None:
        update_fabric_request = FabricRequest(
            name="updated_name",
            description="updated_description",
            class_type="updated_class_type",
        )

        services_mock.fabrics = Mock(FabricsService)
        services_mock.fabrics.update_by_id.side_effect = (
            RequestValidationError(errors=[])
        )

        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/1",
            json=jsonable_encoder(update_fabric_request),
        )

        assert response.status_code == 422
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())

        assert error_response.kind == "Error"
        assert error_response.code == 422

    async def test_delete_204(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.fabrics = Mock(FabricsService)
        services_mock.fabrics.delete_by_id.side_effect = None

        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/1",
        )

        assert response.status_code == 204

    async def test_delete_with_etag(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        fabric_id_to_delete = 1

        services_mock.fabrics = Mock(FabricsService)
        services_mock.fabrics.delete_by_id.side_effect = PreconditionFailedException(
            details=[
                BaseExceptionDetail(
                    type=ETAG_PRECONDITION_VIOLATION_TYPE,
                    message="The resource etag 'wrong_etag' did not match 'my_etag'.",
                )
            ]
        )

        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/{fabric_id_to_delete}",
            headers={"if-match": "wrong_etag"},
        )

        assert response.status_code == 412
        services_mock.fabrics.delete_by_id.assert_called_with(
            id=fabric_id_to_delete,
            etag_if_match="wrong_etag",
        )

    async def test_delete_not_default_fabric(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.fabrics = Mock(FabricsService)
        services_mock.fabrics.delete_by_id.side_effect = BadRequestException(
            details=[
                BaseExceptionDetail(
                    type=CANNOT_DELETE_DEFAULT_FABRIC_VIOLATION_TYPE,
                    message="The default Fabric (id=0) cannot be deleted.",
                )
            ]
        )

        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/0",
        )

        assert response.status_code == 400
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())

        assert error_response.kind == "Error"
        assert error_response.code == 400

    async def test_delete_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.fabrics = Mock(FabricsService)
        services_mock.fabrics.delete_by_id.side_effect = NotFoundException(
            details=[
                BaseExceptionDetail(
                    type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                    message="Fabric with id 99 does not exist.",
                )
            ]
        )

        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/99",
        )

        assert response.status_code == 404
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())

        assert error_response.kind == "Error"
        assert error_response.code == 404
