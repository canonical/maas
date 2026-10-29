# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import cast, String

from maasservicelayer.db.filters import Clause
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.tables import UISubnetView
from maasservicelayer.filters.base import CustomFilter
from maasservicelayer.filters.ui_subnets import (
    UISubnetsCIDRsFilter,
    UISubnetsContainsFilter,
)


class UISubnetDomainDataMapper(DefaultDomainDataMapper):
    def custom_filter_clause(self, filter: CustomFilter) -> Clause:
        match filter:
            case UISubnetsCIDRsFilter(cidrs):
                return Clause(
                    condition=cast(UISubnetView.c.cidr, String).in_(cidrs)
                )
            case UISubnetsContainsFilter(field, value):
                column = self._column_mapping(field).column
                if field == "cidr":
                    column = cast(column, String)
                return Clause(condition=column.contains(value))
            case _:
                return super().custom_filter_clause(filter)
