# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    TokenPaginatedResponse,
)
from maasservicelayer.models.resource_pools import ResourcePool


class ResourcePoolResponse(HalResponse[BaseHal]):
    kind = "ResourcePool"
    id: int
    name: str
    description: str
    created: datetime
    updated: datetime

    @classmethod
    def from_model(cls, resource_pool: ResourcePool, self_base_hyperlink: str):
        return ResourcePoolResponse(
            id=resource_pool.id,
            name=resource_pool.name,
            description=resource_pool.description,
            created=resource_pool.created,
            updated=resource_pool.updated,
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{resource_pool.id}"
                )
            ),
        )


class ResourcePoolsListResponse(TokenPaginatedResponse[ResourcePoolResponse]):
    kind = "ResourcePoolList"
