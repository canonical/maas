# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
from enum import StrEnum
from typing import Self

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maasservicelayer.models.resource_pools import (
    ResourcePool,
    ResourcePoolWithSummary,
)


class ResourcePoolResponse(HalResponse[BaseHal]):
    kind = "ResourcePool"
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
    kind = "ResourcePoolList"


class ResourcePoolPermission(StrEnum):
    EDIT = "edit"
    DELETE = "delete"


class ResourcePoolWithSummaryResponse(ResourcePoolResponse):
    kind = "ResourcePoolWithSummary"
    machine_total_count: int
    machine_ready_count: int
    is_default: bool
    permissions: set[ResourcePoolPermission]

    @classmethod
    def from_model_with_summary(
        cls,
        resource_pool_with_summary: ResourcePoolWithSummary,
        permissions: set[ResourcePoolPermission],
        self_base_hyperlink: str,
    ) -> Self:
        return cls(
            id=resource_pool_with_summary.id,
            name=resource_pool_with_summary.name,
            description=resource_pool_with_summary.description,
            machine_total_count=resource_pool_with_summary.machine_total_count,
            machine_ready_count=resource_pool_with_summary.machine_ready_count,
            is_default=resource_pool_with_summary.is_default(),
            permissions=permissions,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{resource_pool_with_summary.id}"
                )
            ),
        )


class ResourcePoolsWithSummaryListResponse(
    PaginatedResponse[ResourcePoolWithSummaryResponse]
):
    kind = "ResourcePoolsWithSummaryList"
