#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv4Network
from unittest.mock import Mock

from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.requests.reservedips import (
    ReservedIPCreateRequest,
    ReservedIPUpdateRequest,
)
from maasapiserver.v3.api.public.models.responses.reservedips import (
    ReservedIPsListResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.subnet import RdnsMode
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.reservedips import (
    ReservedIPsClauseFactory,
)
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    PreconditionFailedException,
)
from maasservicelayer.exceptions.constants import (
    ETAG_PRECONDITION_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.fields import MacAddress
from maasservicelayer.models.reservedips import ReservedIP
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services import ReservedIPsService, ServiceCollectionV3
from maasservicelayer.services.ipranges import IPRangesService
from maasservicelayer.services.staticipaddress import StaticIPAddressService
from maasservicelayer.services.subnets import SubnetsService
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

TEST_RESERVEDIP = ReservedIP(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    ip=IPv4Address("10.0.0.1"),
    mac_address=MacAddress("01:02:03:04:05:06"),
    comment="test_comment",
    subnet_id=1,
)

TEST_RESERVEDIP_2 = ReservedIP(
    id=2,
    created=utcnow(),
    updated=utcnow(),
    ip=IPv4Address("10.0.0.2"),
    mac_address=MacAddress("02:02:03:04:05:06"),
    comment="test_comment_2",
    subnet_id=1,
)


class TestReservedIPsApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/fabrics/1/vlans/1/subnets/1/reserved_ips"

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
        services_mock.reservedips = Mock(ReservedIPsService)
        services_mock.reservedips.list.return_value = ListResult[ReservedIP](
            items=[TEST_RESERVEDIP], total=1
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        reservedips_response = ReservedIPsListResponse(**response.json())
        assert len(reservedips_response.items) == 1
        assert reservedips_response.total == 1
        assert reservedips_response.next is None
        services_mock.reservedips.list.assert_called_once_with(
            page=1,
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
            items=[TEST_RESERVEDIP_2], total=2
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        reservedips_response = ReservedIPsListResponse(**response.json())
        assert len(reservedips_response.items) == 1
        assert reservedips_response.total == 2
        assert reservedips_response.next == f"{self.BASE_PATH}?page=2&size=1"
        services_mock.reservedips.list.assert_called_once_with(
            page=1,
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

    async def test_get_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.reservedips = Mock(ReservedIPsService)
        services_mock.reservedips.get_one.return_value = TEST_RESERVEDIP
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/{TEST_RESERVEDIP.id}"
        )
        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0
        assert response.json() == {
            "kind": "ReservedIP",
            "id": TEST_RESERVEDIP.id,
            "ip": "10.0.0.1",
            "mac_address": "01:02:03:04:05:06",
            "comment": "test_comment",
            # TODO: FastAPI response_model_exclude_none not working. We need to fix this before making the api public
            "_embedded": None,
            "_links": {
                "self": {"href": f"{self.BASE_PATH}/{TEST_RESERVEDIP.id}"}
            },
        }
        services_mock.reservedips.get_one.assert_called_once_with(
            query=QuerySpec(
                ReservedIPsClauseFactory.and_clauses(
                    [
                        ReservedIPsClauseFactory.with_id(TEST_RESERVEDIP.id),
                        ReservedIPsClauseFactory.with_fabric_id(1),
                        ReservedIPsClauseFactory.with_subnet_id(1),
                        ReservedIPsClauseFactory.with_vlan_id(1),
                    ]
                )
            )
        )

    async def test_get_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.reservedips = Mock(ReservedIPsService)
        services_mock.reservedips.get_one.return_value = None
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
        services_mock.reservedips = Mock(ReservedIPsService)
        services_mock.reservedips.get_one.return_value = (
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
        services_mock.reservedips = Mock(ReservedIPsService)
        services_mock.reservedips.create.return_value = TEST_RESERVEDIP
        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.get_one.return_value = Subnet(
            id=1,
            cidr=IPv4Network(f"{TEST_RESERVEDIP.ip}/24", strict=False),
            rdns_mode=RdnsMode.DEFAULT,
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            disabled_boot_architectures=[],
            vlan_id=1,
        )
        # we test the validation logic in the builder test
        services_mock.staticipaddress = Mock(StaticIPAddressService)
        services_mock.staticipaddress.get_one.return_value = None
        services_mock.ipranges = Mock(IPRangesService)
        services_mock.ipranges.get_dynamic_range_for_ip.return_value = None
        reservedip_request = ReservedIPCreateRequest(
            ip=TEST_RESERVEDIP.ip,
            mac_address=TEST_RESERVEDIP.mac_address,
        )
        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}", json=jsonable_encoder(reservedip_request)
        )
        assert response.status_code == 201
        assert "ETag" in response.headers
        assert len(response.headers["ETag"]) > 0

    async def test_put_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        updated_reservedip = TEST_RESERVEDIP
        updated_reservedip.comment = "updated comment"
        services_mock.reservedips = Mock(ReservedIPsService)
        services_mock.reservedips.get_one.return_value = TEST_RESERVEDIP
        services_mock.reservedips.update_one.return_value = updated_reservedip
        reservedip_request = ReservedIPUpdateRequest(
            ip=TEST_RESERVEDIP.ip,
            mac_address=TEST_RESERVEDIP.mac_address,
            comment="updated comment",
        )
        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/{TEST_RESERVEDIP.id}",
            json=jsonable_encoder(reservedip_request),
        )
        assert response.status_code == 200
        assert "ETag" in response.headers
        assert len(response.headers["ETag"]) > 0
        assert response.json()["comment"] == "updated comment"

        query = QuerySpec(
            where=ReservedIPsClauseFactory.and_clauses(
                [
                    ReservedIPsClauseFactory.with_id(TEST_RESERVEDIP.id),
                    ReservedIPsClauseFactory.with_subnet_id(1),
                    ReservedIPsClauseFactory.with_vlan_id(1),
                    ReservedIPsClauseFactory.with_fabric_id(1),
                ]
            )
        )
        services_mock.reservedips.get_one.assert_called_once_with(query=query)

        services_mock.reservedips.update_one.assert_called_once_with(
            query=query,
            builder=reservedip_request.to_builder(TEST_RESERVEDIP),
            etag_if_match=None,
        )

    async def test_put_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.reservedips = Mock(ReservedIPsService)
        services_mock.reservedips.get_one.return_value = None
        reservedip_request = ReservedIPUpdateRequest(
            ip=TEST_RESERVEDIP.ip,
            mac_address=TEST_RESERVEDIP.mac_address,
            comment="updated comment",
        )
        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/{TEST_RESERVEDIP.id}",
            json=jsonable_encoder(reservedip_request),
        )
        assert response.status_code == 404

    async def test_delete(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.reservedips = Mock(ReservedIPsService)
        services_mock.reservedips.delete_one.return_value = TEST_RESERVEDIP
        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/{TEST_RESERVEDIP.id}"
        )
        assert response.status_code == 204
        services_mock.reservedips.delete_one.assert_called_with(
            query=QuerySpec(
                where=ReservedIPsClauseFactory.and_clauses(
                    [
                        ReservedIPsClauseFactory.with_id(TEST_RESERVEDIP.id),
                        ReservedIPsClauseFactory.with_subnet_id(1),
                        ReservedIPsClauseFactory.with_vlan_id(1),
                        ReservedIPsClauseFactory.with_fabric_id(1),
                    ]
                )
            ),
            etag_if_match=None,
        )

    async def test_delete_with_etag(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.reservedips = Mock(ReservedIPsService)
        services_mock.reservedips.delete_one.side_effect = PreconditionFailedException(
            details=[
                BaseExceptionDetail(
                    type=ETAG_PRECONDITION_VIOLATION_TYPE,
                    message="The resource etag 'wrong_etag' did not match 'my_etag'.",
                )
            ]
        )

        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/{TEST_RESERVEDIP.id}",
            headers={"if-match": "wrong_etag"},
        )
        assert response.status_code == 412
        services_mock.reservedips.delete_one.assert_called_with(
            query=QuerySpec(
                where=ReservedIPsClauseFactory.and_clauses(
                    [
                        ReservedIPsClauseFactory.with_id(TEST_RESERVEDIP.id),
                        ReservedIPsClauseFactory.with_subnet_id(1),
                        ReservedIPsClauseFactory.with_vlan_id(1),
                        ReservedIPsClauseFactory.with_fabric_id(1),
                    ]
                )
            ),
            etag_if_match="wrong_etag",
        )
