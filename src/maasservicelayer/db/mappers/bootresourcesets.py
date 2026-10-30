# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.db.filters import Clause
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.tables import BootResourceSetTable
from maasservicelayer.filters.base import CustomFilter
from maasservicelayer.filters.bootresourcesets import (
    BootResourceSetVersionPrefix,
)


class BootResourceSetDomainDataMapper(DefaultDomainDataMapper):
    def custom_filter_clause(self, filter: CustomFilter) -> Clause:
        match filter:
            case BootResourceSetVersionPrefix(version):
                return Clause(
                    condition=BootResourceSetTable.c.version.like(
                        f"{version}%"
                    )
                )
        return super().custom_filter_clause(filter)
