# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import not_, or_

from maasservicelayer.db.filters import Clause
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.tables import ScriptTable
from maasservicelayer.filters.base import CustomFilter
from maasservicelayer.filters.scripts import (
    ScriptsNonemptyForHardware,
    ScriptsTagsContains,
    ScriptsTagsOverlap,
    ScriptsWithoutTagsContains,
)


class ScriptsDomainDataMapper(DefaultDomainDataMapper):
    def custom_filter_clause(self, filter: CustomFilter) -> Clause:
        match filter:
            case ScriptsTagsContains(tags):
                return Clause(
                    condition=ScriptTable.c.tags.contains(list(tags))
                )
            case ScriptsTagsOverlap(tags):
                return Clause(condition=ScriptTable.c.tags.overlap(list(tags)))
            case ScriptsWithoutTagsContains(tags):
                return Clause(
                    condition=or_(
                        ScriptTable.c.tags.is_(None),
                        not_(ScriptTable.c.tags.contains(list(tags))),
                    )
                )
            case ScriptsNonemptyForHardware():
                return Clause(condition=not_(ScriptTable.c.for_hardware == []))
        return super().custom_filter_clause(filter)
