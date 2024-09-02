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
from maasapiserver.v3.api.public.models.responses.vlans import (
    VlansListResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.services import ServiceCollectionV3
from maasapiserver.v3.services.vlans import VlansService
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.vlans import Vlan
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

TEST_VLAN = Vlan(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    vid=1,
    name="test_vlan",
    description="test_description",
    mtu=1500,
    dhcp_on=False,
    external_dhcp=None,
    primary_rack_id=None,
    secondary_rack_id=None,
    relay_vlan=None,
    fabric_id=1,
    space_id=None,
)

TEST_VLAN_2 = Vlan(
    id=2,
    created=utcnow(),
    updated=utcnow(),
    vid=2,
    name="test_vlan_2",
    description="test_description_2",
    mtu=1500,
    dhcp_on=False,
    external_dhcp=None,
    primary_rack_id=None,
    secondary_rack_id=None,
    relay_vlan=None,
    fabric_id=2,
    space_id=None,
)


class TestVlanApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/vlans"

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
        services_mock.vlans = Mock(VlansService)
        services_mock.vlans.list = AsyncMock(
            return_value=ListResult[Vlan](items=[TEST_VLAN], next_token=None)
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        vlans_response = VlansListResponse(**response.json())
        assert len(vlans_response.items) == 1
        assert vlans_response.next is None

    async def test_list_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.vlans = Mock(VlansService)
        services_mock.vlans.list = AsyncMock(
            return_value=ListResult[Vlan](
                items=[TEST_VLAN_2], next_token=str(TEST_VLAN.id)
            )
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        vlans_response = VlansListResponse(**response.json())
        assert len(vlans_response.items) == 1
        assert (
            vlans_response.next
            == f"{self.BASE_PATH}?{TokenPaginationParams.to_href_format(token=str(TEST_VLAN.id), size='1')}"
        )

    # GET /vlans/{vlan_id}
    async def test_get_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.vlans = Mock(VlansService)
        services_mock.vlans.get_by_id = AsyncMock(return_value=TEST_VLAN)
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/{TEST_VLAN.id}"
        )
        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0
        assert response.json() == {
            "kind": "Vlan",
            "id": TEST_VLAN.id,
            "vid": TEST_VLAN.vid,
            "name": TEST_VLAN.name,
            "description": TEST_VLAN.description,
            "mtu": TEST_VLAN.mtu,
            "dhcp_on": TEST_VLAN.dhcp_on,
            "external_dhcp": TEST_VLAN.external_dhcp,
            "primary_rack": TEST_VLAN.primary_rack_id,
            "secondary_rack": TEST_VLAN.secondary_rack_id,
            "relay_vlan": TEST_VLAN.relay_vlan,
            # TODO: FastAPI response_model_exclude_none not working. We need to fix this before making the api public
            "_embedded": None,
            "fabric": {
                "href": f"{V3_API_PREFIX}/fabrics/{TEST_VLAN.fabric_id}"
            },
            "space": None,
            "_links": {"self": {"href": f"{self.BASE_PATH}/{TEST_VLAN.id}"}},
        }

    async def test_get_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.vlans = Mock(VlansService)
        services_mock.vlans.get_by_id = AsyncMock(return_value=None)
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
        services_mock.vlans = Mock(VlansService)
        services_mock.vlans.get_by_id = AsyncMock(
            side_effect=RequestValidationError(errors=[])
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/xyz")
        assert response.status_code == 422
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422
