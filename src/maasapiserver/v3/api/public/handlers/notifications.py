# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Depends, Query, Response, status

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    NotFoundBodyResponse,
    NotFoundResponse,
    UnauthorizedBodyResponse,
    ValidationErrorBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.handlers.discoveries import PaginationParams
from maasapiserver.v3.api.public.models.requests.notifications import (
    NotificationRequest,
)
from maasapiserver.v3.api.public.models.responses.base import (
    OPENAPI_ETAG_HEADER,
)
from maasapiserver.v3.api.public.models.responses.notifications import (
    NotificationResponse,
    NotificationsListResponse,
)
from maasapiserver.v3.auth.base import (
    check_permissions,
    get_authenticated_user,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.models.auth import AuthenticatedUser
from maasservicelayer.services import ServiceCollectionV3


class NotificationsHandler(Handler):
    """Notifications API handler."""

    TAGS = ["Notifications"]

    @handler(
        path="/notifications",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": NotificationsListResponse,
            },
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_notifications(
        self,
        only_active: bool | None = Query(
            description="Wheter to return only the non-dismissed notifications",
            default=False,
        ),
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        authenticated_user: AuthenticatedUser | None = Depends(  # noqa: B008
            get_authenticated_user
        ),
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        assert authenticated_user is not None
        if only_active:
            notifications_for_user = (
                await services.notifications.list_active_for_user(
                    page=pagination_params.page,
                    size=pagination_params.size,
                    user=authenticated_user,
                )
            )
        else:
            notifications_for_user = (
                await services.notifications.list_all_for_user(
                    page=pagination_params.page,
                    size=pagination_params.size,
                    user=authenticated_user,
                )
            )
        return NotificationsListResponse(
            items=[
                NotificationResponse.from_model(
                    notification=n,
                    self_base_hyperlink=f"{V3_API_PREFIX}/notifications",
                )
                for n in notifications_for_user.items
            ],
            total=notifications_for_user.total,
            next=(
                f"{V3_API_PREFIX}/notifications?"
                f"{pagination_params.to_next_href_format()}"
                if notifications_for_user.has_next(
                    pagination_params.page, pagination_params.size
                )
                else None
            ),
        )

    @handler(
        path="/notifications/{notification_id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": NotificationResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def get_notification(
        self,
        notification_id: int,
        response: Response,
        authenticated_user: AuthenticatedUser | None = Depends(  # noqa: B008
            get_authenticated_user
        ),
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        assert authenticated_user is not None
        if authenticated_user.is_admin():
            # admins can see all the notifications
            notification = await services.notifications.get_by_id(
                notification_id
            )
        else:
            notification = await services.notifications.get_by_id_for_user(
                notification_id=notification_id, user=authenticated_user
            )
        if not notification:
            return NotFoundResponse()
        response.headers["ETag"] = notification.etag()
        return NotificationResponse.from_model(
            notification=notification,
            self_base_hyperlink=f"{V3_API_PREFIX}/notifications",
        )

    @handler(
        path="/notifications",
        methods=["POST"],
        tags=TAGS,
        responses={
            200: {
                "model": NotificationResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            401: {"model": UnauthorizedBodyResponse},
            422: {"model": ValidationErrorBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def create_notification(
        self,
        notification_request: NotificationRequest,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> NotificationResponse:
        notification = await services.notifications.create(
            builder=notification_request.to_builder()
        )
        response.headers["ETag"] = notification.etag()
        return NotificationResponse.from_model(
            notification=notification,
            self_base_hyperlink=f"{V3_API_PREFIX}/notifications",
        )

    @handler(
        path="/notifications/{notification_id}",
        methods=["PUT"],
        tags=TAGS,
        responses={
            200: {
                "model": NotificationResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            401: {"model": UnauthorizedBodyResponse},
            404: {"model": NotFoundBodyResponse},
            422: {"model": ValidationErrorBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def update_notification(
        self,
        notification_id: int,
        notification_request: NotificationRequest,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> NotificationResponse:
        notification = await services.notifications.update_by_id(
            id=notification_id, builder=notification_request.to_builder()
        )
        response.headers["ETag"] = notification.etag()
        return NotificationResponse.from_model(
            notification=notification,
            self_base_hyperlink=f"{V3_API_PREFIX}/notifications",
        )

    @handler(
        path="/notifications/{notification_id}",
        methods=["DELETE"],
        tags=TAGS,
        responses={
            204: {},
            401: {"model": UnauthorizedBodyResponse},
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def delete_notification(
        self,
        notification_id: int,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        await services.notifications.delete_by_id(id=notification_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @handler(
        path="/notifications/{notification_id}:dismiss",
        methods=["POST"],
        tags=TAGS,
        responses={
            204: {},
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def dismiss_notification(
        self,
        notification_id: int,
        authenticated_user: AuthenticatedUser | None = Depends(  # noqa: B008
            get_authenticated_user
        ),
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        assert authenticated_user is not None
        await services.notifications.dismiss(
            notification_id=notification_id, user=authenticated_user
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
