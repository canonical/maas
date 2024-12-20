# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Self

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

    @classmethod
    def from_model(
        cls, resource_pool: ResourcePool, self_base_hyperlink: str
    ) -> Self:
        return ResourcePoolResponse(
            id=resource_pool.id,
            name=resource_pool.name,
            description=resource_pool.description,
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{resource_pool.id}"
                )
            ),
        )


class ResourcePoolsListResponse(TokenPaginatedResponse[ResourcePoolResponse]):
    kind = "ResourcePoolList"
