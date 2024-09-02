# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Depends

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    UnauthorizedBodyResponse,
)
from maasapiserver.common.models.constants import (
    UNEXISTING_USER_OR_INVALID_CREDENTIALS_VIOLATION_TYPE,
)
from maasapiserver.common.models.exceptions import (
    BaseExceptionDetail,
    UnauthorizedException,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.responses.users import UserInfoResponse
from maasapiserver.v3.auth.base import (
    check_permissions,
    get_authenticated_user,
)
from maasapiserver.v3.services import ServiceCollectionV3
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.models.auth import AuthenticatedUser


class UsersHandler(Handler):
    """Users API handler."""

    TAGS = ["Users"]

    @handler(
        path="/users/me",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": UserInfoResponse,
            },
            401: {"model": UnauthorizedBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def get_user_info(
        self,
        authenticated_user: AuthenticatedUser | None = Depends(
            get_authenticated_user
        ),
        services: ServiceCollectionV3 = Depends(services),
    ) -> UserInfoResponse:
        assert authenticated_user is not None
        user = await services.users.get(username=authenticated_user.username)
        if user is None:
            raise UnauthorizedException(
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_USER_OR_INVALID_CREDENTIALS_VIOLATION_TYPE,
                        message="The user does not exist",
                    )
                ]
            )
        return UserInfoResponse(
            id=user.id, username=user.username, is_superuser=user.is_superuser
        )
