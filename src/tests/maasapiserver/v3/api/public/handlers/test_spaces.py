#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.requests.query import (
    TokenPaginationParams,
)
from maasapiserver.v3.api.public.models.requests.spaces import SpaceRequest
from maasapiserver.v3.api.public.models.responses.spaces import (
    SpaceResponse,
    SpacesListResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    BaseExceptionDetail,
    NotFoundException,
    PreconditionFailedException,
)
from maasservicelayer.exceptions.constants import (
    ETAG_PRECONDITION_VIOLATION_TYPE,
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
    UNIQUE_CONSTRAINT_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.spaces import Space
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.spaces import SpacesService
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

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
        return [
            Endpoint(method="PUT", path=f"{self.BASE_PATH}/1"),
            Endpoint(method="POST", path=self.BASE_PATH),
            Endpoint(method="DELETE", path=f"{self.BASE_PATH}/1"),
        ]

    async def test_list_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.spaces = Mock(SpacesService)
        services_mock.spaces.list.return_value = ListResult[Space](
            items=[TEST_SPACE], next_token=None
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
        services_mock.spaces.list.return_value = ListResult[Space](
            items=[TEST_SPACE_2], next_token=str(TEST_SPACE.id)
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
        services_mock.spaces.get_by_id.return_value = TEST_SPACE
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
        services_mock.spaces.get_by_id.return_value = None
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
        services_mock.spaces.get_by_id.return_value = RequestValidationError(
            errors=[]
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/xyz")
        assert response.status_code == 422
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422

    # POST /spaces
    async def test_post_201(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        create_space_request = SpaceRequest(
            name=TEST_SPACE.name,
            description=TEST_SPACE.description,
        )

        services_mock.spaces = Mock(SpacesService)
        services_mock.spaces.create.return_value = TEST_SPACE
        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}",
            json=jsonable_encoder(create_space_request),
        )

        assert response.status_code == 201
        assert len(response.headers["ETag"]) > 0

        space_response = SpaceResponse(**response.json())

        assert space_response.name == create_space_request.name
        assert space_response.description == create_space_request.description
        assert (
            space_response.vlans.href
            == f"{V3_API_PREFIX}/vlans?filter=space_id eq {space_response.id}"
        )
        assert (
            space_response.subnets.href
            == f"{V3_API_PREFIX}/subnets?filter=space_id eq {space_response.id}"
        )
        assert (
            space_response.hal_links.self.href
            == f"{self.BASE_PATH}/{space_response.id}"
        )

    async def test_post_409(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        create_space_request = SpaceRequest(
            name=TEST_SPACE.name,
            description=TEST_SPACE.description,
        )

        services_mock.spaces = Mock(SpacesService)
        services_mock.spaces.create.side_effect = [
            TEST_SPACE,
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
            f"{self.BASE_PATH}",
            json=jsonable_encoder(create_space_request),
        )
        assert response.status_code == 201

        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}",
            json=jsonable_encoder(create_space_request),
        )
        assert response.status_code == 409

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 409
        assert len(error_response.details) == 1
        assert error_response.details[0].type == "UniqueConstraintViolation"
        assert "already exist" in error_response.details[0].message

    async def test_post_422(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        create_space_request = {"name": ""}

        services_mock.spaces = Mock(SpacesService)
        services_mock.spaces.create.side_effect = ValueError(
            "Invalid entity name."
        )

        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}",
            json=jsonable_encoder(create_space_request),
        )
        assert response.status_code == 422

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422

    # PUT /spaces/{space_id}
    async def test_put_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        updated_space = TEST_SPACE
        updated_space.name = "updated_space"
        updated_space.description = "updated_description"

        update_space_request = SpaceRequest(
            name="updated_space",
            description="updated_description",
        )

        services_mock.spaces = Mock(SpacesService)
        services_mock.spaces.update_by_id.return_value = updated_space

        response = await mocked_api_client_admin.put(
            url=f"{self.BASE_PATH}/1",
            json=jsonable_encoder(update_space_request),
        )

        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0

        space_response = SpaceResponse(**response.json())

        assert space_response.id == updated_space.id
        assert space_response.name == updated_space.name
        assert space_response.description == updated_space.description

    async def test_put_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        update_space_request = SpaceRequest(
            name="updated_space",
            description="updated_description",
        )

        services_mock.spaces = Mock(SpacesService)
        services_mock.spaces.update_by_id.side_effect = NotFoundException(
            details=[
                BaseExceptionDetail(
                    type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                    message="Space with id 99 does not exist.",
                )
            ]
        )

        response = await mocked_api_client_admin.put(
            url=f"{self.BASE_PATH}/99",
            json=jsonable_encoder(update_space_request),
        )

        assert response.status_code == 404
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())

        assert error_response.kind == "Error"
        assert error_response.code == 404

    async def test_put_422_request_path(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        update_space_request = SpaceRequest(
            name="updated_space",
            description="updated_description",
        )

        services_mock.spaces = Mock(SpacesService)
        services_mock.spaces.update_by_id.side_effect = RequestValidationError(
            errors=[]
        )

        response = await mocked_api_client_admin.put(
            url=f"{self.BASE_PATH}/xyz",
            json=jsonable_encoder(update_space_request),
        )

        assert response.status_code == 422
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())

        assert error_response.kind == "Error"
        assert error_response.code == 422

    @pytest.mark.parametrize("update_space_request", [{"name": None}])
    async def test_put_422_request_body(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
        update_space_request: dict[str, str],
    ) -> None:
        services_mock.spaces = Mock(SpacesService)
        services_mock.spaces.update_by_id.side_effect = RequestValidationError(
            errors=[]
        )

        response = await mocked_api_client_admin.put(
            url=f"{self.BASE_PATH}/1",
            json=jsonable_encoder(update_space_request),
        )

        assert response.status_code == 422
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())

        assert error_response.kind == "Error"
        assert error_response.code == 422

    # DELETE /spaces/{space_id}
    async def test_delete_204(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.spaces = Mock(SpacesService)
        services_mock.spaces.delete_by_id.side_effect = None

        response = await mocked_api_client_admin.delete(f"{self.BASE_PATH}/1")

        assert response.status_code == 204

    async def test_delete_with_etag(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.spaces = Mock(SpacesService)
        services_mock.spaces.delete_by_id.side_effect = [
            PreconditionFailedException(
                details=[
                    BaseExceptionDetail(
                        type=ETAG_PRECONDITION_VIOLATION_TYPE,
                        message="The resource etag 'wrong_etag' did not match 'correct-etag'.",
                    )
                ]
            ),
            None,
        ]

        failed_response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/1",
            headers={"if-match": "wrong-etag"},
        )
        assert failed_response.status_code == 412
        error_response = ErrorBodyResponse(**failed_response.json())
        assert error_response.code == 412
        assert error_response.message == "A precondition has failed."
        assert (
            error_response.details[0].type == ETAG_PRECONDITION_VIOLATION_TYPE
        )

        success_response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/1",
            headers={"if-match": "correct-etag"},
        )
        assert success_response.status_code == 204
