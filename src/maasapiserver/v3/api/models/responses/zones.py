from maasapiserver.v3.api.models.responses.base import BaseHal, HalResponse


class ZoneResponse(HalResponse[BaseHal]):
    kind = "Zone"
    id: int
    name: str
    description: str
