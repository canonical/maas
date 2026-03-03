# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Union

from fastapi import Depends, Header, Response
from starlette import status

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    ConflictBodyResponse,
    NotFoundBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.query import PaginationParams
from maasapiserver.v3.api.public.models.requests.usergroups import (
    UserGroupRequest,
)
from maasapiserver.v3.api.public.models.responses.base import (
    OPENAPI_ETAG_HEADER,
)
from maasapiserver.v3.api.public.models.responses.usergroups import (
    UserGroupResponse,
    UserGroupsListResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.services import ServiceCollectionV3


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
