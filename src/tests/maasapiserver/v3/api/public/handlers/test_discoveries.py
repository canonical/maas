#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.handlers.discoveries import (
    DiscoveriesListResponse,
)
from maasapiserver.v3.api.public.models.responses.discoveries import (
    DiscoveryResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.discoveries import Discovery
from maasservicelayer.models.fields import MacAddress
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.discoveries import DiscoveriesService
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

TEST_DISCOVERY = Discovery(
    id=1,
    discovery_id="MTAuMTAuMC4yOSwwMDoxNjozZToyOTphNTphMQ==",
    neighbour_id=1,
    ip="10.10.0.29",
    mac_address=MacAddress("aa:bb:cc:dd:ee:ff"),
    first_seen=utcnow(),
    last_seen=utcnow(),
    vid=1,
    observer_hostname="foo",
    observer_system_id="aabbcc",
    observer_id=1,
    observer_interface_id=1,
    observer_interface_name="eth0",
    mdns_id=1,
    hostname="bar",
    fabric_id=1,
    fabric_name="fabric-0",
    vlan_id=5001,
    is_external_dhcp=False,
    subnet_id=1,
    subnet_cidr="10.10.0.0/24",
    subnet_prefixlen=24,
)


class TestDiscoveriesApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/discoveries"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=f"{self.BASE_PATH}"),
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return []

    async def test_list_discoveries_one_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.discoveries = Mock(DiscoveriesService)
        services_mock.discoveries.list.return_value = ListResult[Discovery](
            items=[TEST_DISCOVERY], total=1
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=2")
        assert response.status_code == 200
        discoveries_response = DiscoveriesListResponse(**response.json())
        assert len(discoveries_response.items) == 1
        assert discoveries_response.total == 1
        assert discoveries_response.next is None

    async def test_list_discoveries_with_next_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.discoveries = Mock(DiscoveriesService)
        services_mock.discoveries.list.return_value = ListResult[Discovery](
            items=[TEST_DISCOVERY], total=2
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        discoveries_response = DiscoveriesListResponse(**response.json())
        assert len(discoveries_response.items) == 1
        assert discoveries_response.total == 2
        assert discoveries_response.next == f"{self.BASE_PATH}?page=2&size=1"

    async def test_get_by_id(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.discoveries = Mock(DiscoveriesService)
        services_mock.discoveries.get_by_id.return_value = TEST_DISCOVERY
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/1")
        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0
        discovery_response = DiscoveryResponse(**response.json())
        assert discovery_response.id == 1
        assert (
            discovery_response.discovery_id
            == "MTAuMTAuMC4yOSwwMDoxNjozZToyOTphNTphMQ=="
        )

    async def test_get_by_id_nonexist_id_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.discoveries = Mock(DiscoveriesService)
        services_mock.discoveries.get_by_id.return_value = None
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/100")
        assert response.status_code == 404
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404
