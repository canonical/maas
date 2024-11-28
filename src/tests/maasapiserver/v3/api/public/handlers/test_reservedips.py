#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

from httpx import AsyncClient
import pytest

from maasapiserver.v3.api.public.models.requests.query import (
    TokenPaginationParams,
)
from maasapiserver.v3.api.public.models.responses.reservedips import (
    ReservedIPsListResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.reservedips import (
    ReservedIPsClauseFactory,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.reservedips import ReservedIP
from maasservicelayer.services import ReservedIPsService, ServiceCollectionV3
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

TEST_RESERVEDIP = ReservedIP(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    ip="10.0.0.1",
    mac_address="01:02:03:04:05:06",
    comment="test_comment",
    subnet_id=1,
)

TEST_RESERVEDIP_2 = ReservedIP(
    id=2,
    created=utcnow(),
    updated=utcnow(),
    ip="10.0.0.2",
    mac_address="02:02:03:04:05:06",
    comment="test_comment_2",
    subnet_id=1,
)


class TestReservedIPsApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/fabrics/1/vlans/1/subnets/1/reserved_ips"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=self.BASE_PATH),
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return []

    async def test_list_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.reservedips = Mock(ReservedIPsService)
        services_mock.reservedips.list.return_value = ListResult[ReservedIP](
            items=[TEST_RESERVEDIP], next_token=None
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        reservedips_response = ReservedIPsListResponse(**response.json())
        assert len(reservedips_response.items) == 1
        assert reservedips_response.next is None
        services_mock.reservedips.list.assert_called_once_with(
            token=None,
            size=1,
            query=QuerySpec(
                where=ReservedIPsClauseFactory.and_clauses(
                    [
                        ReservedIPsClauseFactory.with_fabric_id(1),
                        ReservedIPsClauseFactory.with_subnet_id(1),
                        ReservedIPsClauseFactory.with_vlan_id(1),
                    ]
                )
            ),
        )

    async def test_list_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.reservedips = Mock(ReservedIPsService)
        services_mock.reservedips.list.return_value = ListResult[ReservedIP](
            items=[TEST_RESERVEDIP_2], next_token=str(TEST_RESERVEDIP.id)
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        reservedips_response = ReservedIPsListResponse(**response.json())
        assert len(reservedips_response.items) == 1
        assert (
            reservedips_response.next
            == f"{self.BASE_PATH}?{TokenPaginationParams.to_href_format(token=str(TEST_RESERVEDIP.id), size='1')}"
        )
        services_mock.reservedips.list.assert_called_once_with(
            token=None,
            size=1,
            query=QuerySpec(
                where=ReservedIPsClauseFactory.and_clauses(
                    [
                        ReservedIPsClauseFactory.with_fabric_id(1),
                        ReservedIPsClauseFactory.with_subnet_id(1),
                        ReservedIPsClauseFactory.with_vlan_id(1),
                    ]
                )
            ),
        )
