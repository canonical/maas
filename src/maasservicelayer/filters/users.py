# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from typing import ClassVar

from maasservicelayer.filters.base import CustomFilter, Filter, FilterFactory
from maasservicelayer.models.users import User


@dataclass(frozen=True)
class UsernameOrEmailLike(CustomFilter):
    model: ClassVar[type[User]] = User
    value: str


@dataclass(frozen=True)
class UserProviderId(CustomFilter):
    model: ClassVar[type[User]] = User
    provider_id: int


class UserFilters(FilterFactory):
    model = User

    @classmethod
    def with_id(cls, id: int) -> Filter:
        return cls._equals("id", id)

    @classmethod
    def with_ids(cls, ids: list[int]) -> Filter:
        return cls._is_in("id", ids)

    @classmethod
    def with_username(cls, username: str) -> Filter:
        return cls._equals("username", username)

    @classmethod
    def with_username_or_email_like(
        cls, username_or_email_like: str
    ) -> Filter:
        return UsernameOrEmailLike(username_or_email_like)

    @classmethod
    def with_provider_id(cls, provider_id: int) -> Filter:
        return UserProviderId(provider_id)
