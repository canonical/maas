# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Union

from fastapi import Depends, Header, Query, Response, status

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    BadRequestBodyResponse,
    BadRequestResponse,
    ConflictBodyResponse,
    NotFoundBodyResponse,
    NotFoundResponse,
    PreconditionFailedBodyResponse,
    UnauthorizedBodyResponse,
    ValidationErrorBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.query import PaginationParams
from maasapiserver.v3.api.public.models.requests.users import UserRequest
from maasapiserver.v3.api.public.models.responses.base import (
    OPENAPI_ETAG_HEADER,
)
from maasapiserver.v3.api.public.models.responses.users import (
    UserInfoResponse,
    UserResponse,
    UsersListResponse,
)
from maasapiserver.v3.auth.base import (
    check_permissions,
    get_authenticated_user,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.users import UserClauseFactory
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    UnauthorizedException,
)
from maasservicelayer.exceptions.constants import (
    INVALID_ARGUMENT_VIOLATION_TYPE,
    UNEXISTING_USER_OR_INVALID_CREDENTIALS_VIOLATION_TYPE,
)
from maasservicelayer.models.auth import AuthenticatedUser
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.utils.date import utcnow


class UsersHandler(Handler):
    """Users API handler."""

    TAGS = ["Users"]

    def get_handlers(self):
        # The '/me' path component matches both /users/me and /users/{user_id},
        # the default dir(self) returns a handler registration order that is
        # alphabetically ordered, meaning /users/me would get handled by the
        # /users/{user_id}. Therefore we need to specify a custom registration
        # order to disambiguate these paths.
        return [
            "get_user_info",
            "list_users",
            "get_user",
            "create_user",
            "update_user",
            "delete_user",
        ]

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
        user = await services.users.get_one(
            QuerySpec(
                UserClauseFactory.with_username(authenticated_user.username)
            )
        )
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

    @handler(
        path="/users",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": UsersListResponse,
            },
            422: {"model": ValidationErrorBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_users(
        self,
        pagination_params: PaginationParams = Depends(),
        services: ServiceCollectionV3 = Depends(services),
    ) -> UsersListResponse:
        users = await services.users.list(
            page=pagination_params.page,
            size=pagination_params.size,
        )
        return UsersListResponse(
            items=[
                UserResponse.from_model(
                    user=user,
                    self_base_hyperlink=f"{V3_API_PREFIX}/users",
                )
                for user in users.items
            ],
            total=users.total,
            next=(
                f"{V3_API_PREFIX}/users?"
                f"{pagination_params.to_next_href_format()}"
                if users.has_next(
                    pagination_params.page, pagination_params.size
                )
                else None
            ),
        )

    @handler(
        path="/users/{user_id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": UserResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            404: {"model": NotFoundBodyResponse},
            422: {"model": ValidationErrorBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def get_user(
        self,
        user_id: int,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),
    ) -> UserResponse:
        user = await services.users.get_by_id(user_id)
        if not user:
            return NotFoundResponse()

        response.headers["ETag"] = user.etag()
        return UserResponse.from_model(
            user=user,
            self_base_hyperlink=f"{V3_API_PREFIX}/users",
        )

    @handler(
        path="/users",
        methods=["POST"],
        tags=TAGS,
        responses={
            201: {
                "model": UserResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            409: {"model": ConflictBodyResponse},
            422: {"model": ValidationErrorBodyResponse},
        },
        status_code=201,
        response_model_exclude_none=True,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def create_user(
        self,
        user_request: UserRequest,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),
    ) -> UserResponse:
        builder = user_request.to_builder()
        builder.date_joined = utcnow()

        new_user = await services.users.create(builder)

        response.headers["ETag"] = new_user.etag()
        return UserResponse.from_model(
            user=new_user, self_base_hyperlink=f"{V3_API_PREFIX}/users"
        )

    @handler(
        path="/users/{user_id}",
        methods=["PUT"],
        tags=TAGS,
        responses={
            200: {
                "model": UserResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            404: {"model": NotFoundBodyResponse},
            422: {"model": ValidationErrorBodyResponse},
        },
        status_code=200,
        response_model_exclude_none=True,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def update_user(
        self,
        user_id: int,
        user_request: UserRequest,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),
    ) -> UserResponse:
        user = await services.users.update_by_id(
            user_id, user_request.to_builder()
        )
        if not user:
            return NotFoundResponse()

        response.headers["ETag"] = user.etag()
        return UserResponse.from_model(
            user=user,
            self_base_hyperlink=f"{V3_API_PREFIX}/users",
        )

    @handler(
        path="/users/{user_id}",
        methods=["DELETE"],
        tags=TAGS,
        responses={
            204: {},
            400: {"model": BadRequestBodyResponse},
            404: {"model": NotFoundBodyResponse},
            412: {"model": PreconditionFailedBodyResponse},
            422: {"model": ValidationErrorBodyResponse},
        },
        status_code=204,
        response_model_exclude_none=True,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def delete_user(
        self,
        user_id: int,
        authenticated_user: AuthenticatedUser | None = Depends(
            get_authenticated_user
        ),
        services: ServiceCollectionV3 = Depends(services),
        etag_if_match: Union[str, None] = Header(
            alias="if-match", default=None
        ),
        transfer_resources_to: int | None = Query(
            description="The id of the user to transfer the resources to.",
            default=None,
        ),
    ) -> Response:
        assert authenticated_user is not None
        user = await services.users.get_by_id(user_id)
        if not user:
            return NotFoundResponse()
        if user.id == authenticated_user.id:
            return BadRequestResponse(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_ARGUMENT_VIOLATION_TYPE,
                        message="An administrator cannot self-delete.",
                    )
                ]
            )
        if transfer_resources_to is not None:
            await services.users.transfer_resources(
                user_id, transfer_resources_to
            )

        await services.users.delete_by_id(user_id, etag_if_match=etag_if_match)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
