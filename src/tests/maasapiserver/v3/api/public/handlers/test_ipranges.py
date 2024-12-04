#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address
from unittest.mock import Mock

from fastapi.exceptions import RequestValidationError
from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.requests.query import (
    TokenPaginationParams,
)
from maasapiserver.v3.api.public.models.responses.ipranges import (
    IPRangeListResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.ipranges import IPRangeType
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.ipranges import IPRangeClauseFactory
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.ipranges import IPRange
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.ipranges import IPRangesService
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

now = utcnow()

TEST_IPRANGE = IPRange(
    id=1,
    created=now,
    updated=now,
    type=IPRangeType.RESERVED,
    start_ip=IPv4Address("10.10.0.1"),
    end_ip=IPv4Address("10.10.0.3"),
    subnet_id=1,
)

TEST_IPRANGE_2 = IPRange(
    id=2,
    created=now,
    updated=now,
    type=IPRangeType.RESERVED,
    start_ip=IPv4Address("10.10.0.5"),
    end_ip=IPv4Address("10.10.0.7"),
    subnet_id=1,
)


class TestIPRangesApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/fabrics/1/vlans/1/subnets/1/ipranges"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [Endpoint(method="GET", path=f"{self.BASE_PATH}/1")]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return []

    async def test_list_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.ipranges = Mock(IPRangesService)
        services_mock.ipranges.list.return_value = ListResult[IPRange](
            items=[TEST_IPRANGE], next_token=None
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        ipranges_response = IPRangeListResponse(**response.json())
        assert len(ipranges_response.items) == 1
        assert ipranges_response.next is None
        services_mock.ipranges.list.assert_called_once_with(
            token=None,
            size=1,
            query=QuerySpec(
                where=IPRangeClauseFactory.and_clauses(
                    [
                        IPRangeClauseFactory.with_subnet_id(1),
                        IPRangeClauseFactory.with_vlan_id(1),
                        IPRangeClauseFactory.with_fabric_id(1),
                    ]
                )
            ),
        )

    async def test_list_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.ipranges = Mock(IPRangesService)
        services_mock.ipranges.list.return_value = ListResult[IPRange](
            items=[TEST_IPRANGE_2], next_token=str(TEST_IPRANGE.id)
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        ipranges_response = IPRangeListResponse(**response.json())
        assert len(ipranges_response.items) == 1
        assert (
            ipranges_response.next
            == f"{self.BASE_PATH}?{TokenPaginationParams.to_href_format(token=str(TEST_IPRANGE.id), size='1')}"
        )
        services_mock.ipranges.list.assert_called_once_with(
            token=None,
            size=1,
            query=QuerySpec(
                where=IPRangeClauseFactory.and_clauses(
                    [
                        IPRangeClauseFactory.with_subnet_id(1),
                        IPRangeClauseFactory.with_vlan_id(1),
                        IPRangeClauseFactory.with_fabric_id(1),
                    ]
                )
            ),
        )

    # GET /ipranges/{ipranges_id}
    async def test_get_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.ipranges = Mock(IPRangesService)
        services_mock.ipranges.get_one.return_value = TEST_IPRANGE
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/{TEST_IPRANGE.id}"
        )
        print(self.BASE_PATH)
        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0
        assert response.json() == {
            "kind": "IPRange",
            "id": TEST_IPRANGE.id,
            "type": str(TEST_IPRANGE.type),
            "start_ip": str(TEST_IPRANGE.start_ip),
            "end_ip": str(TEST_IPRANGE.end_ip),
            "comment": None,
            # TODO: FastAPI response_model_exclude_none not working. We need to fix this before making the api public
            "_embedded": None,
            "_links": {
                "self": {"href": f"{self.BASE_PATH}/{TEST_IPRANGE.id}"}
            },
        }
        services_mock.ipranges.get_one.assert_called_once_with(
            QuerySpec(
                where=IPRangeClauseFactory.and_clauses(
                    [
                        IPRangeClauseFactory.with_id(TEST_IPRANGE.id),
                        IPRangeClauseFactory.with_subnet_id(1),
                        IPRangeClauseFactory.with_vlan_id(1),
                        IPRangeClauseFactory.with_fabric_id(1),
                    ]
                )
            ),
        )

    async def test_get_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.ipranges = Mock(IPRangesService)
        services_mock.ipranges.get_one.return_value = None
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
        services_mock.ipranges = Mock(IPRangesService)
        services_mock.ipranges.get_one.side_effect = RequestValidationError(
            errors=[]
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/xyz")
        assert response.status_code == 422
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422
