# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import case, join, select

from maasservicelayer.db.filters import Clause, OrderByClause
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.tables import (
    BootResourceFileTable,
    BootResourceSetTable,
    BootResourceTable,
    BootSourceSelectionTable,
)
from maasservicelayer.filters.base import CustomFilter
from maasservicelayer.filters.bootresources import (
    BootResourceArchitecturePrefix,
    BootResourceNamePriority,
    BootResourceSelectionBootSource,
    BootResourceWithFiletype,
)
from maasservicelayer.filters.query import CustomOrderBy


class BootResourceDomainDataMapper(DefaultDomainDataMapper):
    def custom_filter_clause(self, filter: CustomFilter) -> Clause:
        match filter:
            case BootResourceArchitecturePrefix(partial_arch):
                return Clause(
                    condition=BootResourceTable.c.architecture.startswith(
                        partial_arch
                    )
                )
            case BootResourceSelectionBootSource(boot_source_id):
                return Clause(
                    condition=BootSourceSelectionTable.c.boot_source_id
                    == boot_source_id,
                    joins=[
                        join(
                            BootSourceSelectionTable,
                            BootResourceTable,
                            BootSourceSelectionTable.c.id
                            == BootResourceTable.c.selection_id,
                        )
                    ],
                )
            case BootResourceWithFiletype(filetype):
                subquery = (
                    select(BootResourceSetTable.c.resource_id)
                    .distinct()
                    .select_from(BootResourceSetTable)
                    .join(
                        BootResourceFileTable,
                        BootResourceFileTable.c.resource_set_id
                        == BootResourceSetTable.c.id,
                    )
                    .where(BootResourceFileTable.c.filetype == filetype)
                    .scalar_subquery()
                )
                return Clause(condition=BootResourceTable.c.id.in_(subquery))
        return super().custom_filter_clause(filter)

    def custom_order_by_clause(self, order: CustomOrderBy) -> OrderByClause:
        match order:
            case BootResourceNamePriority(lts_releases):
                return OrderByClause(
                    column=case(
                        {
                            release: priority
                            for priority, release in enumerate(lts_releases)
                        },
                        value=BootResourceTable.c.name,
                    )
                )
        return super().custom_order_by_clause(order)
