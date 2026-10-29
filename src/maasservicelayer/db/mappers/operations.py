# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.db.filters import Clause
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.tables import OperationTable
from maasservicelayer.filters.base import CustomFilter
from maasservicelayer.filters.operations import OperationsCreatedBefore


class OperationsDomainDataMapper(DefaultDomainDataMapper):
    def custom_filter_clause(self, filter: CustomFilter) -> Clause:
        match filter:
            case OperationsCreatedBefore(moment):
                return Clause(condition=OperationTable.c.created <= moment)
        return super().custom_filter_clause(filter)
