# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Union

from fastapi import Depends, Header, Response
from starlette import status

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    BadRequestBodyResponse,
    ConflictBodyResponse,
    NotFoundBodyResponse,
    NotFoundResponse,
    ValidationErrorBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.fabrics import FabricRequest
from maasapiserver.v3.api.public.models.requests.query import (
    TokenPaginationParams,
)
from maasapiserver.v3.api.public.models.responses.fabrics import (
    FabricResponse,
    FabricsListResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.utils.date import utcnow


class FabricsHandler(Handler):
    """Fabrics API handler."""

    TAGS = ["Fabrics"]

    @handler(
        path="/fabrics",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": FabricsListResponse,
            },
            422: {"model": ValidationErrorBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_fabrics(
        self,
        token_pagination_params: TokenPaginationParams = Depends(),
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        fabrics = await services.fabrics.list(
            token=token_pagination_params.token,
            size=token_pagination_params.size,
        )
        return FabricsListResponse(
            items=[
                FabricResponse.from_model(
                    fabric=fabric,
                    self_base_hyperlink=f"{V3_API_PREFIX}/fabrics",
                )
                for fabric in fabrics.items
            ],
            next=(
                f"{V3_API_PREFIX}/fabrics?"
                f"{TokenPaginationParams.to_href_format(fabrics.next_token, token_pagination_params.size)}"
                if fabrics.next_token
                else None
            ),
        )

    @handler(
        path="/fabrics/{fabric_id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": FabricResponse,
                "headers": {
                    "ETag": {"description": "The ETag for the resource"}
                },
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
    async def get_fabric(
        self,
        fabric_id: int,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        fabric = await services.fabrics.get_by_id(fabric_id)
        if not fabric:
            return NotFoundResponse()

        response.headers["ETag"] = fabric.etag()
        return FabricResponse.from_model(
            fabric=fabric, self_base_hyperlink=f"{V3_API_PREFIX}/fabrics"
        )

    @handler(
        path="/fabrics",
        methods=["POST"],
        tags=TAGS,
        responses={
            201: {
                "model": FabricResponse,
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
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def create_fabric(
        self,
        fabric_request: FabricRequest,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),
    ) -> None:
        now = utcnow()
        new_fabric_resource = (
            fabric_request.to_builder()
            .with_created(now)
            .with_updated(now)
            .build()
        )

        fabric = await services.fabrics.create(new_fabric_resource)
        response.headers["ETag"] = fabric.etag()
        return FabricResponse.from_model(
            fabric=fabric,
            self_base_hyperlink=f"{V3_API_PREFIX}/fabrics",
        )

    @handler(
        path="/fabrics/{fabric_id}",
        methods=["PUT"],
        tags=TAGS,
        responses={
            200: {
                "model": FabricResponse,
                "headers": {
                    "ETag": {"description": "The ETag for the resource"}
                },
            },
            404: {"model": NotFoundBodyResponse},
            422: {"model": ValidationErrorBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def update_fabric(
        self,
        fabric_id: int,
        fabric_request: FabricRequest,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        now = utcnow()
        fabric = await services.fabrics.update_by_id(
            id=fabric_id,
            resource=fabric_request.to_builder().with_updated(now).build(),
        )

        response.headers["ETag"] = fabric.etag()
        return FabricResponse.from_model(
            fabric=fabric, self_base_hyperlink=f"{V3_API_PREFIX}/fabrics"
        )

    @handler(
        path="/fabrics/{fabric_id}",
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
    async def delete_fabric(
        self,
        fabric_id: int,
        etag_if_match: Union[str, None] = Header(
            alias="if-match", default=None
        ),
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        await services.fabrics.delete_by_id(
            id=fabric_id,
            etag_if_match=etag_if_match,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
