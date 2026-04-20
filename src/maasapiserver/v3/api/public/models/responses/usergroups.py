# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Self

from pydantic import Field

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maasservicelayer.models.usergroups import UserGroup, UserGroupStatistics


class UserGroupResponse(HalResponse[BaseHal]):
    kind: str = Field(default="UserGroup")
    id: int
    name: str
    description: str | None = None

    @classmethod
    def from_model(
        cls, usergroup: UserGroup, self_base_hyperlink: str
    ) -> Self:
        return cls(
            id=usergroup.id,
            name=usergroup.name,
            description=usergroup.description,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{usergroup.id}"
                )
            ),
        )


class UserGroupStatisticsResponse(HalResponse[BaseHal]):
    kind: str = Field(default="UserGroupStatistics")
    id: int
    user_count: int

    @classmethod
    def from_model(
        cls, usergroup: UserGroupStatistics, self_base_hyperlink: str
    ) -> Self:
        return cls(
            id=usergroup.id,
            user_count=usergroup.user_count,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{usergroup.id}"
                )
            ),
        )


class UserGroupsListResponse(PaginatedResponse[UserGroupResponse]):
    kind: str = Field(default="UserGroupsList")


class UserGroupsStatisticsListResponse(
    PaginatedResponse[UserGroupStatisticsResponse]
):
    kind: str = Field(default="UserGroupsStatisticsList")
