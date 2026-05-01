# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maasservicelayer.models.users import User, UserStatistics


class UserInfoResponse(BaseModel):
    id: int
    username: str
    is_superuser: bool


class UserResponse(HalResponse[BaseHal]):
    kind: str = Field(default="User")
    id: int
    username: str
    is_superuser: bool
    first_name: str
    last_name: str | None = None
    date_joined: datetime
    email: str | None = None
    last_login: datetime | None = None

    @classmethod
    def from_model(cls, user: User, self_base_hyperlink: str) -> Self:
        return cls(
            id=user.id,
            username=user.username,
            is_superuser=user.is_superuser,
            first_name=user.first_name,
            last_name=user.last_name,
            date_joined=user.date_joined,
            email=user.email,
            last_login=user.last_login,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{user.id}"
                )
            ),
        )


class UsersListResponse(PaginatedResponse[UserResponse]):
    kind: str = Field(default="UsersList")


class UserStatisticsResponse(HalResponse[BaseHal]):
    kind: str = Field(default="UserStatistics")
    id: int
    completed_intro: bool
    is_local: bool
    machines_count: int
    sshkeys_count: int

    @classmethod
    def from_model(
        cls, user_statistics: UserStatistics, self_base_hyperlink: str
    ) -> Self:
        return cls(
            id=user_statistics.id,
            completed_intro=user_statistics.completed_intro,
            is_local=user_statistics.is_local,
            machines_count=user_statistics.machines_count,
            sshkeys_count=user_statistics.sshkeys_count,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{user_statistics.id}"
                )
            ),
        )


class UsersStatisticsListResponse(PaginatedResponse[UserStatisticsResponse]):
    kind: str = Field(default="UserStatisticsList")
