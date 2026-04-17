# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Self

from pydantic import BaseModel

from maasapiserver.v3.api.public.models.responses.base import PaginatedResponse
from maasservicelayer.models.usergroup_members import UserGroupMember


class UserGroupMemberResponse(BaseModel):
    kind = "UserGroupMember"
    user_id: int
    username: str
    email: str

    @classmethod
    def from_model(cls, member: UserGroupMember) -> Self:
        return cls(
            user_id=member.id,
            username=member.username,
            email=member.email,
        )


class UserGroupMembersListResponse(PaginatedResponse[UserGroupMemberResponse]):
    kind = "UserGroupMembersList"
