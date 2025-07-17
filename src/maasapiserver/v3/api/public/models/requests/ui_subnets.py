# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from fastapi import Query
from pydantic import BaseModel, Field

from maasapiserver.v3.api.public.models.requests.base import OrderByQueryFilter
from maasservicelayer.db.filters import Clause
from maasservicelayer.db.repositories.ui_subnets import (
    UISubnetsClauseFactory,
    UISubnetsOrderByClauses,
)


class UISubnetOrderByQueryFilter(OrderByQueryFilter):
    _order_by_columns = {
        "cidr": UISubnetsOrderByClauses.by_cidr(),
        "fabric": UISubnetsOrderByClauses.by_fabric_name(),
        "space": UISubnetsOrderByClauses.by_space_name(),
    }


class UISubnetFiltersParams(BaseModel):
    cidrs: Optional[list[str]] = Field(
        Query(default=None, title="Filter by subnet cidr", alias="cidr")
    )

    vlan_ids: Optional[list[int]] = Field(
        Query(default=None, title="Filter by vlan id", alias="vlan_id")
    )

    fabric_names: Optional[list[str]] = Field(
        Query(default=None, title="Filter by fabric name", alias="fabric")
    )

    space_names: Optional[list[str]] = Field(
        Query(default=None, title="Filter by space name", alias="space")
    )

    def to_clause(self) -> Optional[Clause]:
        clauses = []
        if self.cidrs:
            clauses.append(UISubnetsClauseFactory.with_cidrs(self.cidrs))
        if self.vlan_ids:
            clauses.append(UISubnetsClauseFactory.with_vlan_ids(self.vlan_ids))

        if self.fabric_names:
            clauses.append(
                UISubnetsClauseFactory.with_fabric_names(self.fabric_names)
            )

        if self.space_names:
            clauses.append(
                UISubnetsClauseFactory.with_space_names(self.space_names)
            )

        if not clauses:
            return None
        if len(clauses) > 1:
            return UISubnetsClauseFactory.and_clauses(clauses)
        else:
            return clauses[0]

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

        if tokens:
            return "&".join(tokens)
        return ""
