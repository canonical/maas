# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from typing import ClassVar

from maascommon.enums.scriptresult import ScriptStatus
from maasservicelayer.filters.base import (
    CustomFilter,
    FieldFilter,
    FilterFactory,
)
from maasservicelayer.models.scriptresult import ScriptResult


@dataclass(frozen=True)
class ScriptResultsForNode(CustomFilter):
    model: ClassVar[type[ScriptResult]] = ScriptResult
    node_id: int


class ScriptResultFilters(FilterFactory):
    model = ScriptResult

    @classmethod
    def with_id(cls, id: int) -> FieldFilter:
        return cls._equals("id", id)

    @classmethod
    def with_script_id(cls, script_id: int) -> FieldFilter:
        return cls._equals("script_id", script_id)

    @classmethod
    def with_script_id_in(cls, script_ids: list[int]) -> FieldFilter:
        return cls._is_in("script_id", script_ids)

    @classmethod
    def with_script_set_id(cls, script_set_id: int) -> FieldFilter:
        return cls._equals("script_set_id", script_set_id)

    @classmethod
    def with_script_set_id_in(cls, set_ids: list[int]) -> FieldFilter:
        return cls._is_in("script_set_id", set_ids)

    @classmethod
    def with_status(cls, status: ScriptStatus) -> FieldFilter:
        return cls._equals("status", status)

    @classmethod
    def with_status_in(cls, statuses: list[ScriptStatus]) -> FieldFilter:
        return cls._is_in("status", statuses)

    @classmethod
    def with_node_id(cls, node_id: int) -> ScriptResultsForNode:
        return ScriptResultsForNode(node_id)
