# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maascommon.enums.script import ScriptType
from maasservicelayer.builders.script import ScriptBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import Clause, QuerySpec
from maasservicelayer.db.repositories.scripts import (
    ScriptsClauseFactory,
    ScriptsRepository,
)
from maasservicelayer.models.script import Script
from maasservicelayer.services.base import BaseService

NO_USER_SCRIPTS = "none"
DEFAULT_TESTING_TAG = "commissioning"
# Commissioning scripts with this tag only run when explicitly selected.
NOAUTO_TAG = "noauto"


def _selected_by(names_or_tags: list[str]) -> Clause:
    return ScriptsClauseFactory.or_clauses(
        [
            ScriptsClauseFactory.with_names(names_or_tags),
            ScriptsClauseFactory.with_tags_overlap(names_or_tags),
        ]
    )


def get_unmatched_selection(
    selection: list[str] | None, scripts: list[Script]
) -> list[str]:
    if not selection:
        return []
    names_and_tags = set()
    for script in scripts:
        names_and_tags.add(script.name)
        names_and_tags.update(script.tags or [])
    return [item for item in selection if item not in names_and_tags]


class ScriptsService(BaseService[Script, ScriptsRepository, ScriptBuilder]):
    def __init__(
        self,
        context: Context,
        repository: ScriptsRepository,
    ):
        super().__init__(context, repository)

    async def get_commissioning_scripts(
        self, selection: list[str] | None = None
    ) -> list[Script]:
        if not selection:
            selected = ScriptsClauseFactory.and_clauses(
                [
                    ScriptsClauseFactory.with_empty_for_hardware(),
                    ScriptsClauseFactory.without_tags_contains([NOAUTO_TAG]),
                ]
            )
        else:
            clauses = [
                ScriptsClauseFactory.with_default(True),
                ScriptsClauseFactory.with_tags_overlap_builtin_names(),
            ]
            if NO_USER_SCRIPTS not in selection:
                clauses.append(_selected_by(selection))
            selected = ScriptsClauseFactory.or_clauses(clauses)
        return await self._get_scripts(ScriptType.COMMISSIONING, selected)

    async def get_testing_scripts(
        self, selection: list[str] | None = None
    ) -> list[Script]:
        if selection and NO_USER_SCRIPTS in selection:
            return []
        return await self._get_scripts(
            ScriptType.TESTING,
            _selected_by(selection or [DEFAULT_TESTING_TAG]),
        )

    async def _get_scripts(
        self, script_type: ScriptType, selected: Clause
    ) -> list[Script]:
        return await self.get_many(
            QuerySpec(
                where=ScriptsClauseFactory.and_clauses(
                    [
                        ScriptsClauseFactory.with_script_type(script_type),
                        selected,
                    ]
                )
            )
        )
