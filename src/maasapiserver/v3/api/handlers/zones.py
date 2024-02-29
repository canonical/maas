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
from maasapiserver.v3.api.models.requests.query import PaginationParams
from maasapiserver.v3.api.models.requests.zones import ZoneRequest
from maasapiserver.v3.api.models.responses.zones import (
    ZoneResponse,
    ZonesListResponse,
)
from maasapiserver.v3.constants import EXTERNAL_V3_API_PREFIX
from maasapiserver.v3.services import ServiceCollectionV3


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
    )
    async def list_zones(
        self,
        pagination_params: PaginationParams = Depends(),
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        zones = await services.zones.list(pagination_params)
        return ZonesListResponse(
            items=[
                zone.to_response(f"{EXTERNAL_V3_API_PREFIX}/zones")
                for zone in zones.items
            ],
            total=zones.total,
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
    )
    async def create_zone(
        self,
        response: Response,
        zone_request: ZoneRequest,
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        zone = await services.zones.create(zone_request)
        response.headers["ETag"] = zone.etag()
        return zone.to_response(
            self_base_hyperlink=f"{EXTERNAL_V3_API_PREFIX}/zones"
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
        return zone.to_response(
            self_base_hyperlink=f"{EXTERNAL_V3_API_PREFIX}/zones"
        )

    # TODO: ensure authorization
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
