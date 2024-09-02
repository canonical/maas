#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlparse

from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.requests.query import (
    TokenPaginationParams,
)
from maasapiserver.v3.api.public.models.requests.zones import ZoneRequest
from maasapiserver.v3.api.public.models.responses.zones import (
    ZoneResponse,
    ZonesListResponse,
)
from maasapiserver.v3.constants import DEFAULT_ZONE_NAME, V3_API_PREFIX
from maasapiserver.v3.services import ServiceCollectionV3
from maasapiserver.v3.services.zones import ZonesService
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    BadRequestException,
    BaseExceptionDetail,
    PreconditionFailedException,
)
from maasservicelayer.exceptions.constants import (
    CANNOT_DELETE_DEFAULT_ZONE_VIOLATION_TYPE,
    ETAG_PRECONDITION_VIOLATION_TYPE,
    UNIQUE_CONSTRAINT_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.zones import Zone
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

DEFAULT_ZONE = Zone(
    id=1,
    name=DEFAULT_ZONE_NAME,
    description="",
    created=utcnow(),
    updated=utcnow(),
)
TEST_ZONE = Zone(
    id=4,
    name="test_zone",
    description="test_description",
    created=utcnow(),
    updated=utcnow(),
)


class TestZonesApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/zones"
    DEFAULT_ZONE_PATH = f"{BASE_PATH}/1"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=f"{self.BASE_PATH}"),
            Endpoint(method="GET", path=f"{self.BASE_PATH}/2"),
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="POST", path=f"{self.BASE_PATH}"),
            Endpoint(method="DELETE", path=f"{self.BASE_PATH}/2"),
        ]

    async def test_list_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.zones = Mock(ZonesService)
        services_mock.zones.list = AsyncMock(
            return_value=ListResult[Zone](
                items=[TEST_ZONE], next_token=str(DEFAULT_ZONE.id)
            )
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        zones_response = ZonesListResponse(**response.json())
        assert len(zones_response.items) == 1
        assert (
            zones_response.next
            == f"{self.BASE_PATH}?{TokenPaginationParams.to_href_format(token=str(DEFAULT_ZONE.id), size='1')}"
        )

    async def test_list_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.zones = Mock(ZonesService)
        services_mock.zones.list = AsyncMock(
            return_value=ListResult[Zone](
                items=[DEFAULT_ZONE, TEST_ZONE], next_token=None
            )
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        zones_response = ZonesListResponse(**response.json())
        assert len(zones_response.items) == 2
        assert zones_response.next is None

    # GET /zones with filters
    async def test_list_with_filters(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:

        services_mock.zones = Mock(ZonesService)
        services_mock.zones.list = AsyncMock(
            return_value=ListResult[Zone](
                items=[TEST_ZONE], next_token=str(DEFAULT_ZONE.id)
            )
        )

        # Get also the default zone
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}?id=1&id=4&size=1"
        )
        assert response.status_code == 200
        zones_response = ZonesListResponse(**response.json())
        assert len(zones_response.items) == 1

        assert zones_response.next is not None
        next_link_params = parse_qs(urlparse(zones_response.next).query)
        assert set(next_link_params["id"]) == {
            str(DEFAULT_ZONE.id),
            str(TEST_ZONE.id),
        }
        assert next_link_params["size"][0] == "1"
        assert next_link_params["token"][0] == str(DEFAULT_ZONE.id)

    # GET /zones/{zone_id}
    async def test_get_default(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        # A "default" zone should be created at startup by the migration scripts.
        services_mock.zones = Mock(ZonesService)
        services_mock.zones.get_by_id = AsyncMock(return_value=DEFAULT_ZONE)
        response = await mocked_api_client_user.get(self.DEFAULT_ZONE_PATH)
        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0
        zone_response = ZoneResponse(**response.json())
        assert zone_response.id == 1
        assert zone_response.name == DEFAULT_ZONE_NAME

    async def test_get_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.zones = Mock(ZonesService)
        services_mock.zones.get_by_id = AsyncMock(return_value=None)
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
        services_mock.zones = Mock(ZonesService)
        services_mock.zones.get_by_id = AsyncMock(
            side_effect=RequestValidationError(errors=[])
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/xyz")
        assert response.status_code == 422
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422

    # POST /zones
    async def test_post_201(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        zone_request = ZoneRequest(
            name=TEST_ZONE.name, description=TEST_ZONE.description
        )
        services_mock.zones = Mock(ZonesService)
        services_mock.zones.create = AsyncMock(return_value=TEST_ZONE)
        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=jsonable_encoder(zone_request)
        )
        assert response.status_code == 201
        assert len(response.headers["ETag"]) > 0
        zone_response = ZoneResponse(**response.json())
        assert zone_response.id > 1
        assert zone_response.name == zone_request.name
        assert zone_response.description == zone_request.description
        assert (
            zone_response.hal_links.self.href
            == f"{self.BASE_PATH}/{zone_response.id}"
        )

    async def test_post_default_parameters(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        zone_request = ZoneRequest(name="myzone", description=None)
        services_mock.zones = Mock(ZonesService)
        services_mock.zones.create = AsyncMock(
            return_value=Zone(
                id=2,
                name="myzone",
                description="",
                created=utcnow(),
                updated=utcnow(),
            )
        )
        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=jsonable_encoder(zone_request)
        )
        assert response.status_code == 201
        zone_response = ZoneResponse(**response.json())
        assert zone_response.description == ""

    async def test_post_409(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        zone_request = ZoneRequest(name="myzone", description=None)
        services_mock.zones = Mock(ZonesService)
        services_mock.zones.create = AsyncMock(
            side_effect=[
                TEST_ZONE,
                AlreadyExistsException(
                    details=[
                        BaseExceptionDetail(
                            type=UNIQUE_CONSTRAINT_VIOLATION_TYPE,
                            message="A resource with such identifiers already exist.",
                        )
                    ]
                ),
            ]
        )
        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=jsonable_encoder(zone_request)
        )
        assert response.status_code == 201

        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=jsonable_encoder(zone_request)
        )
        assert response.status_code == 409

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 409
        assert len(error_response.details) == 1
        assert error_response.details[0].type == "UniqueConstraintViolation"
        assert "already exist" in error_response.details[0].message

    @pytest.mark.parametrize(
        "zone_request",
        [
            {"name": ""},
            {"name": "-myzone"},
            {"name": "Hello$Zone"},
        ],
    )
    async def test_post_422(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
        zone_request: dict[str, str],
    ) -> None:
        services_mock.zones = Mock(ZonesService)
        services_mock.zones.create = AsyncMock(
            side_effect=ValueError("Invalid entity name.")
        )
        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=zone_request
        )
        assert response.status_code == 422

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422

    # DELETE /zones/{id}
    async def test_delete_default_zone(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.zones = Mock(ZonesService)
        services_mock.zones.delete = AsyncMock(
            side_effect=BadRequestException(
                details=[
                    BaseExceptionDetail(
                        type=CANNOT_DELETE_DEFAULT_ZONE_VIOLATION_TYPE,
                        message="The default zone can not be deleted.",
                    )
                ]
            )
        )

        response = await mocked_api_client_admin.delete(self.DEFAULT_ZONE_PATH)

        error_response = ErrorBodyResponse(**response.json())
        assert response.status_code == 400
        assert error_response.code == 400
        assert error_response.message == "Bad request."
        assert (
            error_response.details[0].type
            == CANNOT_DELETE_DEFAULT_ZONE_VIOLATION_TYPE
        )

    async def test_delete_resource(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.zones = Mock(ZonesService)
        services_mock.zones.delete = AsyncMock(side_effect=None)
        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/100"
        )
        assert response.status_code == 204

    async def test_delete_with_etag(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.zones = Mock(ZonesService)
        services_mock.zones.delete = AsyncMock(
            side_effect=[
                PreconditionFailedException(
                    details=[
                        BaseExceptionDetail(
                            type=ETAG_PRECONDITION_VIOLATION_TYPE,
                            message="The resource etag 'wrong_etag' did not match 'my_etag'.",
                        )
                    ]
                ),
                None,
            ]
        )

        failed_response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/100",
            headers={"if-match": "wrong_etag"},
        )
        assert failed_response.status_code == 412
        error_response = ErrorBodyResponse(**failed_response.json())
        assert error_response.code == 412
        assert error_response.message == "A precondition has failed."
        assert (
            error_response.details[0].type == ETAG_PRECONDITION_VIOLATION_TYPE
        )

        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/100",
            headers={"if-match": "my_etag"},
        )
        assert response.status_code == 204
