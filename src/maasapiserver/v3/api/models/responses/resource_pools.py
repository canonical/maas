from datetime import datetime

from maasapiserver.v3.api.models.responses.base import (
    BaseHal,
    HalResponse,
    TokenPaginatedResponse,
)


class ResourcePoolResponse(HalResponse[BaseHal]):
    kind = "ResourcePool"
    id: int
    name: str
    description: str
    created: datetime
    updated: datetime


class ResourcePoolsListResponse(TokenPaginatedResponse[ResourcePoolResponse]):
    kind = "ResourcePoolList"
