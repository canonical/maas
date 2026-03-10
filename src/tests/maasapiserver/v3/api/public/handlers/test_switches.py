#  Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone
from unittest.mock import Mock

from httpx import AsyncClient
import pytest

from maasapiserver.v3.api.public.models.responses.switches import (
    SwitchesListResponse,
    SwitchResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.boot_resources import BootResourceType
from maascommon.enums.interface import InterfaceType
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.bootresources import BootResource
from maasservicelayer.models.interfaces import Interface
from maasservicelayer.models.switches import Switch
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.bootresources import BootResourceService
from maasservicelayer.services.interfaces import InterfacesService
from maasservicelayer.services.switches import SwitchesService
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

TEST_SWITCH = Switch(
    id=1,
    target_image_id=None,
    created=utcnow(),
    updated=utcnow(),
)

TEST_SWITCH_2 = Switch(
    id=2,
    target_image_id=10,
    created=utcnow(),
    updated=utcnow(),
)

TEST_NOS_IMAGE = BootResource(
    id=1,
    rtype=BootResourceType.UPLOADED,
    name="onie/dellos10",
    architecture="amd64/generic",
    extra={},
    rolling=False,
    base_image="",
)


class TestSwitchesApi(ApiCommonTests):
    """Tests for the Switches API endpoints."""

    BASE_PATH = f"{V3_API_PREFIX}/switches"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        """Endpoints accessible to regular users."""
        return [
            Endpoint(method="GET", path=f"{self.BASE_PATH}"),
            Endpoint(method="GET", path=f"{self.BASE_PATH}/1"),
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        """Endpoints accessible only to admins."""
        return [
            Endpoint(method="POST", path=f"{self.BASE_PATH}"),
            Endpoint(method="PATCH", path=f"{self.BASE_PATH}/1"),
            Endpoint(method="DELETE", path=f"{self.BASE_PATH}/1"),
        ]

    async def test_admin_endpoints_forbidden(
        self,
        admin_endpoints: list[Endpoint],
        mocked_api_client: AsyncClient,
        mocked_api_client_user: AsyncClient,
    ):
        """Test proper unauthenticated/unauthorized responses for admin endpoints."""
        for endpoint in admin_endpoints:
            response = await mocked_api_client.request(
                endpoint.method,
                endpoint.path,
                json={"mac_address": "00:11:22:33:44:55"},
            )
            assert response.status_code == 401

            response = await mocked_api_client_user.request(
                endpoint.method,
                endpoint.path,
                json={"mac_address": "00:11:22:33:44:55"},
            )
            assert response.status_code == 403

    async def test_list_switches(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        """Test listing switches returns correct response."""
        services_mock.switches = Mock(SwitchesService)
        services_mock.switches.list.return_value = ListResult[Switch](
            items=[TEST_SWITCH, TEST_SWITCH_2], total=2
        )

        # TEST_SWITCH does not have target_image_id, so no need to mock boot_resources for it
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_by_id.return_value = TEST_NOS_IMAGE

        response = await mocked_api_client_user.get(f"{self.BASE_PATH}")
        assert response.status_code == 200

        switches_response = SwitchesListResponse(**response.json())
        assert len(switches_response.items) == 2
        assert switches_response.total == 2
        assert switches_response.items[0].id == 1
        assert switches_response.items[0].target_image_id is None
        assert switches_response.items[0].target_image is None
        assert switches_response.items[1].id == 2
        assert switches_response.items[1].target_image_id == 10
        assert switches_response.items[1].target_image == TEST_NOS_IMAGE.name

    async def test_list_switches_with_pagination(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        """Test listing switches with pagination parameters."""
        services_mock.switches = Mock(SwitchesService)
        services_mock.switches.list.return_value = ListResult[Switch](
            items=[TEST_SWITCH], total=2
        )

        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}?page=1&size=1"
        )
        assert response.status_code == 200

        switches_response = SwitchesListResponse(**response.json())
        assert len(switches_response.items) == 1
        assert switches_response.total == 2
        assert switches_response.next == f"{self.BASE_PATH}?page=2&size=1"

    async def test_get_switch(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        """Test getting a specific switch by ID."""
        services_mock.switches = Mock(SwitchesService)
        services_mock.switches.get_by_id.return_value = TEST_SWITCH

        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/1")
        assert response.status_code == 200

        switch_response = SwitchResponse(**response.json())
        assert switch_response.id == 1
        assert switch_response.target_image_id is None
        assert switch_response.target_image is None

    async def test_get_switch_not_found(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        """Test getting a non-existent switch returns 404."""
        services_mock.switches = Mock(SwitchesService)
        services_mock.switches.get_by_id.return_value = None

        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/999")
        assert response.status_code == 404

    async def test_create_switch(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        """Test creating a new switch."""
        services_mock.switches = Mock(SwitchesService)
        services_mock.interfaces = Mock(InterfacesService)
        services_mock.interfaces.list.return_value = ListResult[Interface](
            items=[], total=0
        )
        services_mock.switches.create_new_switch_and_interface.return_value = (
            TEST_SWITCH
        )

        new_switch_data = {
            "mac_address": "00:11:22:33:44:55",
        }

        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}", json=new_switch_data
        )
        assert response.status_code == 201
        assert response.headers["Location"] == f"{self.BASE_PATH}/1"

    async def test_create_switch_with_image(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        """Test creating a new switch with target image."""
        services_mock.switches = Mock(SwitchesService)
        services_mock.interfaces = Mock(InterfacesService)
        services_mock.interfaces.list.return_value = ListResult[Interface](
            items=[], total=0
        )
        services_mock.switches.create_new_switch_and_interface.return_value = (
            Switch(
                **{
                    **TEST_SWITCH.dict(),
                    "target_image_id": TEST_NOS_IMAGE.id,
                    "target_image": TEST_NOS_IMAGE.name,
                }
            )
        )
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_one.return_value = TEST_NOS_IMAGE
        services_mock.boot_resources.get_by_id.return_value = TEST_NOS_IMAGE

        new_switch_data = {
            "mac_address": "00:11:22:33:44:55",
            "image": "onie/dellos10",
        }

        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}", json=new_switch_data
        )
        assert response.status_code == 201
        assert response.headers["Location"] == f"{self.BASE_PATH}/1"

        switch_response = SwitchResponse(**response.json())
        assert switch_response.target_image_id == TEST_NOS_IMAGE.id
        assert switch_response.target_image == TEST_NOS_IMAGE.name

    async def test_create_switch_with_nonexistent_image(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        """Test creating a new switch with target image."""
        services_mock.switches = Mock(SwitchesService)
        services_mock.interfaces = Mock(InterfacesService)
        services_mock.interfaces.list.return_value = ListResult[Interface](
            items=[], total=0
        )

        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_one.return_value = None

        new_switch_data = {
            "mac_address": "00:11:22:33:44:55",
            "image": "onie/not-an-image",
        }

        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}", json=new_switch_data
        )
        assert response.status_code == 422

    async def test_create_switch_with_non_onie_image(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        """Test creating a new switch with a non-onie image."""
        services_mock.switches = Mock(SwitchesService)
        services_mock.interfaces = Mock(InterfacesService)
        services_mock.interfaces.list.return_value = ListResult[Interface](
            items=[], total=0
        )

        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_one.side_effect = [
            BootResource(
                id=2,
                rtype=BootResourceType.UPLOADED,
                name="ubuntu/noble",
                architecture="amd64/generic",
                extra={},
                rolling=False,
                base_image="",
            )
        ]

        new_switch_data = {
            "mac_address": "00:11:22:33:44:55",
            "image": "ubuntu/noble",
        }

        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}", json=new_switch_data
        )
        assert response.status_code == 422

    async def test_create_switch_with_assigned_interface(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        """Test creating a switch with a MAC address already assigned to another entity fails."""
        services_mock.switches = Mock(SwitchesService)
        services_mock.interfaces = Mock(InterfacesService)
        services_mock.interfaces.list.return_value = ListResult[Interface](
            items=[
                Interface(
                    id=1,
                    created=datetime.now(timezone.utc),
                    updated=datetime.now(timezone.utc),
                    name="eth0",
                    mac_address="00:11:22:33:44:55",
                    switch_id=1,  # Already assigned to a switch
                    type=InterfaceType.PHYSICAL,
                )
            ],
            total=1,
        )

        new_switch_data = {
            "mac_address": "00:11:22:33:44:55",  # Same as existing interface
        }

        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}", json=new_switch_data
        )
        assert response.status_code == 409

    async def test_create_switch_claims_unknown_interface(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        """Test creating a switch claims an existing UNKNOWN interface."""
        services_mock.switches = Mock(SwitchesService)
        services_mock.interfaces = Mock(InterfacesService)
        # Return an UNKNOWN interface with no assignments
        services_mock.interfaces.list.return_value = ListResult[Interface](
            items=[
                Interface(
                    id=1,
                    created=datetime.now(timezone.utc),
                    updated=datetime.now(timezone.utc),
                    name="eth0",
                    mac_address="00:11:22:33:44:55",
                    node_config_id=None,  # Not assigned to a node
                    switch_id=None,  # Not assigned to a switch
                    type=InterfaceType.UNKNOWN,  # UNKNOWN interface
                )
            ],
            total=1,
        )
        services_mock.switches.create_switch_and_link_interface.return_value = TEST_SWITCH

        new_switch_data = {
            "mac_address": "00:11:22:33:44:55",
        }

        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}", json=new_switch_data
        )
        assert response.status_code == 201
        assert response.headers["Location"] == f"{self.BASE_PATH}/1"
        # Verify that create_switch_and_link_interface was called instead of create_new_switch_and_interface
        services_mock.switches.create_switch_and_link_interface.assert_called_once()

    async def test_update_switch(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        """Test updating an existing switch."""
        services_mock.switches = Mock(SwitchesService)
        services_mock.switches.get_by_id.return_value = TEST_SWITCH
        updated_switch = Switch(
            **{
                **TEST_SWITCH.dict(),
                "target_image_id": TEST_NOS_IMAGE.id,
                "target_image": TEST_NOS_IMAGE.name,
            }
        )
        services_mock.switches.update_by_id.return_value = updated_switch

        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_one.return_value = TEST_NOS_IMAGE
        services_mock.boot_resources.get_by_id.return_value = TEST_NOS_IMAGE

        update_data = {
            "image": TEST_NOS_IMAGE.name,
        }

        response = await mocked_api_client_admin.patch(
            f"{self.BASE_PATH}/1", json=update_data
        )
        assert response.status_code == 200

        switch_response = SwitchResponse(**response.json())
        assert switch_response.target_image_id == TEST_NOS_IMAGE.id
        assert switch_response.target_image == TEST_NOS_IMAGE.name

    async def test_update_switch_not_found(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        """Test updating a non-existent switch returns 404."""
        services_mock.switches = Mock(SwitchesService)
        services_mock.switches.get_by_id.return_value = None

        update_data = {
            "image": "onie/dellos10",
        }

        response = await mocked_api_client_admin.patch(
            f"{self.BASE_PATH}/999", json=update_data
        )
        assert response.status_code == 404

    async def test_update_switch_image_not_found(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        """Test updating a switch with non-existent image returns 422."""
        services_mock.switches = Mock(SwitchesService)
        services_mock.switches.get_by_id.return_value = TEST_SWITCH

        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_one.return_value = None

        update_data = {
            "image": "onie/not-an-image",
        }

        response = await mocked_api_client_admin.patch(
            f"{self.BASE_PATH}/1", json=update_data
        )
        assert response.status_code == 422

    async def test_delete_switch(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        """Test deleting a switch."""
        services_mock.switches = Mock(SwitchesService)
        services_mock.switches.get_by_id.return_value = TEST_SWITCH
        services_mock.switches.delete_by_id.return_value = None

        response = await mocked_api_client_admin.delete(f"{self.BASE_PATH}/1")
        assert response.status_code == 204

    async def test_delete_switch_not_found(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        """Test deleting a non-existent switch returns 404."""
        services_mock.switches = Mock(SwitchesService)
        services_mock.switches.delete_by_id.side_effect = NotFoundException()

        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/999"
        )
        assert response.status_code == 404
