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
from maasapiserver.v3.api.public.models.requests.query import (
    TokenPaginationParams,
)
from maasapiserver.v3.api.public.models.requests.zones import (
    ZoneRequest,
    ZonesFiltersParams,
)
from maasapiserver.v3.api.public.models.responses.zones import (
    ZoneResponse,
    ZonesListResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.zones import ZoneResourceBuilder
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.utils.date import utcnow


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
        token_pagination_params: TokenPaginationParams = Depends(),
        filters: ZonesFiltersParams = Depends(),
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        zones = await services.zones.list(
            token=token_pagination_params.token,
            size=token_pagination_params.size,
            query=QuerySpec(where=filters.to_clause()),
        )
        next_link = None
        if zones.next_token:
            next_link = f"{V3_API_PREFIX}/zones?{TokenPaginationParams.to_href_format(zones.next_token, token_pagination_params.size)}"
            if query_filters := filters.to_href_format():
                next_link += f"&{query_filters}"

        return ZonesListResponse(
            items=[
                ZoneResponse.from_model(
                    zone=zone, self_base_hyperlink=f"{V3_API_PREFIX}/zones"
                )
                for zone in zones.items
            ],
            next=next_link,
        )

    @handler(
        path="/zones",
        methods=["POST"],
        tags=TAGS,
        responses={
            201: {
                "model": ZoneResponse,
                "headers": {
                    "ETag": {"description": "The ETag for the resource"}
                },
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
        now = utcnow()
        resource = (
            ZoneResourceBuilder()
            .with_name(zone_request.name)
            .with_description(zone_request.description)
            .with_created(now)
            .with_updated(now)
            .build()
        )
        zone = await services.zones.create(resource)
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
        await services.zones.delete(zone_id, etag_if_match)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
