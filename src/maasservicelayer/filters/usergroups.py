# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from typing import ClassVar

from maasservicelayer.filters.base import CustomFilter, Filter, FilterFactory
from maasservicelayer.models.usergroups import UserGroup


@dataclass(frozen=True)
class UserGroupNameLike(CustomFilter):
    model: ClassVar[type[UserGroup]] = UserGroup
    name: str


class UserGroupsFilters(FilterFactory):
    model = UserGroup

    @classmethod
    def with_ids(cls, ids: list[int]) -> Filter:
        return cls._is_in("id", ids)

    @classmethod
    def with_name(cls, name: str) -> Filter:
        return cls._equals("name", name)

    @classmethod
    def with_name_like(cls, name: str) -> Filter:
        return UserGroupNameLike(name)
