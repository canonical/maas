#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Network
from unittest.mock import Mock

from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.requests.query import (
    TokenPaginationParams,
)
from maasapiserver.v3.api.public.models.requests.subnets import SubnetRequest
from maasapiserver.v3.api.public.models.responses.subnets import (
    SubnetsListResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.subnet import RdnsMode
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.models.vlans import Vlan
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.subnets import SubnetsService
from maasservicelayer.services.vlans import VlansService
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

TEST_SUBNET = Subnet(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    name="test_name",
    description="test_description",
    cidr=IPv4Network("10.10.10.10"),
    rdns_mode=RdnsMode.DEFAULT,
    gateway_ip=None,
    dns_servers=None,
    allow_dns=False,
    allow_proxy=True,
    active_discovery=False,
    managed=True,
    disabled_boot_architectures=[],
    vlan_id=1,
)

TEST_SUBNET_2 = Subnet(
    id=2,
    created=utcnow(),
    updated=utcnow(),
    name="test_name_2",
    description="test_description_2",
    cidr=IPv4Network("12.12.12.12"),
    rdns_mode=RdnsMode.DEFAULT,
    gateway_ip=None,
    dns_servers=None,
    allow_dns=False,
    allow_proxy=True,
    active_discovery=False,
    managed=True,
    disabled_boot_architectures=[],
    vlan_id=1,
)


class TestSubnetApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/fabrics/1/vlans/1/subnets"

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
        ]

    async def test_list_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.list.return_value = ListResult[Subnet](
            items=[TEST_SUBNET], next_token=None
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        subnets_response = SubnetsListResponse(**response.json())
        assert len(subnets_response.items) == 1
        assert subnets_response.next is None

    async def test_list_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.list.return_value = ListResult[Subnet](
            items=[TEST_SUBNET_2], next_token=str(TEST_SUBNET.id)
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        subnets_response = SubnetsListResponse(**response.json())
        assert len(subnets_response.items) == 1
        assert (
            subnets_response.next
            == f"{self.BASE_PATH}?{TokenPaginationParams.to_href_format(token=str(TEST_SUBNET.id), size='1')}"
        )

    # GET /subnets/{subnet_id}
    async def test_get_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.get_by_id.return_value = TEST_SUBNET
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/{TEST_SUBNET.id}"
        )
        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0
        assert response.json() == {
            "kind": "Subnet",
            "id": TEST_SUBNET.id,
            "name": TEST_SUBNET.name,
            "description": TEST_SUBNET.description,
            "cidr": str(TEST_SUBNET.cidr),
            "dns_servers": TEST_SUBNET.dns_servers,
            "gateway_ip": TEST_SUBNET.gateway_ip,
            "rdns_mode": TEST_SUBNET.rdns_mode,
            "allow_proxy": TEST_SUBNET.allow_proxy,
            "active_discovery": TEST_SUBNET.active_discovery,
            "managed": TEST_SUBNET.managed,
            "allow_dns": TEST_SUBNET.allow_dns,
            "disabled_boot_architectures": TEST_SUBNET.disabled_boot_architectures,
            # TODO: FastAPI response_model_exclude_none not working. We need to fix this before making the api public
            "_embedded": None,
            "vlan": {
                "href": f"{V3_API_PREFIX}/vlans?filter=subnet_id eq {TEST_SUBNET.id}"
            },
            "_links": {"self": {"href": f"{self.BASE_PATH}/{TEST_SUBNET.id}"}},
        }

    async def test_get_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.get_by_id.return_value = None
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
        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.get_by_id.side_effect = RequestValidationError(
            errors=[]
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/xyz")
        assert response.status_code == 422
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422

    async def test_post_201(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.create.return_value = TEST_SUBNET_2
        services_mock.vlans = Mock(VlansService)
        services_mock.vlans.get_by_id.return_value = Vlan(
            id=1,
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
        request = SubnetRequest(cidr=TEST_SUBNET_2.cidr)
        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=jsonable_encoder(request)
        )
        assert response.status_code == 201
        assert "ETag" in response.headers

    async def test_post_404_vlan_not_in_fabric(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.create.return_value = TEST_SUBNET_2
        services_mock.vlans = Mock(VlansService)
        services_mock.vlans.get_by_id.return_value = None
        request = SubnetRequest(cidr=TEST_SUBNET_2.cidr)
        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=jsonable_encoder(request)
        )
        assert response.status_code == 404

    async def test_put_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        modified_subnet = TEST_SUBNET_2
        modified_subnet.name = "modified"
        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.update.return_value = modified_subnet
        services_mock.vlans = Mock(VlansService)
        services_mock.vlans.get_by_id.return_value = Vlan(
            id=1,
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
        request = SubnetRequest(cidr=TEST_SUBNET_2.cidr, name="modified")
        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/1", json=jsonable_encoder(request)
        )
        assert response.status_code == 200

    async def test_put_404_vlan_not_in_fabric(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        modified_subnet = TEST_SUBNET_2
        modified_subnet.name = "modified"
        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.update.side_effect = NotFoundException()
        request = SubnetRequest(cidr=TEST_SUBNET_2.cidr, name="modified")
        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/1", json=jsonable_encoder(request)
        )
        assert response.status_code == 404
