#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address
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
        return [
            Endpoint(method="DELETE", path=f"{self.BASE_PATH}"),
            Endpoint(
                method="DELETE", path=f"{self.BASE_PATH}:clear_neighbours"
            ),
            Endpoint(method="DELETE", path=f"{self.BASE_PATH}:clear_dns"),
        ]

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

    async def test_clear_all_discoveries(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.discoveries = Mock(DiscoveriesService)
        services_mock.discoveries.clear_all.return_value = None

        response = await mocked_api_client_admin.delete(self.BASE_PATH)
        assert response.status_code == 204
        services_mock.discoveries.clear_all.assert_called_once()

    async def test_clear_all_discoveries_matching_ip_and_mac(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.discoveries = Mock(DiscoveriesService)
        services_mock.discoveries.clear_by_ip_and_mac.return_value = None

        ip = "10.0.0.1"
        mac = "aa:bb:cc:dd:ee:ff"

        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}?ip={ip}&mac={mac}"
        )
        assert response.status_code == 204
        services_mock.discoveries.clear_by_ip_and_mac.assert_called_once_with(
            ip=IPv4Address(ip), mac=MacAddress(mac)
        )

    @pytest.mark.parametrize(
        "ip,mac",
        [
            ("10.0.0.1", None),
            (None, "aa:bb:cc:dd:ee:ff"),
        ],
    )
    async def test_clear_all_discoveries_raises_with_missing_ip_or_mac(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
        ip: str | None,
        mac: str | None,
    ) -> None:
        services_mock.discoveries = Mock(DiscoveriesService)
        services_mock.discoveries.clear_by_ip_and_mac.return_value = None

        query = ""
        if ip:
            query = f"ip={ip}"
        if mac:
            query = f"mac={mac}"
        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}?{query}"
        )
        assert response.status_code == 422
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422

        assert error_response.details is not None
        msg = "Missing '{field}' query parameter. You must specify both IP and MAC to delete a specific neighbour."
        if ip:
            assert error_response.details[0].message == msg.format(field="mac")
            assert error_response.details[0].field == "mac"
        if mac:
            assert error_response.details[0].message == msg.format(field="ip")
            assert error_response.details[0].field == "ip"
        services_mock.discoveries.clear_by_ip_and_mac.assert_not_called()
        services_mock.discoveries.clear_all.assert_not_called()
