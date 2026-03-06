# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Union

from fastapi import Depends, Header, Query, Response
from starlette import status

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    BadRequestBodyResponse,
    ConflictBodyResponse,
    NotFoundBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.entitlements import (
    EntitlementRequest,
)
from maasapiserver.v3.api.public.models.requests.query import PaginationParams
from maasapiserver.v3.api.public.models.requests.usergroup_members import (
    UserGroupMemberRequest,
)
from maasapiserver.v3.api.public.models.requests.usergroups import (
    UserGroupRequest,
)
from maasapiserver.v3.api.public.models.responses.base import (
    OPENAPI_ETAG_HEADER,
)
from maasapiserver.v3.api.public.models.responses.entitlements import (
    EntitlementResponse,
    EntitlementsListResponse,
)
from maasapiserver.v3.api.public.models.responses.usergroup_members import (
    UserGroupMemberResponse,
    UserGroupMembersListResponse,
)
from maasapiserver.v3.api.public.models.responses.usergroups import (
    UserGroupResponse,
    UserGroupsListResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.openfga.base import OpenFGAEntitlementResourceType
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.exceptions.catalog import (
    BadRequestException,
    BaseExceptionDetail,
    ConflictException,
    NotFoundException,
)
from maasservicelayer.exceptions.constants import (
    INVALID_ARGUMENT_VIOLATION_TYPE,
    USER_ALREADY_IN_GROUP,
)
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.openfga_tuples import EntitlementsBuilderFactory
from maasservicelayer.services.usergroups import (
    UserAlreadyInGroup,
    UserGroupNotFound,
)


class UserGroupsHandler(Handler):
    """User Groups API handler."""

    TAGS = ["UserGroups"]

    @handler(
        path="/groups",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": UserGroupsListResponse,
            },
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_groups(
        self,
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> UserGroupsListResponse:
        groups = await services.usergroups.list(
            page=pagination_params.page,
            size=pagination_params.size,
        )
        next_link = None
        if groups.has_next(pagination_params.page, pagination_params.size):
            next_link = (
                f"{V3_API_PREFIX}/groups?"
                f"{pagination_params.to_next_href_format()}"
            )

        return UserGroupsListResponse(
            items=[
                UserGroupResponse.from_model(
                    usergroup=group,
                    self_base_hyperlink=f"{V3_API_PREFIX}/groups",
                )
                for group in groups.items
            ],
            total=groups.total,
            next=next_link,
        )

    @handler(
        path="/groups",
        methods=["POST"],
        tags=TAGS,
        responses={
            201: {
                "model": UserGroupResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            409: {"model": ConflictBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=201,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def create_group(
        self,
        response: Response,
        group_request: UserGroupRequest,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> UserGroupResponse:
        group = await services.usergroups.create(group_request.to_builder())
        response.headers["ETag"] = group.etag()
        return UserGroupResponse.from_model(
            usergroup=group,
            self_base_hyperlink=f"{V3_API_PREFIX}/groups",
        )

    @handler(
        path="/groups/{group_id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": UserGroupResponse,
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
    async def get_group(
        self,
        group_id: int,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> UserGroupResponse:
        group = await services.usergroups.get_by_id(group_id)
        if not group:
            raise NotFoundException()

        response.headers["ETag"] = group.etag()
        return UserGroupResponse.from_model(
            usergroup=group,
            self_base_hyperlink=f"{V3_API_PREFIX}/groups",
        )

    @handler(
        path="/groups/{group_id}",
        methods=["PUT"],
        tags=TAGS,
        responses={
            200: {
                "model": UserGroupResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def update_group(
        self,
        group_id: int,
        group_request: UserGroupRequest,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> UserGroupResponse:
        group = await services.usergroups.update_by_id(
            group_id, group_request.to_builder()
        )
        if not group:
            raise NotFoundException()

        response.headers["ETag"] = group.etag()
        return UserGroupResponse.from_model(
            usergroup=group,
            self_base_hyperlink=f"{V3_API_PREFIX}/groups",
        )

    @handler(
        path="/groups/{group_id}",
        methods=["DELETE"],
        tags=TAGS,
        responses={
            204: {},
            404: {"model": NotFoundBodyResponse},
        },
        status_code=204,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def delete_group(
        self,
        group_id: int,
        etag_if_match: Union[str, None] = Header(
            alias="if-match", default=None
        ),
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        await services.usergroups.delete_by_id(group_id, etag_if_match)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # Membership endpoints

    @handler(
        path="/groups/{group_id}/members",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": UserGroupMembersListResponse,
            },
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_group_members(
        self,
        group_id: int,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> UserGroupMembersListResponse:
        group = await services.usergroups.get_by_id(group_id)
        if not group:
            raise NotFoundException()

        members = await services.usergroups.list_usergroup_members(group_id)
        return UserGroupMembersListResponse(
            items=[
                UserGroupMemberResponse.from_model(member)
                for member in members
            ],
        )

    @handler(
        path="/groups/{group_id}/members",
        methods=["POST"],
        tags=TAGS,
        responses={
            200: {},
            404: {"model": NotFoundBodyResponse},
            409: {"model": ConflictBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def add_group_member(
        self,
        group_id: int,
        member_request: UserGroupMemberRequest,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        user = await services.users.get_by_id(id=member_request.user_id)
        if not user:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_ARGUMENT_VIOLATION_TYPE,
                        message=str(
                            f"User with ID `{member_request.user_id}` not found.`"
                        ),
                    )
                ]
            )

        try:
            await services.usergroups.add_user_to_group_by_id(
                member_request.user_id, group_id
            )
        except UserGroupNotFound as err:
            raise NotFoundException() from err
        except UserAlreadyInGroup as err:
            raise ConflictException(
                details=[
                    BaseExceptionDetail(
                        type=USER_ALREADY_IN_GROUP,
                        message=str(err),
                    )
                ]
            ) from err

        return Response(status_code=200)

    @handler(
        path="/groups/{group_id}/members/{user_id}",
        methods=["DELETE"],
        tags=TAGS,
        responses={
            204: {},
            404: {"model": NotFoundBodyResponse},
        },
        status_code=204,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def remove_group_member(
        self,
        group_id: int,
        user_id: int,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        group = await services.usergroups.get_by_id(group_id)
        if not group:
            raise NotFoundException()

        await services.usergroups.remove_user_from_group(group_id, user_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # Entitlement endpoints

    @handler(
        path="/groups/{group_id}/entitlements",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": EntitlementsListResponse,
            },
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_group_entitlements(
        self,
        group_id: int,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> EntitlementsListResponse:
        group = await services.usergroups.get_by_id(group_id)
        if not group:
            raise NotFoundException()

        entitlements = await services.openfga_tuples.list_entitlements(
            group_id
        )
        return EntitlementsListResponse(
            items=[EntitlementResponse.from_model(t) for t in entitlements],
        )

    @handler(
        path="/groups/{group_id}/entitlements",
        methods=["POST"],
        tags=TAGS,
        responses={
            200: {
                "model": EntitlementResponse,
            },
            400: {"model": BadRequestBodyResponse},
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def add_group_entitlement(
        self,
        group_id: int,
        entitlement_request: EntitlementRequest,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> EntitlementResponse:
        group = await services.usergroups.get_by_id(group_id)
        if not group:
            raise NotFoundException()

        builder = await entitlement_request.to_builder(group_id, services)
        openfga_tuple = await services.openfga_tuples.upsert(builder)
        return EntitlementResponse.from_model(openfga_tuple)

    @handler(
        path="/groups/{group_id}/entitlements",
        methods=["DELETE"],
        tags=TAGS,
        responses={
            204: {},
            400: {"model": BadRequestBodyResponse},
            404: {"model": NotFoundBodyResponse},
        },
        status_code=204,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def remove_group_entitlement(
        self,
        group_id: int,
        resource_type: OpenFGAEntitlementResourceType = Query(),  # noqa: B008
        resource_id: int = Query(),  # noqa: B008
        entitlement: str = Query(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        group = await services.usergroups.get_by_id(group_id)
        if not group:
            raise NotFoundException()

        is_valid, error_message = (
            EntitlementsBuilderFactory.validate_entitlement(
                entitlement, resource_type
            )
        )
        if not is_valid:
            raise BadRequestException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_ARGUMENT_VIOLATION_TYPE,
                        message=error_message,  # type: ignore[reportArgumentType]
                    )
                ]
            )

        await services.openfga_tuples.delete_entitlement(
            group_id, entitlement, resource_type, resource_id
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
