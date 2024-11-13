#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

from httpx import AsyncClient
from netaddr import IPAddress
import pytest

from maasapiserver.v3.api.public.models.requests.query import (
    TokenPaginationParams,
)
from maasapiserver.v3.api.public.models.responses.interfaces import (
    InterfaceListResponse,
    InterfaceType,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.ipaddress import IpAddressType
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.interfaces import Interface, Link
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.interfaces import InterfacesService
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

LINK = Link(
    id=1,
    ip_type=IpAddressType.AUTO,
    ip_address=IPAddress(addr="10.10.10.10"),
    ip_subnet=0,
)

TEST_INTERFACE = Interface(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    name="test_interface",
    type=InterfaceType.PHYSICAL,
    mac_address="",
    link_connected=True,
    interface_speed=0,
    link_speed=0,
    sriov_max_vf=0,
    links=[LINK],
)

TEST_INTERFACE_2 = Interface(
    id=2,
    created=utcnow(),
    updated=utcnow(),
    name="test_interface_2",
    type=InterfaceType.PHYSICAL,
    mac_address="",
    link_connected=True,
    interface_speed=0,
    link_speed=0,
    sriov_max_vf=0,
    links=[LINK],
)


class TestInterfaceApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/machines/1/interfaces"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=f"{self.BASE_PATH}"),
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return []

    async def test_list_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.interfaces = Mock(InterfacesService)
        services_mock.interfaces.list.return_value = ListResult[Interface](
            items=[TEST_INTERFACE_2], next_token=str(TEST_INTERFACE.id)
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        interfaces_response = InterfaceListResponse(**response.json())
        assert len(interfaces_response.items) == 1
        assert (
            interfaces_response.next
            == f"{self.BASE_PATH}?{TokenPaginationParams.to_href_format(token=str(TEST_INTERFACE.id), size='1')}"
        )

    async def test_list_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.interfaces = Mock(InterfacesService)
        services_mock.interfaces.list.return_value = ListResult[Interface](
            items=[TEST_INTERFACE_2, TEST_INTERFACE], next_token=None
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        interfaces_response = InterfaceListResponse(**response.json())
        assert len(interfaces_response.items) == 2
        assert interfaces_response.next is None
