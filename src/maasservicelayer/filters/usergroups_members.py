# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.filters.base import Filter, FilterFactory
from maasservicelayer.models.usergroup_members import UserGroupMember


class UserGroupMembersFilters(FilterFactory):
    model = UserGroupMember

    @classmethod
    def with_group_id(cls, group_id: int) -> Filter:
        return cls._equals("group_id", group_id)

    @classmethod
    def with_username(cls, username: str) -> Filter:
        return cls._equals("username", username)

    @classmethod
    def with_id(cls, user_id: int) -> Filter:
        return cls._equals("id", user_id)

    @classmethod
    def with_ids(cls, user_ids: list[int]) -> Filter:
        return cls._is_in("id", user_ids)
