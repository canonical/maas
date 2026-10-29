# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from typing import ClassVar

from maascommon.enums.script import ScriptType
from maasservicelayer.filters.base import (
    CustomFilter,
    FieldFilter,
    FilterFactory,
)
from maasservicelayer.models.script import Script


@dataclass(frozen=True)
class ScriptsTagsContains(CustomFilter):
    model: ClassVar[type[Script]] = Script
    tags: tuple[str, ...]


@dataclass(frozen=True)
class ScriptsTagsOverlap(CustomFilter):
    model: ClassVar[type[Script]] = Script
    tags: tuple[str, ...]


@dataclass(frozen=True)
class ScriptsWithoutTagsContains(CustomFilter):
    model: ClassVar[type[Script]] = Script
    tags: tuple[str, ...]


@dataclass(frozen=True)
class ScriptsNonemptyForHardware(CustomFilter):
    model: ClassVar[type[Script]] = Script


class ScriptsFilters(FilterFactory):
    model = Script

    @classmethod
    def with_id(cls, id: int) -> FieldFilter:
        return cls._equals("id", id)

    @classmethod
    def with_ids(cls, ids: list[int]) -> FieldFilter:
        return cls._is_in("id", ids)

    @classmethod
    def with_name(cls, name: str) -> FieldFilter:
        return cls._equals("name", name)

    @classmethod
    def with_names(cls, names: list[str]) -> FieldFilter:
        return cls._is_in("name", names)

    @classmethod
    def with_script_type(cls, script_type: ScriptType) -> FieldFilter:
        return cls._equals("script_type", script_type)

    @classmethod
    def with_default(cls, default: bool) -> FieldFilter:
        return cls._equals("default", default)

    @classmethod
    def with_tags_contains(cls, tags: list[str]) -> ScriptsTagsContains:
        return ScriptsTagsContains(tuple(tags))

    @classmethod
    def with_tags_overlap(cls, tags: list[str]) -> ScriptsTagsOverlap:
        return ScriptsTagsOverlap(tuple(tags))

    @classmethod
    def without_tags_contains(
        cls, tags: list[str]
    ) -> ScriptsWithoutTagsContains:
        """NULL-safe exclude(tags__contains=...)."""
        return ScriptsWithoutTagsContains(tuple(tags))

    @classmethod
    def with_empty_for_hardware(cls) -> FieldFilter:
        return cls._equals("for_hardware", [])

    @classmethod
    def with_nonempty_for_hardware(cls) -> ScriptsNonemptyForHardware:
        return ScriptsNonemptyForHardware()
