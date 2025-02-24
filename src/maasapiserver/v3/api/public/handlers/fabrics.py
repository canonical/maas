# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
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
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.fabrics import FabricRequest
from maasapiserver.v3.api.public.models.requests.query import PaginationParams
from maasapiserver.v3.api.public.models.responses.base import (
    OPENAPI_ETAG_HEADER,
)
from maasapiserver.v3.api.public.models.responses.fabrics import (
    FabricResponse,
    FabricsListResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.services import ServiceCollectionV3


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
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_fabrics(
        self,
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> FabricsListResponse:
        fabrics = await services.fabrics.list(
            page=pagination_params.page,
            size=pagination_params.size,
        )
        return FabricsListResponse(
            items=[
                FabricResponse.from_model(
                    fabric=fabric,
                    self_base_hyperlink=f"{V3_API_PREFIX}/fabrics",
                )
                for fabric in fabrics.items
            ],
            total=fabrics.total,
            next=(
                f"{V3_API_PREFIX}/fabrics?"
                f"{pagination_params.to_next_href_format()}"
                if fabrics.has_next(
                    pagination_params.page, pagination_params.size
                )
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
    async def get_fabric(
        self,
        fabric_id: int,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
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
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            409: {"model": ConflictBodyResponse},
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
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> None:
        fabric = await services.fabrics.create(fabric_request.to_builder())
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
    async def update_fabric(
        self,
        fabric_id: int,
        fabric_request: FabricRequest,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        fabric = await services.fabrics.update_by_id(
            id=fabric_id,
            builder=fabric_request.to_builder(),
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
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        await services.fabrics.delete_by_id(
            id=fabric_id,
            etag_if_match=etag_if_match,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
