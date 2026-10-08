# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq
from typing import Type

from sqlalchemy import not_, or_, Table

from maascommon.enums.script import ScriptType
from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import ScriptTable
from maasservicelayer.models.script import Script


class ScriptsClauseFactory(ClauseFactory):
    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(ScriptTable.c.id, id))

    @classmethod
    def with_ids(cls, ids: list[int]) -> Clause:
        return Clause(condition=ScriptTable.c.id.in_(ids))

    @classmethod
    def with_name(cls, name: str) -> Clause:
        return Clause(condition=eq(ScriptTable.c.name, name))

    @classmethod
    def with_names(cls, names: list[str]) -> Clause:
        return Clause(condition=ScriptTable.c.name.in_(names))

    @classmethod
    def with_script_type(cls, script_type: ScriptType) -> Clause:
        return Clause(condition=eq(ScriptTable.c.script_type, script_type))

    @classmethod
    def with_default(cls, default: bool) -> Clause:
        return Clause(condition=eq(ScriptTable.c.default, default))

    @classmethod
    def with_tags_contains(cls, tags: list[str]) -> Clause:
        return Clause(condition=ScriptTable.c.tags.contains(tags))

    @classmethod
    def with_tags_overlap(cls, tags: list[str]) -> Clause:
        return Clause(condition=ScriptTable.c.tags.overlap(tags))

    @classmethod
    def without_tags(cls, tags: list[str]) -> Clause:
        """NULL-safe exclude(tags__contains=...)."""
        return Clause(
            condition=or_(
                ScriptTable.c.tags.is_(None),
                not_(ScriptTable.c.tags.contains(tags)),
            )
        )

    @classmethod
    def with_empty_for_hardware(cls) -> Clause:
        return Clause(condition=eq(ScriptTable.c.for_hardware, []))

    @classmethod
    def with_nonempty_for_hardware(cls) -> Clause:
        return cls.not_clause(cls.with_empty_for_hardware())


class ScriptsRepository(BaseRepository[Script]):
    def get_repository_table(self) -> Table:
        return ScriptTable

    def get_model_factory(self) -> Type[Script]:
        return Script
