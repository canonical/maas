from fastapi import Depends, Response

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    NotFoundBodyResponse,
    NotFoundResponse,
    ValidationErrorBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.models.responses.base import BaseHal, BaseHref
from maasapiserver.v3.api.models.responses.zones import ZoneResponse
from maasapiserver.v3.constants import EXTERNAL_V3_API_PREFIX
from maasapiserver.v3.services import ServiceCollectionV3


class ZonesHandler(Handler):
    """Zones API handler."""

    TAGS = ["Zones"]

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
        return ZoneResponse(
            id=zone.id,
            name=zone.name,
            description=zone.description,
            hal_links=BaseHal(
                self=BaseHref(href=f"{EXTERNAL_V3_API_PREFIX}/zones/{zone.id}")
            ),
        )
