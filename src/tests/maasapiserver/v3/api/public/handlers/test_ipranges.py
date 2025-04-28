# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv4Network
from unittest.mock import Mock

from fastapi.exceptions import RequestValidationError
from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.responses.ipranges import (
    IPRangeListResponse,
    IPRangeResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.ipranges import IPRangeType
from maascommon.enums.subnet import RdnsMode
from maascommon.utils.network import MAASIPRange, MAASIPSet
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.ipranges import IPRangeClauseFactory
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    PreconditionFailedException,
)
from maasservicelayer.exceptions.constants import (
    ETAG_PRECONDITION_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.ipranges import IPRange
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services import (
    ReservedIPsService,
    ServiceCollectionV3,
    SubnetsService,
    V3SubnetUtilizationService,
)
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
    user_id=0,
)

TEST_IPRANGE_2 = IPRange(
    id=2,
    created=now,
    updated=now,
    type=IPRangeType.RESERVED,
    start_ip=IPv4Address("10.10.0.5"),
    end_ip=IPv4Address("10.10.0.7"),
    subnet_id=1,
    user_id=0,
)


class TestIPRangesApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/fabrics/1/vlans/1/subnets/1/ipranges"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=f"{self.BASE_PATH}/1"),
            Endpoint(method="POST", path=self.BASE_PATH),
            Endpoint(method="DELETE", path=f"{self.BASE_PATH}/1"),
            Endpoint(method="PUT", path=f"{self.BASE_PATH}/1"),
        ]

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
            items=[TEST_IPRANGE], total=1
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        ipranges_response = IPRangeListResponse(**response.json())
        assert len(ipranges_response.items) == 1
        assert ipranges_response.total == 1
        assert ipranges_response.next is None
        services_mock.ipranges.list.assert_called_once_with(
            page=1,
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
            items=[TEST_IPRANGE_2], total=2
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        ipranges_response = IPRangeListResponse(**response.json())
        assert len(ipranges_response.items) == 1
        assert ipranges_response.next == f"{self.BASE_PATH}?page=2&size=1"
        services_mock.ipranges.list.assert_called_once_with(
            page=1,
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
        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0
        assert response.json() == {
            "kind": "IPRange",
            "id": TEST_IPRANGE.id,
            "type": str(TEST_IPRANGE.type),
            "start_ip": str(TEST_IPRANGE.start_ip),
            "end_ip": str(TEST_IPRANGE.end_ip),
            "comment": None,
            "owner_id": 0,
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

    async def test_post_201(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.reservedips = Mock(ReservedIPsService)
        services_mock.reservedips.exists_within_subnet_iprange.return_value = (
            False
        )

        services_mock.v3subnet_utilization = Mock(V3SubnetUtilizationService)
        services_mock.v3subnet_utilization.get_ipranges_available_for_reserved_range.return_value = MAASIPSet(
            ranges=[MAASIPRange(start="10.10.0.1", end="10.10.0.3")]
        )

        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.get_one.return_value = Subnet(
            id=1,
            cidr=IPv4Network("10.10.0.0/24", strict=False),
            rdns_mode=RdnsMode.DEFAULT,
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            disabled_boot_architectures=[],
            vlan_id=1,
        )

        services_mock.ipranges = Mock(IPRangesService)
        services_mock.ipranges.create.return_value = TEST_IPRANGE

        iprange_request = {
            "type": "reserved",
            "start_ip": "10.10.0.1",
            "end_ip": "10.10.0.3",
        }
        response = await mocked_api_client_user.post(
            f"{self.BASE_PATH}", json=iprange_request
        )
        assert response.status_code == 201
        assert "ETag" in response.headers
        assert len(response.headers["ETag"]) > 0
        iprange_response = IPRangeResponse(**response.json())
        assert iprange_response.start_ip == IPv4Address("10.10.0.1")
        assert iprange_response.end_ip == IPv4Address("10.10.0.3")
        assert iprange_response.type == IPRangeType.RESERVED
        assert iprange_response.comment is None
        assert (
            iprange_response.owner_id == 0
        )  # The user_id for the requests in these tests is always 0
        services_mock.ipranges.create.assert_called_once()

    async def test_post_201_dynamic_iprange(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.reservedips = Mock(ReservedIPsService)
        services_mock.reservedips.exists_within_subnet_iprange.return_value = (
            False
        )

        services_mock.v3subnet_utilization = Mock(V3SubnetUtilizationService)
        services_mock.v3subnet_utilization.get_ipranges_available_for_dynamic_range.return_value = MAASIPSet(
            ranges=[MAASIPRange(start="10.10.0.1", end="10.10.0.3")]
        )

        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.get_one.return_value = Subnet(
            id=1,
            cidr=IPv4Network("10.10.0.0/24", strict=False),
            rdns_mode=RdnsMode.DEFAULT,
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            disabled_boot_architectures=[],
            vlan_id=1,
        )

        dynamic_iprange = TEST_IPRANGE.copy()
        dynamic_iprange.type = IPRangeType.DYNAMIC
        services_mock.ipranges = Mock(IPRangesService)
        services_mock.ipranges.create.return_value = dynamic_iprange

        iprange_request = {
            "type": "dynamic",
            "start_ip": "10.10.0.1",
            "end_ip": "10.10.0.3",
        }
        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}", json=iprange_request
        )
        assert response.status_code == 201
        assert "ETag" in response.headers
        assert len(response.headers["ETag"]) > 0
        iprange_response = IPRangeResponse(**response.json())
        assert iprange_response.start_ip == IPv4Address("10.10.0.1")
        assert iprange_response.end_ip == IPv4Address("10.10.0.3")
        assert iprange_response.type == IPRangeType.DYNAMIC
        assert iprange_response.comment is None
        assert iprange_response.owner_id == 0
        services_mock.ipranges.create.assert_called_once()

    async def test_post_400(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.get_one.return_value = None
        iprange_request = {
            "type": "reserved",
            "start_ip": "10.0.0.1",
            "end_ip": "10.0.0.1",
            "owner_id": 99,
        }
        response = await mocked_api_client_user.post(
            f"{self.BASE_PATH}", json=iprange_request
        )
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 400
        assert error_response.details is not None
        assert (
            error_response.details[0].message
            == "Only admins can create IP ranges on behalf of other users."
        )

    async def test_post_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.get_one.return_value = None
        iprange_request = {
            "type": "reserved",
            "start_ip": "10.0.0.1",
            "end_ip": "10.0.0.1",
        }
        response = await mocked_api_client_user.post(
            f"{self.BASE_PATH}", json=iprange_request
        )
        assert response.status_code == 404

    @pytest.mark.parametrize(
        "start_ip, end_ip, matches_reserved_ips, message",
        [
            (
                "10.0.0.1",
                "10.0.0.2",
                True,
                "The dynamic IP range would include some IPs that are already reserved. Remove them first.",
            ),
            (
                ".0.0.1",
                "10.0.0.2",
                False,
                "value is not a valid IPv4 or IPv6 address",
            ),
            (
                "10.0.0.1",
                "10.0.0.256",
                False,
                "value is not a valid IPv4 or IPv6 address",
            ),
            (
                ":::ffff:a00:65",
                "10.0.0.256",
                False,
                "value is not a valid IPv4 or IPv6 address",
            ),
            (
                "::ffff:a00:65",
                "10.0.0.1",
                False,
                "Start IP address and end IP address must be in the same address family.",
            ),
        ],
    )
    async def test_post_422(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
        start_ip: str,
        end_ip: str,
        matches_reserved_ips: bool,
        message: str,
    ) -> None:
        services_mock.reservedips = Mock(ReservedIPsService)
        services_mock.reservedips.exists_within_subnet_iprange.return_value = (
            matches_reserved_ips
        )

        services_mock.v3subnet_utilization = Mock(V3SubnetUtilizationService)
        services_mock.v3subnet_utilization.get_ipranges_available_for_dynamic_range.return_value = MAASIPSet(
            ranges=[MAASIPRange(start="10.0.0.1", end="10.0.0.254")]
        )

        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.get_one.return_value = Subnet(
            id=1,
            cidr=IPv4Network("10.0.0.0/24", strict=False),
            rdns_mode=RdnsMode.DEFAULT,
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            disabled_boot_architectures=[],
            vlan_id=1,
        )
        iprange_request = {
            "type": "dynamic",
            "start_ip": start_ip,
            "end_ip": end_ip,
        }
        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}", json=iprange_request
        )
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422
        assert error_response.details[0].message == message

    async def test_post_422_no_free_ranges(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.reservedips = Mock(ReservedIPsService)
        services_mock.reservedips.exists_within_subnet_iprange.return_value = (
            False
        )

        services_mock.v3subnet_utilization = Mock(V3SubnetUtilizationService)
        services_mock.v3subnet_utilization.get_ipranges_available_for_dynamic_range.return_value = MAASIPSet(
            ranges=[]
        )

        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.get_one.return_value = Subnet(
            id=1,
            cidr=IPv4Network("10.0.0.0/24", strict=False),
            rdns_mode=RdnsMode.DEFAULT,
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            disabled_boot_architectures=[],
            vlan_id=1,
        )
        iprange_request = {
            "type": "dynamic",
            "start_ip": "10.0.0.1",
            "end_ip": "10.0.0.3",
        }
        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}", json=iprange_request
        )
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422
        assert (
            error_response.details[0].message
            == "There is no room for any dynamic ranges on this subnet."
        )
        services_mock.v3subnet_utilization.get_ipranges_available_for_dynamic_range.assert_called_once_with(
            subnet_id=1, exclude_ip_range_id=None
        )

    async def test_post_422_conflict_ranges(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.reservedips = Mock(ReservedIPsService)
        services_mock.reservedips.exists_within_subnet_iprange.return_value = (
            False
        )

        services_mock.v3subnet_utilization = Mock(V3SubnetUtilizationService)
        services_mock.v3subnet_utilization.get_ipranges_available_for_dynamic_range.return_value = MAASIPSet(
            ranges=[MAASIPRange(start="10.0.0.100", end="10.0.0.111")]
        )

        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.get_one.return_value = Subnet(
            id=1,
            cidr=IPv4Network("10.0.0.0/24", strict=False),
            rdns_mode=RdnsMode.DEFAULT,
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            disabled_boot_architectures=[],
            vlan_id=1,
        )
        iprange_request = {
            "type": "dynamic",
            "start_ip": "10.0.0.111",
            "end_ip": "10.0.0.112",
        }
        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}", json=iprange_request
        )
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 409
        assert (
            error_response.details[0].message
            == "Requested dynamic range conflicts with an existing IP address or range."
        )
        services_mock.v3subnet_utilization.get_ipranges_available_for_dynamic_range.assert_called_once_with(
            subnet_id=1, exclude_ip_range_id=None
        )

    async def test_post_403_dynamic_iprange(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.get_one.return_value = Subnet(
            id=1,
            cidr=IPv4Network("10.0.0.0/24", strict=False),
            rdns_mode=RdnsMode.DEFAULT,
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            disabled_boot_architectures=[],
            vlan_id=1,
        )
        iprange_request = {
            "type": "dynamic",
            "start_ip": "10.0.0.1",
            "end_ip": "10.0.0.1",
        }
        response = await mocked_api_client_user.post(
            f"{self.BASE_PATH}", json=iprange_request
        )
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 403
        assert error_response.details is not None
        assert (
            error_response.details[0].message
            == "Only admins can create/update dynamic IP ranges."
        )

    async def test_post_403_iprange_owned_by_another_user(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.get_one.return_value = Subnet(
            id=1,
            cidr=IPv4Network("10.0.0.0/24", strict=False),
            rdns_mode=RdnsMode.DEFAULT,
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            disabled_boot_architectures=[],
            vlan_id=1,
        )
        iprange_request = {
            "type": "reserved",
            "start_ip": "10.0.0.1",
            "end_ip": "10.0.0.1",
            "owner_id": 99,
        }
        response = await mocked_api_client_user.post(
            f"{self.BASE_PATH}", json=iprange_request
        )
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 400
        assert error_response.details is not None
        assert (
            error_response.details[0].message
            == "Only admins can create IP ranges on behalf of other users."
        )

    async def test_delete(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.ipranges = Mock(IPRangesService)
        services_mock.ipranges.get_one.return_value = TEST_IPRANGE
        services_mock.ipranges.delete_by_id.return_value = TEST_IPRANGE
        response = await mocked_api_client_user.delete(
            f"{self.BASE_PATH}/{TEST_IPRANGE.id}"
        )

        assert response.status_code == 204

        services_mock.ipranges.get_one.assert_called_once_with(
            query=QuerySpec(
                where=IPRangeClauseFactory.and_clauses(
                    [
                        IPRangeClauseFactory.with_id(TEST_IPRANGE.id),
                        IPRangeClauseFactory.with_subnet_id(1),
                        IPRangeClauseFactory.with_vlan_id(1),
                        IPRangeClauseFactory.with_fabric_id(1),
                    ]
                )
            )
        )
        services_mock.ipranges.delete_by_id.assert_called_once_with(
            TEST_IPRANGE.id, etag_if_match=None
        )

    async def test_delete_not_owner(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.ipranges = Mock(IPRangesService)
        iprange = TEST_IPRANGE.copy()
        iprange.user_id = 3
        services_mock.ipranges.get_one.return_value = iprange
        services_mock.ipranges.delete_by_id.return_value = iprange
        response = await mocked_api_client_user.delete(
            f"{self.BASE_PATH}/{iprange.id}"
        )
        assert response.status_code == 403

        services_mock.ipranges.get_one.assert_called_once_with(
            query=QuerySpec(
                where=IPRangeClauseFactory.and_clauses(
                    [
                        IPRangeClauseFactory.with_id(iprange.id),
                        IPRangeClauseFactory.with_subnet_id(1),
                        IPRangeClauseFactory.with_vlan_id(1),
                        IPRangeClauseFactory.with_fabric_id(1),
                    ]
                )
            )
        )
        services_mock.ipranges.delete_by_id.assert_not_called()

    async def test_delete_with_etag(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.ipranges = Mock(IPRangesService)
        services_mock.ipranges.get_one.return_value = TEST_IPRANGE
        services_mock.ipranges.delete_by_id.side_effect = PreconditionFailedException(
            details=[
                BaseExceptionDetail(
                    type=ETAG_PRECONDITION_VIOLATION_TYPE,
                    message="The resource etag 'wrong_etag' did not match 'my_etag'.",
                )
            ]
        )

        response = await mocked_api_client_user.delete(
            f"{self.BASE_PATH}/1", headers={"if-match": "wrong_etag"}
        )
        assert response.status_code == 412
        services_mock.ipranges.get_one.assert_called_with(
            query=QuerySpec(
                where=IPRangeClauseFactory.and_clauses(
                    [
                        IPRangeClauseFactory.with_id(1),
                        IPRangeClauseFactory.with_subnet_id(1),
                        IPRangeClauseFactory.with_vlan_id(1),
                        IPRangeClauseFactory.with_fabric_id(1),
                    ]
                )
            )
        )
        services_mock.ipranges.delete_by_id.assert_called_with(
            TEST_IPRANGE.id,
            etag_if_match="wrong_etag",
        )

    async def test_update_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.ipranges = Mock(IPRangesService)
        services_mock.ipranges.get_one.return_value = TEST_IPRANGE

        services_mock.v3subnet_utilization = Mock(V3SubnetUtilizationService)
        services_mock.v3subnet_utilization.get_ipranges_available_for_reserved_range.return_value = MAASIPSet(
            ranges=[MAASIPRange(start="10.0.0.1", end="10.0.0.3")]
        )

        updated_iprange = TEST_IPRANGE.copy()
        updated_iprange.comment = "comment"
        services_mock.ipranges.update_one.return_value = updated_iprange
        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.get_one.return_value = Subnet(
            id=1,
            cidr=IPv4Network("10.0.0.0/16", strict=False),
            rdns_mode=RdnsMode.DEFAULT,
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            disabled_boot_architectures=[],
            vlan_id=1,
        )

        iprange_request = {
            "type": "reserved",
            "start_ip": "10.0.0.1",
            "end_ip": "10.0.0.3",
            "comment": "comment",
            "owner_id": 0,
        }
        response = await mocked_api_client_user.put(
            f"{self.BASE_PATH}/1", json=iprange_request
        )
        assert response.status_code == 200
        services_mock.v3subnet_utilization.get_ipranges_available_for_reserved_range.assert_called_once_with(
            subnet_id=1, exclude_ip_range_id=1
        )

    async def test_update_400(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.ipranges = Mock(IPRangesService)
        services_mock.ipranges.get_one.return_value = TEST_IPRANGE
        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.get_one.return_value = Subnet(
            id=1,
            cidr=IPv4Network("10.0.0.0/24", strict=False),
            rdns_mode=RdnsMode.DEFAULT,
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            disabled_boot_architectures=[],
            vlan_id=1,
        )

        iprange_request = {
            "type": "reserved",
            "start_ip": "10.0.0.1",
            "end_ip": "10.0.0.3",
            "comment": "comment",
            "owner_id": 99,
        }
        response = await mocked_api_client_user.put(
            f"{self.BASE_PATH}/1", json=iprange_request
        )
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 400
        assert error_response.details is not None
        assert (
            error_response.details[0].message
            == "Only admins can update IP ranges for other users."
        )

    async def test_update_403(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        iprange = TEST_IPRANGE.copy()
        iprange.user_id = 99
        services_mock.ipranges = Mock(IPRangesService)
        services_mock.ipranges.get_one.return_value = iprange
        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.get_one.return_value = Subnet(
            id=1,
            cidr=IPv4Network("10.0.0.0/24", strict=False),
            rdns_mode=RdnsMode.DEFAULT,
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            disabled_boot_architectures=[],
            vlan_id=1,
        )

        iprange_request = {
            "type": "reserved",
            "start_ip": "10.0.0.1",
            "end_ip": "10.0.0.3",
            "comment": "comment",
            "owner_id": 0,
        }
        response = await mocked_api_client_user.put(
            f"{self.BASE_PATH}/1", json=iprange_request
        )
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 403
        assert error_response.details is not None
        assert (
            error_response.details[0].message
            == "Only admins can update IP ranges for other users."
        )

    async def test_update_403_dynamic_iprange(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.ipranges = Mock(IPRangesService)
        services_mock.ipranges.get_one.return_value = TEST_IPRANGE
        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.get_one.return_value = Subnet(
            id=1,
            cidr=IPv4Network("10.0.0.0/24", strict=False),
            rdns_mode=RdnsMode.DEFAULT,
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            disabled_boot_architectures=[],
            vlan_id=1,
        )

        iprange_request = {
            "type": "dynamic",
            "start_ip": "10.0.0.1",
            "end_ip": "10.0.0.3",
            "comment": "comment",
            "owner_id": 0,
        }
        response = await mocked_api_client_user.put(
            f"{self.BASE_PATH}/1", json=iprange_request
        )
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 403
        assert error_response.details is not None
        assert (
            error_response.details[0].message
            == "Only admins can create/update dynamic IP ranges."
        )

    async def test_update_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.ipranges = Mock(IPRangesService)
        services_mock.ipranges.get_one.return_value = None
        services_mock.subnets = Mock(SubnetsService)
        services_mock.subnets.get_one.return_value = Subnet(
            id=1,
            cidr=IPv4Network("10.0.0.0/24", strict=False),
            rdns_mode=RdnsMode.DEFAULT,
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            disabled_boot_architectures=[],
            vlan_id=1,
        )

        iprange_request = {
            "type": "reserved",
            "start_ip": "10.0.0.1",
            "end_ip": "10.0.0.3",
            "comment": "comment",
            "owner_id": 0,
        }
        response = await mocked_api_client_user.put(
            f"{self.BASE_PATH}/1", json=iprange_request
        )
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404
