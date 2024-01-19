from maasapiserver.v3.api.models.responses.base import (
    BaseHal,
    HalResponse,
    PaginatedResponse,
)


class ZoneResponse(HalResponse[BaseHal]):
    kind = "Zone"
    id: int
    name: str
    description: str


class ZonesListResponse(PaginatedResponse[ZoneResponse]):
    kind = "ZonesList"
