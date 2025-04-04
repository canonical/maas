# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from typing import Optional, Self

from pydantic import BaseModel

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maasservicelayer.models.users import User, UserWithSummary


class UserInfoResponse(BaseModel):
    id: int
    username: str
    is_superuser: bool


class UserResponse(HalResponse[BaseHal]):
    kind = "User"
    id: int
    username: str
    password: str
    is_superuser: bool
    first_name: str
    last_name: Optional[str]
    is_staff: bool
    is_active: bool
    date_joined: datetime
    email: Optional[str]
    last_login: Optional[datetime]

    @classmethod
    def from_model(cls, user: User, self_base_hyperlink: str) -> Self:
        return cls(
            id=user.id,
            username=user.username,
            password=user.password,
            is_superuser=user.is_superuser,
            first_name=user.first_name,
            last_name=user.last_name,
            is_staff=user.is_staff,
            is_active=user.is_active,
            date_joined=user.date_joined,
            email=user.email,
            last_login=user.last_login,
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{user.id}"
                )
            ),
        )


class UsersListResponse(PaginatedResponse[UserResponse]):
    kind = "UsersList"


class UserWithSummaryResponse(HalResponse[BaseHal]):
    kind = "UserWithSummary"
    id: int
    completed_intro: bool
    email: Optional[str] = None
    is_local: bool
    is_superuser: bool
    last_name: Optional[str] = None
    last_login: Optional[datetime] = None
    machines_count: int
    sshkeys_count: int
    username: str

    @classmethod
    def from_model(
        cls, user_with_summary: UserWithSummary, self_base_hyperlink: str
    ) -> Self:
        return cls(
            id=user_with_summary.id,
            completed_intro=user_with_summary.completed_intro,
            email=user_with_summary.email,
            is_local=user_with_summary.is_local,
            is_superuser=user_with_summary.is_superuser,
            last_name=user_with_summary.last_name,
            last_login=user_with_summary.last_login,
            machines_count=user_with_summary.machines_count,
            sshkeys_count=user_with_summary.sshkeys_count,
            username=user_with_summary.username,
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{user_with_summary.id}"
                )
            ),
        )


class UsersWithSummaryListResponse(PaginatedResponse[UserWithSummaryResponse]):
    kind = "UserWithSummaryList"
