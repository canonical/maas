from fastapi import Depends, Response

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    NotFoundBodyResponse,
    NotFoundResponse,
    ValidationErrorBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.models.requests.query import PaginationParams
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
