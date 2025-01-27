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
    ValidationErrorBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.query import PaginationParams
from maasapiserver.v3.api.public.models.requests.zones import (
    ZoneRequest,
    ZonesFiltersParams,
)
from maasapiserver.v3.api.public.models.responses.base import (
    OPENAPI_ETAG_HEADER,
)
from maasapiserver.v3.api.public.models.responses.zones import (
    ZoneResponse,
    ZonesListResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.services import ServiceCollectionV3


class ZonesHandler(Handler):
    """Zones API handler."""

    TAGS = ["Zones"]

    @handler(
        path="/zones",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": ZonesListResponse,
            },
            422: {"model": ValidationErrorBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_zones(
        self,
        pagination_params: PaginationParams = Depends(),
        filters: ZonesFiltersParams = Depends(),
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        zones = await services.zones.list(
            page=pagination_params.page,
            size=pagination_params.size,
            query=QuerySpec(where=filters.to_clause()),
        )
        next_link = None
        if zones.has_next(pagination_params.page, pagination_params.size):
            next_link = f"{V3_API_PREFIX}/zones?{pagination_params.to_next_href_format()}"
            if query_filters := filters.to_href_format():
                next_link += f"&{query_filters}"

        return ZonesListResponse(
            items=[
                ZoneResponse.from_model(
                    zone=zone, self_base_hyperlink=f"{V3_API_PREFIX}/zones"
                )
                for zone in zones.items
            ],
            total=zones.total,
            next=next_link,
        )

    @handler(
        path="/zones",
        methods=["POST"],
        tags=TAGS,
        responses={
            201: {
                "model": ZoneResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            409: {"model": ConflictBodyResponse},
            422: {"model": ValidationErrorBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=201,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def create_zone(
        self,
        response: Response,
        zone_request: ZoneRequest,
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        zone = await services.zones.create(zone_request.to_builder())
        response.headers["ETag"] = zone.etag()
        return ZoneResponse.from_model(
            zone=zone, self_base_hyperlink=f"{V3_API_PREFIX}/zones"
        )

    @handler(
        path="/zones/{zone_id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": ZoneResponse,
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
    async def get_zone(
        self,
        zone_id: int,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        zone = await services.zones.get_by_id(zone_id)
        if not zone:
            return NotFoundResponse()

        response.headers["ETag"] = zone.etag()
        return ZoneResponse.from_model(
            zone=zone, self_base_hyperlink=f"{V3_API_PREFIX}/zones"
        )

    @handler(
        path="/zones/{zone_id}",
        methods=["PUT"],
        tags=TAGS,
        responses={
            200: {
                "model": ZoneResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
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
    async def update_zone(
        self,
        zone_id: int,
        zone_request: ZoneRequest,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        zone = await services.zones.update_by_id(
            zone_id, zone_request.to_builder()
        )
        if not zone:
            return NotFoundResponse()

        response.headers["ETag"] = zone.etag()
        return ZoneResponse.from_model(
            zone=zone, self_base_hyperlink=f"{V3_API_PREFIX}/zones"
        )

    @handler(
        path="/zones/{zone_id}",
        methods=["DELETE"],
        description="Deletes a zone. All the resources belonging to this zone will be moved to the default zone.",
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
    async def delete_zone(
        self,
        zone_id: int,
        etag_if_match: Union[str, None] = Header(
            alias="if-match", default=None
        ),
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        await services.zones.delete_by_id(zone_id, etag_if_match)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
