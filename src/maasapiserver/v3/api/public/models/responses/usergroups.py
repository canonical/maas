# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional, Self

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maasservicelayer.models.usergroups import UserGroup


class UserGroupResponse(HalResponse[BaseHal]):
    kind = "UserGroup"
    id: int
    name: str
    description: Optional[str]

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


class UserGroupsListResponse(PaginatedResponse[UserGroupResponse]):
    kind = "UserGroupsList"
