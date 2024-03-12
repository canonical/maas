from fastapi import Depends, Response

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    ConflictBodyResponse,
    NotFoundBodyResponse,
    NotFoundResponse,
    ValidationErrorBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.models.requests.query import PaginationParams
from maasapiserver.v3.api.models.requests.resource_pools import (
    ResourcePoolPatchRequest,
    ResourcePoolRequest,
)
from maasapiserver.v3.api.models.responses.resource_pools import (
    ResourcePoolResponse,
    ResourcePoolsListResponse,
)
from maasapiserver.v3.constants import EXTERNAL_V3_API_PREFIX
from maasapiserver.v3.services import ServiceCollectionV3


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
    )
    async def list_resource_pools(
        self,
        pagination_params: PaginationParams = Depends(),
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        resource_pools = await services.resource_pools.list(pagination_params)
        return ResourcePoolsListResponse(
            items=[
                resource_pools.to_response(
                    f"{EXTERNAL_V3_API_PREFIX}/resource_pools"
                )
                for resource_pools in resource_pools.items
            ],
            total=resource_pools.total,
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
    )
    async def create_resource_pool(
        self,
        response: Response,
        resource_pool_request: ResourcePoolRequest,
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        resource_pools = await services.resource_pools.create(
            resource_pool_request
        )
        response.headers["ETag"] = resource_pools.etag()
        return resource_pools.to_response(
            self_base_hyperlink=f"{EXTERNAL_V3_API_PREFIX}/resource_pools"
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
    )
    async def get_resource_pool(
        self,
        resource_pool_id: int,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        if resource_pool := await services.resource_pools.get_by_id(
            resource_pool_id
        ):
            response.headers["ETag"] = resource_pool.etag()
            return resource_pool.to_response(
                self_base_hyperlink=f"{EXTERNAL_V3_API_PREFIX}/resource_pools"
            )
        return NotFoundResponse()

    @handler(
        path="/resource_pools/{resource_pool_id}",
        methods=["PATCH"],
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
    )
    async def patch_resource_pool(
        self,
        resource_pool_id: int,
        response: Response,
        resource_pool_request: ResourcePoolPatchRequest,
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        resource_pool = await services.resource_pools.patch(
            resource_pool_id, resource_pool_request
        )
        response.headers["ETag"] = resource_pool.etag()
        return resource_pool.to_response(
            self_base_hyperlink=f"{EXTERNAL_V3_API_PREFIX}/resource_pools"
        )
