# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Depends, Response

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    ConflictBodyResponse,
    NotFoundBodyResponse,
    NotFoundResponse,
    ValidationErrorBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.query import (
    TokenPaginationParams,
)
from maasapiserver.v3.api.public.models.requests.resource_pools import (
    ResourcePoolRequest,
    ResourcePoolUpdateRequest,
)
from maasapiserver.v3.api.public.models.responses.resource_pools import (
    ResourcePoolResponse,
    ResourcePoolsListResponse,
)
from maasapiserver.v3.auth.base import (
    check_permissions,
    get_authenticated_user,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.resource_pools import (
    ResourcePoolClauseFactory,
    ResourcePoolResourceBuilder,
)
from maasservicelayer.enums.rbac import RbacPermission
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    ForbiddenException,
)
from maasservicelayer.exceptions.constants import (
    MISSING_PERMISSIONS_VIOLATION_TYPE,
)
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.utils.date import utcnow


class ResourcePoolHandler(Handler):
    """ResourcePool API handler."""

    TAGS = ["ResourcePool"]

    @handler(
        path="/resource_pools",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": ResourcePoolsListResponse,
            },
            422: {"model": ValidationErrorBodyResponse},
        },
        status_code=200,
        response_model_exclude_none=True,
        dependencies=[
            Depends(
                check_permissions(
                    required_roles={UserRole.USER},
                    rbac_permissions={
                        RbacPermission.VIEW,
                        RbacPermission.VIEW_ALL,
                    },
                )
            )
        ],
    )
    async def list_resource_pools(
        self,
        token_pagination_params: TokenPaginationParams = Depends(),
        authenticated_user=Depends(get_authenticated_user),
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        query = None
        if authenticated_user.rbac_permissions:
            query = QuerySpec(
                where=ResourcePoolClauseFactory.with_ids(
                    ids=(
                        authenticated_user.rbac_permissions.visible_pools
                        | authenticated_user.rbac_permissions.view_all_pools
                    )
                )
            )
        resource_pools = await services.resource_pools.list(
            token=token_pagination_params.token,
            size=token_pagination_params.size,
            query=query,
        )
        return ResourcePoolsListResponse(
            items=[
                ResourcePoolResponse.from_model(
                    resource_pool=resource_pools,
                    self_base_hyperlink=f"{V3_API_PREFIX}/resource_pools",
                )
                for resource_pools in resource_pools.items
            ],
            next=(
                f"{V3_API_PREFIX}/resource_pools?"
                f"{TokenPaginationParams.to_href_format(resource_pools.next_token, token_pagination_params.size)}"
                if resource_pools.next_token
                else None
            ),
        )

    @handler(
        path="/resource_pools",
        methods=["POST"],
        tags=TAGS,
        responses={
            201: {
                "model": ResourcePoolResponse,
                "headers": {
                    "ETag": {"description": "The ETag for the resource"}
                },
            },
            409: {"model": ConflictBodyResponse},
            422: {"model": ValidationErrorBodyResponse},
        },
        status_code=201,
        response_model_exclude_none=True,
        dependencies=[
            Depends(
                check_permissions(
                    required_roles={UserRole.ADMIN},
                    rbac_permissions={
                        RbacPermission.EDIT,
                    },
                )
            )
        ],
    )
    async def create_resource_pool(
        self,
        response: Response,
        resource_pool_request: ResourcePoolRequest,
        authenticated_user=Depends(get_authenticated_user),
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        if (
            authenticated_user.rbac_permissions
            and not authenticated_user.rbac_permissions.can_edit_all_resource_pools
        ):
            raise ForbiddenException(
                details=[
                    BaseExceptionDetail(
                        type=MISSING_PERMISSIONS_VIOLATION_TYPE,
                        message="The user does not have the permissions to access this endpoint.",
                    )
                ]
            )
        now = utcnow()
        resource = (
            ResourcePoolResourceBuilder()
            .with_name(resource_pool_request.name)
            .with_description(resource_pool_request.description)
            .with_created(now)
            .with_updated(now)
            .build()
        )
        resource_pool = await services.resource_pools.create(resource)
        response.headers["ETag"] = resource_pool.etag()
        return ResourcePoolResponse.from_model(
            resource_pool=resource_pool,
            self_base_hyperlink=f"{V3_API_PREFIX}/resource_pools",
        )

    @handler(
        path="/resource_pools/{resource_pool_id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": ResourcePoolResponse,
                "headers": {
                    "ETag": {"description": "The ETag for the resource"}
                },
            },
            404: {"model": NotFoundBodyResponse},
            422: {"model": ValidationErrorBodyResponse},
        },
        status_code=200,
        response_model_exclude_none=True,
        dependencies=[
            Depends(
                check_permissions(
                    required_roles={UserRole.USER},
                    rbac_permissions={
                        RbacPermission.VIEW,
                    },
                )
            )
        ],
    )
    async def get_resource_pool(
        self,
        resource_pool_id: int,
        response: Response,
        authenticated_user=Depends(get_authenticated_user),
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        if (
            authenticated_user.rbac_permissions
            and resource_pool_id
            not in authenticated_user.rbac_permissions.visible_pools
        ):
            raise ForbiddenException(
                details=[
                    BaseExceptionDetail(
                        type=MISSING_PERMISSIONS_VIOLATION_TYPE,
                        message="The user does not have the permissions to view this resource pool.",
                    )
                ]
            )
        if resource_pool := await services.resource_pools.get_by_id(
            resource_pool_id
        ):
            response.headers["ETag"] = resource_pool.etag()
            return ResourcePoolResponse.from_model(
                resource_pool=resource_pool,
                self_base_hyperlink=f"{V3_API_PREFIX}/resource_pools",
            )
        return NotFoundResponse()

    @handler(
        path="/resource_pools/{resource_pool_id}",
        methods=["PUT"],
        tags=TAGS,
        responses={
            200: {
                "model": ResourcePoolResponse,
                "headers": {
                    "ETag": {"description": "The ETag for the resource"}
                },
            },
            404: {"model": NotFoundBodyResponse},
            422: {"model": ValidationErrorBodyResponse},
        },
        status_code=200,
        response_model_exclude_none=True,
        dependencies=[
            Depends(
                check_permissions(
                    required_roles={UserRole.ADMIN},
                    rbac_permissions={
                        RbacPermission.EDIT,
                    },
                )
            )
        ],
    )
    async def update_resource_pool(
        self,
        resource_pool_id: int,
        response: Response,
        resource_pool_request: ResourcePoolUpdateRequest,
        authenticated_user=Depends(get_authenticated_user),
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        if (
            authenticated_user.rbac_permissions
            and resource_pool_id
            not in authenticated_user.rbac_permissions.edit_pools
        ):
            raise ForbiddenException(
                details=[
                    BaseExceptionDetail(
                        type=MISSING_PERMISSIONS_VIOLATION_TYPE,
                        message="The user does not have the permissions to edit this resource pool.",
                    )
                ]
            )
        resource = (
            ResourcePoolResourceBuilder()
            .with_name(resource_pool_request.name)
            .with_description(resource_pool_request.description)
            .with_updated(utcnow())
            .build()
        )
        resource_pool = await services.resource_pools.update_by_id(
            resource_pool_id, resource
        )
        response.headers["ETag"] = resource_pool.etag()
        return ResourcePoolResponse.from_model(
            resource_pool=resource_pool,
            self_base_hyperlink=f"{V3_API_PREFIX}/resource_pools",
        )
