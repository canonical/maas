# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv4Network
from unittest.mock import Mock

from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.requests.staticroutes import (
    StaticRouteRequest,
)
from maasapiserver.v3.api.public.models.responses.staticroutes import (
    StaticRouteResponse,
    StaticRoutesListResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.subnet import RdnsMode
from maasservicelayer.builders.staticroutes import StaticRouteBuilder
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.staticroutes import (
    StaticRoutesClauseFactory,
)
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    PreconditionFailedException,
)
from maasservicelayer.exceptions.constants import (
    ETAG_PRECONDITION_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.staticroutes import StaticRoute
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services import (
    ReservedIPsService,
    ServiceCollectionV3,
    StaticRoutesService,
)
from maasservicelayer.services.subnets import SubnetsService
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

TEST_STATICROUTE = StaticRoute(
    id=0,
    created=utcnow(),
    updated=utcnow(),
    gateway_ip=IPv4Address("10.0.0.1"),
    destination_id=2,
    source_id=1,
    metric=0,
)

TEST_SOURCE_SUBNET = Subnet(
    id=1,
    cidr=IPv4Network("10.0.0.0/24"),
    rdns_mode=RdnsMode.DEFAULT,
    allow_dns=True,
    allow_proxy=True,
    active_discovery=True,
    managed=True,
    disabled_boot_architectures=[],
    vlan_id=1,
)

TEST_DESTINATION_SUBNET = Subnet(
    id=2,
    cidr=IPv4Network("20.0.0.0/24"),
    rdns_mode=RdnsMode.DEFAULT,
    allow_dns=True,
    allow_proxy=True,
    active_discovery=True,
    managed=True,
    disabled_boot_architectures=[],
    vlan_id=1,
)


class TestStaticRoutesApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/fabrics/1/vlans/1/subnets/1/staticroutes"

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
            Endpoint(method="DELETE", path=f"{self.BASE_PATH}/1"),
        ]

    async def test_list_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.staticroutes = Mock(StaticRoutesService)
        services_mock.staticroutes.list.return_value = ListResult[StaticRoute](
            items=[TEST_STATICROUTE], total=1
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        staticroutes_response = StaticRoutesListResponse(**response.json())
        assert len(staticroutes_response.items) == 1
        assert staticroutes_response.total == 1
        assert staticroutes_response.next is None
        services_mock.staticroutes.list.assert_called_once_with(
            page=1,
            size=1,
            query=QuerySpec(
                where=StaticRoutesClauseFactory.and_clauses(
                    [
                        StaticRoutesClauseFactory.with_source_id(1),
                        StaticRoutesClauseFactory.with_vlan_id(1),
                        StaticRoutesClauseFactory.with_fabric_id(1),
                    ]
                )
            ),
        )

    async def test_list_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.staticroutes = Mock(StaticRoutesService)
        services_mock.staticroutes.list.return_value = ListResult[StaticRoute](
            items=[TEST_STATICROUTE], total=2
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        staticroutes_response = StaticRoutesListResponse(**response.json())
        assert len(staticroutes_response.items) == 1
        assert staticroutes_response.total == 2
        assert staticroutes_response.next == f"{self.BASE_PATH}?page=2&size=1"
        services_mock.staticroutes.list.assert_called_once_with(
            page=1,
            size=1,
            query=QuerySpec(
                where=StaticRoutesClauseFactory.and_clauses(
                    [
                        StaticRoutesClauseFactory.with_source_id(1),
                        StaticRoutesClauseFactory.with_vlan_id(1),
                        StaticRoutesClauseFactory.with_fabric_id(1),
                    ]
                )
            ),
        )

    async def test_get_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.staticroutes = Mock(StaticRoutesService)
        services_mock.staticroutes.get_one.return_value = TEST_STATICROUTE
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/{TEST_STATICROUTE.id}"
        )
        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0
        assert response.json() == {
            "kind": "StaticRoute",
            "id": TEST_STATICROUTE.id,
            "gateway_ip": str(TEST_STATICROUTE.gateway_ip),
            "destination_id": TEST_STATICROUTE.destination_id,
            "metric": TEST_STATICROUTE.metric,
            "_links": {
                "self": {"href": f"{self.BASE_PATH}/{TEST_STATICROUTE.id}"}
            },
        }
        services_mock.staticroutes.get_one.assert_called_once_with(
            query=QuerySpec(
                where=StaticRoutesClauseFactory.and_clauses(
                    [
                        StaticRoutesClauseFactory.with_id(TEST_STATICROUTE.id),
                        StaticRoutesClauseFactory.with_source_id(1),
                        StaticRoutesClauseFactory.with_vlan_id(1),
                        StaticRoutesClauseFactory.with_fabric_id(1),
                    ]
                )
            )
        )

    async def test_get_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.staticroutes = Mock(StaticRoutesService)
        services_mock.staticroutes.get_one.return_value = None
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
        services_mock.staticroutes = Mock(StaticRoutesService)
        services_mock.staticroutes.get_one.return_value = (
            RequestValidationError(errors=[])
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
        services_mock.staticroutes = Mock(StaticRoutesService)
        services_mock.staticroutes.create.return_value = TEST_STATICROUTE
        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.get_one.side_effect = [
            TEST_SOURCE_SUBNET,
            TEST_DESTINATION_SUBNET,
        ]
        staticroute_request = StaticRouteRequest(
            gateway_ip=TEST_STATICROUTE.gateway_ip,
            metric=TEST_STATICROUTE.metric,
            destination_id=TEST_STATICROUTE.destination_id,
        )
        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}", json=jsonable_encoder(staticroute_request)
        )
        assert response.status_code == 201
        staticroutes_response = StaticRouteResponse(**response.json())
        assert staticroutes_response.id == TEST_STATICROUTE.id
        assert staticroutes_response.gateway_ip == TEST_STATICROUTE.gateway_ip
        assert staticroutes_response.metric == TEST_STATICROUTE.metric
        assert (
            staticroutes_response.destination_id
            == TEST_STATICROUTE.destination_id
        )
        assert "ETag" in response.headers
        assert len(response.headers["ETag"]) > 0
        services_mock.staticroutes.create.assert_called_once_with(
            StaticRouteBuilder(
                gateway_ip=TEST_STATICROUTE.gateway_ip,
                metric=TEST_STATICROUTE.metric,
                source_id=TEST_SOURCE_SUBNET.id,
                destination_id=TEST_STATICROUTE.destination_id,
            )
        )

    async def test_post_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.staticroutes = Mock(StaticRoutesService)
        services_mock.staticroutes.create.return_value = TEST_STATICROUTE
        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.get_one.return_value = None
        staticroute_request = StaticRouteRequest(
            gateway_ip=TEST_STATICROUTE.gateway_ip,
            metric=TEST_STATICROUTE.metric,
            destination_id=TEST_STATICROUTE.destination_id,
        )
        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}", json=jsonable_encoder(staticroute_request)
        )
        assert response.status_code == 404

    async def test_put_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        updated_staticroute = TEST_STATICROUTE
        updated_staticroute.gateway_ip = IPv4Address("10.0.0.2")
        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.get_one.side_effect = [
            TEST_SOURCE_SUBNET,
            TEST_DESTINATION_SUBNET,
        ]
        services_mock.staticroutes = Mock(StaticRoutesService)
        services_mock.staticroutes.update_one.return_value = (
            updated_staticroute
        )
        staticroute_request = StaticRouteRequest(
            gateway_ip="10.0.0.2",
            metric=TEST_STATICROUTE.metric,
            destination_id=TEST_STATICROUTE.destination_id,
        )
        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/{TEST_STATICROUTE.id}",
            json=jsonable_encoder(staticroute_request),
        )
        assert response.status_code == 200
        assert "ETag" in response.headers
        assert len(response.headers["ETag"]) > 0
        assert response.json()["gateway_ip"] == "10.0.0.2"

        services_mock.staticroutes.update_one.assert_called_once_with(
            query=QuerySpec(
                where=StaticRoutesClauseFactory.and_clauses(
                    [
                        StaticRoutesClauseFactory.with_id(TEST_STATICROUTE.id),
                        StaticRoutesClauseFactory.with_source_id(
                            TEST_SOURCE_SUBNET.id
                        ),
                    ]
                )
            ),
            builder=StaticRouteBuilder(
                gateway_ip=IPv4Address("10.0.0.2"),
                source_id=TEST_STATICROUTE.source_id,
                metric=TEST_STATICROUTE.metric,
                destination_id=TEST_STATICROUTE.destination_id,
            ),
        )

    async def test_put_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.subnets = Mock(ReservedIPsService)
        services_mock.subnets.get_one.return_value = None
        staticroute_request = StaticRouteRequest(
            gateway_ip="10.0.0.2",
            metric=TEST_STATICROUTE.metric,
            destination_id=TEST_STATICROUTE.destination_id,
        )
        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/{TEST_STATICROUTE.id}",
            json=jsonable_encoder(staticroute_request),
        )
        assert response.status_code == 404

    async def test_delete(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.staticroutes = Mock(StaticRoutesService)
        services_mock.staticroutes.get_one.return_value = TEST_STATICROUTE
        services_mock.staticroutes.delete_one.return_value = TEST_STATICROUTE
        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/{TEST_STATICROUTE.id}"
        )
        assert response.status_code == 204
        services_mock.staticroutes.get_one.assert_called_with(
            query=QuerySpec(
                where=StaticRoutesClauseFactory.and_clauses(
                    [
                        StaticRoutesClauseFactory.with_id(TEST_STATICROUTE.id),
                        StaticRoutesClauseFactory.with_source_id(1),
                        StaticRoutesClauseFactory.with_vlan_id(1),
                        StaticRoutesClauseFactory.with_fabric_id(1),
                    ]
                )
            )
        )
        services_mock.staticroutes.delete_by_id.assert_called_with(
            TEST_STATICROUTE.id,
            etag_if_match=None,
        )

    async def test_delete_with_etag(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.staticroutes = Mock(StaticRoutesService)
        services_mock.staticroutes.get_one.return_value = TEST_STATICROUTE
        services_mock.staticroutes.delete_by_id.side_effect = PreconditionFailedException(
            details=[
                BaseExceptionDetail(
                    type=ETAG_PRECONDITION_VIOLATION_TYPE,
                    message="The resource etag 'wrong_etag' did not match 'my_etag'.",
                )
            ]
        )

        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/{TEST_STATICROUTE.id}",
            headers={"if-match": "wrong_etag"},
        )
        assert response.status_code == 412
        services_mock.staticroutes.get_one.assert_called_with(
            query=QuerySpec(
                where=StaticRoutesClauseFactory.and_clauses(
                    [
                        StaticRoutesClauseFactory.with_id(TEST_STATICROUTE.id),
                        StaticRoutesClauseFactory.with_source_id(1),
                        StaticRoutesClauseFactory.with_vlan_id(1),
                        StaticRoutesClauseFactory.with_fabric_id(1),
                    ]
                )
            )
        )
        services_mock.staticroutes.delete_by_id.assert_called_with(
            TEST_STATICROUTE.id,
            etag_if_match="wrong_etag",
        )
