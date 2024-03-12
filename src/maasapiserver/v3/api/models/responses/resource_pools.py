from datetime import datetime

from maasapiserver.v3.api.models.responses.base import (
    BaseHal,
    HalResponse,
    PaginatedResponse,
)


class ResourcePoolResponse(HalResponse[BaseHal]):
    kind = "ResourcePool"
    id: int
    name: str
    description: str
    created: datetime
    updated: datetime


class ResourcePoolsListResponse(PaginatedResponse[ResourcePoolResponse]):
    kind = "ResourcePoolList"
