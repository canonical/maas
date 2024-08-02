from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from fastapi.encoders import jsonable_encoder
from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.common.models.constants import (
    CANNOT_DELETE_DEFAULT_ZONE_VIOLATION_TYPE,
)
from maasapiserver.v3.api.models.requests.zones import ZoneRequest
from maasapiserver.v3.api.models.responses.zones import (
    ZoneResponse,
    ZonesListResponse,
)
from maasapiserver.v3.auth.jwt import UserRole
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.models.zones import Zone
from tests.fixtures.factories.zone import create_test_zone
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasapiserver.v3.api.base import (
    ApiCommonTests,
    EndpointDetails,
    PaginatedEndpointTestConfig,
    SingleResourceTestConfig,
)


class TestZonesApi(ApiCommonTests):
    def get_endpoints_configuration(self) -> list[EndpointDetails]:

        async def create_pagination_test_resources(
            fixture: Fixture, size: int
        ) -> list[Zone]:
            # The default zone is created by the migrations
            created_zones = [
                Zone(
                    id=1,
                    name="default",
                    description="",
                    created=datetime.now(timezone.utc),
                    updated=datetime.now(timezone.utc),
                )
            ]
            for i in range(size - 1):
                created_zones.append(
                    await create_test_zone(
                        fixture, name=str(i), description=str(i)
                    )
                )
            return created_zones

        return [
            EndpointDetails(
                method="GET",
                path=f"{V3_API_PREFIX}/zones",
                user_role=UserRole.USER,
                resource_config=SingleResourceTestConfig[Zone, ZoneResponse](
                    response_type=ZoneResponse,
                    create_resource_routine=create_test_zone,
                ),
                pagination_config=PaginatedEndpointTestConfig[
                    Zone, ZonesListResponse
                ](
                    response_type=ZonesListResponse,
                    create_resources_routine=create_pagination_test_resources,
                ),
            ),
            EndpointDetails(
                method="POST",
                path=f"{V3_API_PREFIX}/zones",
                user_role=UserRole.ADMIN,
            ),
        ]

    # GET /zones with filters
    async def test_list_with_filters(
        self, authenticated_user_api_client_v3: AsyncClient, fixture: Fixture
    ) -> None:

        created_zone = await create_test_zone(fixture, name="test")

        response = await authenticated_user_api_client_v3.get(
            f"{V3_API_PREFIX}/zones?id={created_zone.id}"
        )
        assert response.status_code == 200
        zones_response = ZonesListResponse(**response.json())
        assert len(zones_response.items) == 1
        assert zones_response.items[0].id == created_zone.id

        # Get also the default zone
        response = await authenticated_user_api_client_v3.get(
            f"{V3_API_PREFIX}/zones?id={created_zone.id}&id=1"
        )
        assert response.status_code == 200
        zones_response = ZonesListResponse(**response.json())
        assert len(zones_response.items) == 2

        # Get also the default zone
        response = await authenticated_user_api_client_v3.get(
            f"{V3_API_PREFIX}/zones?id={created_zone.id}&id=1&size=1"
        )
        assert response.status_code == 200
        zones_response = ZonesListResponse(**response.json())
        assert len(zones_response.items) == 1
        assert zones_response.next is not None
        next_link_params = parse_qs(urlparse(zones_response.next).query)
        assert set(next_link_params["id"]) == {"1", str(created_zone.id)}
        assert next_link_params["size"][0] == "1"
        assert next_link_params["token"][0] == "1"

    # GET /zones/{zone_id}
    async def test_get_default(
        self, authenticated_user_api_client_v3: AsyncClient, fixture: Fixture
    ) -> None:
        # A "default" zone should be created at startup by the migration scripts.
        response = await authenticated_user_api_client_v3.get(
            f"{V3_API_PREFIX}/zones/1"
        )
        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0
        zone_response = ZoneResponse(**response.json())
        assert zone_response.id == 1
        assert zone_response.name == "default"

    # POST /zones
    async def test_post_201(
        self, authenticated_admin_api_client_v3: AsyncClient
    ) -> None:
        zone_request = ZoneRequest(name="myzone", description="my description")
        response = await authenticated_admin_api_client_v3.post(
            f"{V3_API_PREFIX}/zones", json=jsonable_encoder(zone_request)
        )
        assert response.status_code == 201
        assert len(response.headers["ETag"]) > 0
        zone_response = ZoneResponse(**response.json())
        assert zone_response.id > 1
        assert zone_response.name == zone_request.name
        assert zone_response.description == zone_request.description
        assert (
            zone_response.hal_links.self.href
            == f"{V3_API_PREFIX}/zones/{zone_response.id}"
        )

    async def test_post_default_parameters(
        self, authenticated_admin_api_client_v3: AsyncClient
    ) -> None:
        zone_request = ZoneRequest(name="myzone", description=None)
        response = await authenticated_admin_api_client_v3.post(
            f"{V3_API_PREFIX}/zones", json=jsonable_encoder(zone_request)
        )
        assert response.status_code == 201
        zone_response = ZoneResponse(**response.json())
        assert zone_response.description == ""

    async def test_post_409(
        self, authenticated_admin_api_client_v3: AsyncClient
    ) -> None:
        zone_request = ZoneRequest(name="myzone", description=None)
        response = await authenticated_admin_api_client_v3.post(
            f"{V3_API_PREFIX}/zones", json=jsonable_encoder(zone_request)
        )
        assert response.status_code == 201

        response = await authenticated_admin_api_client_v3.post(
            f"{V3_API_PREFIX}/zones", json=jsonable_encoder(zone_request)
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
        authenticated_admin_api_client_v3: AsyncClient,
        zone_request: dict[str, str],
    ) -> None:
        response = await authenticated_admin_api_client_v3.post(
            f"{V3_API_PREFIX}/zones", json=zone_request
        )
        assert response.status_code == 422

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422

    async def test_delete_default_zone(
        self, authenticated_admin_api_client_v3: AsyncClient, fixture: Fixture
    ) -> None:
        response = await authenticated_admin_api_client_v3.delete(
            f"{V3_API_PREFIX}/zones/1"
        )
        error_response = ErrorBodyResponse(**response.json())
        assert response.status_code == 400
        assert error_response.code == 400
        assert error_response.message == "Bad request."
        assert (
            error_response.details[0].type
            == CANNOT_DELETE_DEFAULT_ZONE_VIOLATION_TYPE
        )
