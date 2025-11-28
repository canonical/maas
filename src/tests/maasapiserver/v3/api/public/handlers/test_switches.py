#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

from httpx import AsyncClient
import pytest

from maasapiserver.v3.api.public.models.responses.switches import (
    SwitchesListResponse,
    SwitchResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.switches import Switch
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.switches import SwitchesService
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

TEST_SWITCH = Switch(
    id=1,
    name="test-switch",
    mac_address="00:11:22:33:44:55",
    ip_address="192.168.1.100",
    model="Cisco Catalyst 2960",
    manufacturer="Cisco",
    description="Test network switch",
    vlan_id=1,
    subnet_id=1,
    created=utcnow(),
    updated=utcnow(),
)

TEST_SWITCH_2 = Switch(
    id=2,
    name="test-switch-2",
    mac_address="aa:bb:cc:dd:ee:ff",
    ip_address="192.168.1.101",
    model="Juniper EX2200",
    manufacturer="Juniper",
    description="Another test switch",
    vlan_id=1,
    subnet_id=1,
    created=utcnow(),
    updated=utcnow(),
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
            Endpoint(method="PUT", path=f"{self.BASE_PATH}/1"),
            Endpoint(method="DELETE", path=f"{self.BASE_PATH}/1"),
        ]

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

        response = await mocked_api_client_user.get(f"{self.BASE_PATH}")
        assert response.status_code == 200

        switches_response = SwitchesListResponse(**response.json())
        assert len(switches_response.items) == 2
        assert switches_response.total == 2
        assert switches_response.items[0].name == "test-switch"
        assert switches_response.items[1].name == "test-switch-2"

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
        assert switch_response.name == "test-switch"
        assert switch_response.mac_address == "00:11:22:33:44:55"

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
        services_mock.switches.list.return_value = ListResult[Switch](
            items=[], total=0
        )
        services_mock.switches.create.return_value = TEST_SWITCH

        new_switch_data = {
            "name": "test-switch",
            "mac_address": "00:11:22:33:44:55",
            "ip_address": "192.168.1.100",
            "model": "Cisco Catalyst 2960",
            "manufacturer": "Cisco",
            "description": "Test network switch",
            "vlan_id": 1,
            "subnet_id": 1,
        }

        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}", json=new_switch_data
        )
        assert response.status_code == 201
        assert response.headers["Location"] == f"{self.BASE_PATH}/1"

        switch_response = SwitchResponse(**response.json())
        assert switch_response.name == "test-switch"
        assert switch_response.mac_address == "00:11:22:33:44:55"

    async def test_create_switch_duplicate_mac(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        """Test creating a switch with duplicate MAC address fails."""
        services_mock.switches = Mock(SwitchesService)
        services_mock.switches.list.return_value = ListResult[Switch](
            items=[TEST_SWITCH], total=1
        )

        new_switch_data = {
            "name": "duplicate-switch",
            "mac_address": "00:11:22:33:44:55",  # Same as TEST_SWITCH
        }

        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}", json=new_switch_data
        )
        assert response.status_code == 409

    async def test_update_switch(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        """Test updating an existing switch."""
        services_mock.switches = Mock(SwitchesService)
        services_mock.switches.get_by_id.return_value = TEST_SWITCH
        services_mock.switches.list.return_value = ListResult[Switch](
            items=[], total=0
        )

        updated_switch = Switch(
            **{
                **TEST_SWITCH.dict(),
                "name": "updated-switch",
                "description": "Updated description",
            }
        )
        services_mock.switches.update_by_id.return_value = updated_switch

        update_data = {
            "name": "updated-switch",
            "mac_address": "00:11:22:33:44:55",
            "description": "Updated description",
        }

        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/1", json=update_data
        )
        assert response.status_code == 200

        switch_response = SwitchResponse(**response.json())
        assert switch_response.name == "updated-switch"
        assert switch_response.description == "Updated description"

    async def test_update_switch_not_found(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        """Test updating a non-existent switch returns 404."""
        services_mock.switches = Mock(SwitchesService)
        services_mock.switches.get_by_id.return_value = None

        update_data = {
            "name": "updated-switch",
            "mac_address": "00:11:22:33:44:55",
        }

        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/999", json=update_data
        )
        assert response.status_code == 404

    async def test_update_switch_duplicate_mac(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        """Test updating a switch to a duplicate MAC address fails."""
        services_mock.switches = Mock(SwitchesService)
        services_mock.switches.get_by_id.return_value = TEST_SWITCH
        services_mock.switches.list.return_value = ListResult[Switch](
            items=[TEST_SWITCH_2], total=1
        )

        update_data = {
            "name": "test-switch",
            "mac_address": "aa:bb:cc:dd:ee:ff",  # Same as TEST_SWITCH_2
        }

        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/1", json=update_data
        )
        assert response.status_code == 409

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
        services_mock.switches.get_by_id.return_value = None

        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/999"
        )
        assert response.status_code == 404
