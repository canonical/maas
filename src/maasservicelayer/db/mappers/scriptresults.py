# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import join

from maasservicelayer.db.filters import Clause
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.tables import ScriptResultTable, ScriptSetTable
from maasservicelayer.filters.base import CustomFilter
from maasservicelayer.filters.scriptresults import ScriptResultsForNode


class ScriptResultsDomainDataMapper(DefaultDomainDataMapper):
    def custom_filter_clause(self, filter: CustomFilter) -> Clause:
        match filter:
            case ScriptResultsForNode(node_id):
                return Clause(
                    condition=ScriptSetTable.c.node_id == node_id,
                    joins=[
                        join(
                            ScriptSetTable,
                            ScriptResultTable,
                            ScriptResultTable.c.script_set_id
                            == ScriptSetTable.c.id,
                        )
                    ],
                )
        return super().custom_filter_clause(filter)
