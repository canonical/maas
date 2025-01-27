#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.requests.vlans import (
    VlanCreateRequest,
    VlanUpdateRequest,
)
from maasapiserver.v3.api.public.models.responses.vlans import (
    VlanResponse,
    VlansListResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.db.filters import ClauseFactory, QuerySpec
from maasservicelayer.db.repositories.vlans import VlansClauseFactory
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    PreconditionFailedException,
)
from maasservicelayer.exceptions.constants import (
    ETAG_PRECONDITION_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.vlans import Vlan, VlanBuilder
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.vlans import VlansService
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
    relay_vlan_id=None,
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
    relay_vlan_id=None,
    fabric_id=2,
    space_id=None,
)


class TestVlanApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/fabrics/1/vlans"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=self.BASE_PATH),
            Endpoint(method="GET", path=f"{self.BASE_PATH}/1"),
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="POST", path=f"{self.BASE_PATH}"),
            Endpoint(method="DELETE", path=f"{self.BASE_PATH}/1"),
        ]

    # POST /fabrics/{fabric_id}/vlans
    async def test_post_201(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        vlan_request = VlanCreateRequest(
            name=TEST_VLAN.name,
            description=TEST_VLAN.description,
            vid=TEST_VLAN.vid,
            mtu=TEST_VLAN.mtu,
        )
        services_mock.vlans = Mock(VlansService)
        services_mock.vlans.create.return_value = TEST_VLAN
        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=jsonable_encoder(vlan_request)
        )
        assert response.status_code == 201
        assert len(response.headers["ETag"]) > 0
        vlan_response = VlanResponse(**response.json())
        assert vlan_response.id == TEST_VLAN.id
        assert vlan_response.name == vlan_request.name
        assert vlan_response.description == vlan_request.description
        assert vlan_response.vid == vlan_request.vid
        assert vlan_response.mtu == vlan_request.mtu
        assert vlan_response.dhcp_on is False
        assert vlan_response.external_dhcp is None
        assert vlan_response.primary_rack is None
        assert vlan_response.secondary_rack is None
        assert vlan_response.relay_vlan_id is None
        assert (
            vlan_response.hal_links.self.href
            == f"{self.BASE_PATH}/{vlan_response.id}"
        )
        services_mock.vlans.create.assert_called_with(
            builder=VlanBuilder(
                name=TEST_VLAN.name,
                description=TEST_VLAN.description,
                vid=TEST_VLAN.vid,
                mtu=TEST_VLAN.mtu,
                dhcp_on=False,
                space_id=TEST_VLAN.space_id,
                fabric_id=TEST_VLAN.fabric_id,
            )
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "vlan_request",
        [
            {"vid": -1},
            {"vid": 4097},
            {"vid": 0, "mtu": 551},
            {"vid": 0, "mtu": 65536},
        ],
    )
    async def test_post_invalid_parameters(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
        vlan_request: dict,
    ) -> None:
        services_mock.vlans = Mock(VlansService)
        services_mock.vlans.create.return_value = TEST_VLAN
        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=vlan_request
        )
        assert response.status_code == 422

    async def test_list_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.vlans = Mock(VlansService)
        services_mock.vlans.list.return_value = ListResult[Vlan](
            items=[TEST_VLAN], total=1
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        vlans_response = VlansListResponse(**response.json())
        assert len(vlans_response.items) == 1
        assert vlans_response.total == 1
        assert vlans_response.next is None

    async def test_list_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.vlans = Mock(VlansService)
        services_mock.vlans.list.return_value = ListResult[Vlan](
            items=[TEST_VLAN_2], total=2
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        vlans_response = VlansListResponse(**response.json())
        assert len(vlans_response.items) == 1
        assert vlans_response.total == 2
        assert vlans_response.next == f"{self.BASE_PATH}?page=2&size=1"

    # GET /vlans/{vlan_id}
    async def test_get_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.vlans = Mock(VlansService)
        services_mock.vlans.get_one.return_value = TEST_VLAN
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
            "relay_vlan_id": TEST_VLAN.relay_vlan_id,
            # TODO: FastAPI response_model_exclude_none not working. We need to fix this before making the api public
            "_embedded": None,
            "space": None,
            "_links": {"self": {"href": f"{self.BASE_PATH}/{TEST_VLAN.id}"}},
        }

    async def test_get_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.vlans = Mock(VlansService)
        services_mock.vlans.get_one.return_value = None
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
        services_mock.vlans.get_by_id.side_effect = RequestValidationError(
            errors=[]
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/xyz")
        assert response.status_code == 422
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422

    async def test_put_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        updated_vlan = TEST_VLAN.copy()
        updated_vlan.name = "newname"
        services_mock.vlans = Mock(VlansService)
        services_mock.vlans.update_one.return_value = updated_vlan
        update_vlan_request = VlanUpdateRequest(
            name="newname",
            description=TEST_VLAN.description,
            vid=TEST_VLAN.vid,
            mtu=TEST_VLAN.mtu,
            dhcp_on=False,
            fabric_id=TEST_VLAN.fabric_id,
        )
        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/{str(TEST_VLAN.id)}",
            json=jsonable_encoder(update_vlan_request),
        )
        assert response.status_code == 200

        updated_vlan = VlanResponse(**response.json())
        assert updated_vlan.id == TEST_VLAN.id
        assert updated_vlan.name == "newname"
        assert updated_vlan.description == TEST_VLAN.description

    # All the validations are covered in the VlanUpdateRequest tests.
    async def test_put_422_dhcp_on_incompatible_with_relay(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        update_vlan_request = VlanUpdateRequest(
            name="newname",
            description=TEST_VLAN.description,
            vid=TEST_VLAN.vid,
            mtu=TEST_VLAN.mtu,
            dhcp_on=True,
            fabric_id=TEST_VLAN.fabric_id,
            relay_vlan_id=1,
        )
        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/{str(TEST_VLAN.id)}",
            json=jsonable_encoder(update_vlan_request),
        )
        assert response.status_code == 422

        error_response = ErrorBodyResponse(**response.json())
        assert len(error_response.details) == 1
        assert error_response.details[0].field == "relay_vlan_id"
        assert (
            error_response.details[0].message
            == "'relay_vlan_id' cannot be set when dhcp is on."
        )

    async def test_delete(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.vlans = Mock(VlansService)
        services_mock.vlans.delete_one.return_value = None
        response = await mocked_api_client_admin.delete(f"{self.BASE_PATH}/1")
        assert response.status_code == 204
        services_mock.vlans.delete_one.assert_called_with(
            query=QuerySpec(
                where=ClauseFactory.and_clauses(
                    [
                        VlansClauseFactory.with_id(1),
                        VlansClauseFactory.with_fabric_id(1),
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
        services_mock.vlans = Mock(VlansService)
        services_mock.vlans.delete_one.side_effect = PreconditionFailedException(
            details=[
                BaseExceptionDetail(
                    type=ETAG_PRECONDITION_VIOLATION_TYPE,
                    message="The resource etag 'wrong_etag' did not match 'my_etag'.",
                )
            ]
        )

        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/1", headers={"if-match": "wrong_etag"}
        )
        assert response.status_code == 412
        services_mock.vlans.delete_one.assert_called_with(
            query=QuerySpec(
                where=ClauseFactory.and_clauses(
                    [
                        VlansClauseFactory.with_id(1),
                        VlansClauseFactory.with_fabric_id(1),
                    ]
                )
            ),
            etag_if_match="wrong_etag",
        )
