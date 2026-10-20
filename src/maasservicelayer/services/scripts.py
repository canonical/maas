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

# Selecting this restricts commissioning to the built-in scripts.
NO_USER_SCRIPTS = "none"
# Tag of the testing scripts run after commissioning when none are selected.
DEFAULT_TESTING_TAG = "commissioning"
# Commissioning scripts with this tag only run when explicitly selected.
NOAUTO_TAG = "noauto"


def _selected_by(names_tags_or_ids: list[str]) -> Clause:
    ids = [int(item) for item in names_tags_or_ids if item.isdecimal()]
    clauses = [
        ScriptsClauseFactory.with_names(names_tags_or_ids),
        ScriptsClauseFactory.with_tags_overlap(names_tags_or_ids),
    ]
    if ids:
        clauses.append(ScriptsClauseFactory.with_ids(ids))
    return ScriptsClauseFactory.or_clauses(clauses)


def get_unmatched_selection(
    selection: list[str] | None, scripts: list[Script]
) -> list[str]:
    """Return the entries of `selection` that match none of `scripts`.

    `none` is not a script selection, so it is never returned.
    """
    if not selection:
        return []
    names_and_tags = set()
    ids = set()
    for script in scripts:
        names_and_tags.add(script.name)
        names_and_tags.update(script.tags or [])
        ids.add(script.id)
    return [
        item
        for item in selection
        if item != NO_USER_SCRIPTS
        and item not in names_and_tags
        and not (item.isdecimal() and int(item) in ids)
    ]


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
        """Return the commissioning scripts to run on a machine.

        Built-in scripts are always included. Without a selection, all
        scripts not tagged `noauto` and not restricted to specific hardware
        are included. Selecting `none` includes only the built-in scripts.
        As in the legacy ScriptSet, the names of all built-in scripts are
        added to the selection, so scripts tagged with them are included
        too.

        Scripts restricted to specific hardware are returned as selected;
        whether they run depends on the machine's hardware.

        :param selection: Names, tags or ids of scripts to run.
        """
        if not selection:
            selected = ScriptsClauseFactory.and_clauses(
                [
                    ScriptsClauseFactory.with_empty_for_hardware(),
                    ScriptsClauseFactory.without_tags_contains([NOAUTO_TAG]),
                ]
            )
        else:
            builtin_scripts = await self.get_many(
                QuerySpec(where=ScriptsClauseFactory.with_default(True))
            )
            names = [script.name for script in builtin_scripts]
            if NO_USER_SCRIPTS not in selection:
                names += selection
            selected = _selected_by(names)
        return await self._get_scripts(ScriptType.COMMISSIONING, selected)

    async def get_testing_scripts(
        self, selection: list[str] | None = None
    ) -> list[Script]:
        """Return the testing scripts to run on a machine.

        Without a selection, the scripts tagged `commissioning` are included.
        Selecting `none` includes no scripts.

        Scripts restricted to specific hardware are returned as selected;
        whether they run depends on the machine's hardware.

        :param selection: Names, tags or ids of scripts to run.
        """
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
