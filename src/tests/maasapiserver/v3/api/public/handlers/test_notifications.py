# Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Callable
from unittest.mock import Mock

from httpx import AsyncClient
import pytest

from maasapiserver.v3.api.public.models.responses.notifications import (
    NotificationResponse,
    NotificationsListResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.notifications import NotificationCategoryEnum
from maascommon.openfga.base import MAASResourceEntitlement
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.notifications import Notification
from maasservicelayer.services import OpenFGATupleService, ServiceCollectionV3
from maasservicelayer.services.notifications import NotificationsService
from tests.maasapiserver.fixtures.app import AsyncOpenFGAClientMock
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

TEST_NOTIFICATION = Notification(
    id=1,
    ident="deprecation_MD5_users",
    message="Foo is deprecated, please update {variable}",
    users=True,
    admins=False,
    context={"variable": "now"},
    user_id=None,
    category=NotificationCategoryEnum.WARNING,
    dismissable=True,
)


class TestNotificationsApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/notifications"

    @pytest.fixture
    def endpoints_with_authorization(self) -> list[Endpoint]:
        return [
            Endpoint(
                method="PUT",
                path=f"{self.BASE_PATH}/1",
                permission=MAASResourceEntitlement.CAN_EDIT_NOTIFICATIONS,
            ),
            Endpoint(
                method="POST",
                path=f"{self.BASE_PATH}",
                permission=MAASResourceEntitlement.CAN_EDIT_NOTIFICATIONS,
            ),
            Endpoint(
                method="DELETE",
                path=f"{self.BASE_PATH}/2",
                permission=MAASResourceEntitlement.CAN_EDIT_NOTIFICATIONS,
            ),
        ]

    @pytest.fixture
    def endpoints_with_authentication_only(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=f"{self.BASE_PATH}"),
            Endpoint(method="GET", path=f"{self.BASE_PATH}/2"),
            Endpoint(method="POST", path=f"{self.BASE_PATH}/2:dismiss"),
        ]

    async def test_list_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_NOTIFICATIONS,
        )
        services_mock.notifications = Mock(NotificationsService)
        services_mock.notifications.list_all_for_user.return_value = (
            ListResult[Notification](items=[TEST_NOTIFICATION], total=2)
        )
        response = await client.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        notifications_response = NotificationsListResponse(**response.json())
        assert len(notifications_response.items) == 1
        assert notifications_response.total == 2
        assert notifications_response.next == f"{self.BASE_PATH}?page=2&size=1"

    async def test_list_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_NOTIFICATIONS,
        )
        services_mock.notifications = Mock(NotificationsService)
        services_mock.notifications.list_all_for_user.return_value = (
            ListResult[Notification](items=[TEST_NOTIFICATION], total=1)
        )
        response = await client.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        notifications_response = NotificationsListResponse(**response.json())
        assert len(notifications_response.items) == 1
        assert notifications_response.total == 1
        assert notifications_response.next is None

    async def test_list_only_active_query_param(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_NOTIFICATIONS,
        )
        services_mock.notifications = Mock(NotificationsService)
        services_mock.notifications.list_active_for_user.return_value = (
            ListResult[Notification](items=[TEST_NOTIFICATION], total=1)
        )
        response = await client.get(
            f"{self.BASE_PATH}?size=1&only_active=true"
        )
        assert response.status_code == 200
        notifications_response = NotificationsListResponse(**response.json())
        assert len(notifications_response.items) == 1

        services_mock.notifications.list_active_for_user.assert_called_once()
        services_mock.notifications.list_all_for_user.assert_not_called()

    async def test_get_by_id_user(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: Callable,
    ) -> None:
        services_mock.openfga_tuples = Mock(OpenFGATupleService)
        services_mock.openfga_tuples.get_client.return_value = (
            AsyncOpenFGAClientMock()
        )

        services_mock.notifications = Mock(NotificationsService)
        services_mock.notifications.get_by_id_for_user.return_value = (
            TEST_NOTIFICATION
        )

        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/1")
        assert response.status_code == 200

        services_mock.notifications.get_by_id_for_user.assert_called_once()
        services_mock.notifications.get_by_id.assert_not_called()

    async def test_get_by_id_admin(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_NOTIFICATIONS,
        )
        services_mock.notifications = Mock(NotificationsService)
        services_mock.notifications.get_by_id.return_value = TEST_NOTIFICATION

        response = await client.get(f"{self.BASE_PATH}/1")
        assert response.status_code == 200

        services_mock.notifications.get_by_id_for_user.assert_not_called()
        services_mock.notifications.get_by_id.assert_called_once()

    async def test_create_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_NOTIFICATIONS,
        )
        services_mock.notifications = Mock(NotificationsService)
        services_mock.notifications.create.return_value = TEST_NOTIFICATION
        notification_request = {
            "ident": "deprecation_MD5_users",
            "message": "Foo is deprecated, please update {variable}",
            "for_users": True,
            "for_admins": False,
            "context": {"variable": "now"},
            "user_id": None,
            "category": NotificationCategoryEnum.WARNING,
            "dismissable": True,
        }
        response = await client.post(self.BASE_PATH, json=notification_request)
        assert response.status_code == 200
        notification_response = NotificationResponse(**response.json())
        assert notification_response.kind == "Notification"
        assert notification_response.ident == TEST_NOTIFICATION.ident
        assert (
            notification_response.message
            == "Foo is deprecated, please update now"
        )

    async def test_create_422(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_NOTIFICATIONS,
        )
        services_mock.notifications = Mock(NotificationsService)
        services_mock.notifications.create.return_value = TEST_NOTIFICATION
        response = await client.post(self.BASE_PATH, json={})
        assert response.status_code == 422

    async def test_update(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_NOTIFICATIONS,
        )
        services_mock.notifications = Mock(NotificationsService)
        services_mock.notifications.update_by_id.return_value = (
            TEST_NOTIFICATION
        )
        notification_request = {
            "ident": "deprecation_MD5_users",
            "message": "Foo is deprecated, please update",
            "for_users": True,
            "for_admins": False,
            "context": {},
            "user_id": None,
            "category": NotificationCategoryEnum.WARNING,
            "dismissable": True,
        }
        response = await client.put(
            f"{self.BASE_PATH}/1", json=notification_request
        )
        assert response.status_code == 200
        notification_response = NotificationResponse(**response.json())
        assert notification_response.kind == "Notification"
        assert notification_response.ident == TEST_NOTIFICATION.ident

    async def test_update_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_NOTIFICATIONS,
        )
        services_mock.notifications = Mock(NotificationsService)
        services_mock.notifications.update_by_id.side_effect = (
            NotFoundException()
        )
        notification_request = {
            "ident": "deprecation_MD5_users",
            "message": "Foo is deprecated, please update",
            "for_users": True,
            "for_admins": False,
            "context": {},
            "user_id": None,
            "category": NotificationCategoryEnum.WARNING,
            "dismissable": True,
        }
        response = await client.put(
            f"{self.BASE_PATH}/1", json=notification_request
        )
        assert response.status_code == 404

    async def test_delete(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_NOTIFICATIONS,
        )
        services_mock.notifications = Mock(NotificationsService)
        services_mock.notifications.delete_by_id.return_value = (
            TEST_NOTIFICATION
        )
        response = await client.delete(f"{self.BASE_PATH}/1")
        assert response.status_code == 204

    async def test_delete_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_NOTIFICATIONS,
        )
        services_mock.notifications = Mock(NotificationsService)
        services_mock.notifications.delete_by_id.side_effect = (
            NotFoundException()
        )
        response = await client.delete(f"{self.BASE_PATH}/1")
        assert response.status_code == 404

    async def test_dismiss(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_NOTIFICATIONS,
        )
        services_mock.notifications = Mock(NotificationsService)
        services_mock.notifications.dismiss.return_value = None
        response = await client.post(f"{self.BASE_PATH}/1:dismiss")
        assert response.status_code == 204

    async def test_dismiss_404(
        self, services_mock: ServiceCollectionV3, mocked_api_client_user
    ) -> None:
        services_mock.notifications = Mock(NotificationsService)
        services_mock.notifications.dismiss.side_effect = NotFoundException()
        response = await mocked_api_client_user.post(
            f"{self.BASE_PATH}/1:dismiss"
        )
        assert response.status_code == 404
