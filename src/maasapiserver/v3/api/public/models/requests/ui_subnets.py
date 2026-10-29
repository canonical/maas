# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Query
from pydantic import BaseModel, Field

from maasapiserver.v3.api.public.models.requests.base import (
    FreeTextSearchQueryParam,
    OrderByQueryFilter,
)
from maasservicelayer.filters.base import Filter
from maasservicelayer.filters.ui_subnets import (
    UISubnetsFilters,
    UISubnetsOrdering,
)


class UISubnetOrderByQueryFilter(OrderByQueryFilter):
    order_by_fields = {
        "cidr": UISubnetsOrdering.by_cidr(),
        "fabric": UISubnetsOrdering.by_fabric_name(),
        "space": UISubnetsOrdering.by_space_name(),
    }


class UISubnetFiltersParams(BaseModel):
    cidrs: list[str] | None = Field(
        Query(default=None, title="Filter by subnet cidr", alias="cidr")
    )

    vlan_ids: list[int] | None = Field(
        Query(default=None, title="Filter by vlan id", alias="vlan_id")
    )

    fabric_names: list[str] | None = Field(
        Query(default=None, title="Filter by fabric name", alias="fabric")
    )

    space_names: list[str] | None = Field(
        Query(default=None, title="Filter by space name", alias="space")
    )

    subnet_ids: list[int] | None = Field(
        Query(default=None, title="Filter by subnet id", alias="subnet_id")
    )

    def to_filter(self) -> Filter | None:
        filters = []
        if self.cidrs:
            filters.append(UISubnetsFilters.with_cidrs(self.cidrs))
        if self.vlan_ids:
            filters.append(UISubnetsFilters.with_vlan_ids(self.vlan_ids))

        if self.fabric_names:
            filters.append(
                UISubnetsFilters.with_fabric_names(self.fabric_names)
            )

        if self.space_names:
            filters.append(UISubnetsFilters.with_space_names(self.space_names))

        if self.subnet_ids:
            filters.append(UISubnetsFilters.with_subnet_ids(self.subnet_ids))

        if not filters:
            return None
        if len(filters) > 1:
            return UISubnetsFilters.and_filters(filters)
        else:
            return filters[0]

    def to_href_format(self) -> str:
        tokens = []
        if self.cidrs:
            tokens.extend([f"cidr={name}" for name in self.cidrs])
        if self.vlan_ids:
            tokens.extend([f"vlan_id={id}" for id in self.vlan_ids])
        if self.fabric_names:
            tokens.extend([f"fabric={name}" for name in self.fabric_names])
        if self.space_names:
            tokens.extend([f"space={name}" for name in self.space_names])
        if self.subnet_ids:
            tokens.extend([f"subnet_id={id}" for id in self.subnet_ids])

        if tokens:
            return "&".join(tokens)
        return ""


class UISubnetsFreeTextSearchQueryParam(FreeTextSearchQueryParam):
    def to_filter(self) -> Filter | None:
        if self.q:
            return UISubnetsFilters.or_filters(
                [
                    UISubnetsFilters.with_fabric_name_like(self.q),
                    UISubnetsFilters.with_vlan_name_like(self.q),
                    UISubnetsFilters.with_space_name_like(self.q),
                    UISubnetsFilters.with_cidr_like(self.q),
                ]
            )
        return None
