# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
from enum import StrEnum
from typing import Self

from pydantic import Field

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maasservicelayer.models.resource_pools import (
    ResourcePool,
    ResourcePoolStatistics,
)


class ResourcePoolResponse(HalResponse[BaseHal]):
    kind: str = Field(default="ResourcePool")
    id: int
    name: str
    description: str

    @classmethod
    def from_model(
        cls, resource_pool: ResourcePool, self_base_hyperlink: str
    ) -> Self:
        return cls(
            id=resource_pool.id,
            name=resource_pool.name,
            description=resource_pool.description,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{resource_pool.id}"
                )
            ),
        )


class ResourcePoolsListResponse(PaginatedResponse[ResourcePoolResponse]):
    kind: str = Field(default="ResourcePoolList")


class ResourcePoolPermission(StrEnum):
    EDIT = "edit"
    DELETE = "delete"


class ResourcePoolStatisticsResponse(ResourcePoolResponse):
    kind: str = Field(default="ResourcePoolStatistics")
    machine_total_count: int
    machine_ready_count: int
    is_default: bool
    permissions: set[ResourcePoolPermission]

    @classmethod
    def from_model_with_statistics(
        cls,
        resource_pool_statistics: ResourcePoolStatistics,
        permissions: set[ResourcePoolPermission],
        self_base_hyperlink: str,
    ) -> Self:
        return cls(
            id=resource_pool_statistics.id,
            name=resource_pool_statistics.name,
            description=resource_pool_statistics.description,
            machine_total_count=resource_pool_statistics.machine_total_count,
            machine_ready_count=resource_pool_statistics.machine_ready_count,
            is_default=resource_pool_statistics.is_default(),
            permissions=permissions,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{resource_pool_statistics.id}"
                )
            ),
        )


class ResourcePoolStatisticsListResponse(
    PaginatedResponse[ResourcePoolStatisticsResponse]
):
    kind: str = Field(default="ResourcePoolStatisticsList")
