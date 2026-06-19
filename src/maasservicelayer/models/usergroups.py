# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import BaseModel, Field

from maasservicelayer.models.base import (
    generate_builder,
    MaasBaseModel,
    MaasTimestampedBaseModel,
)


@generate_builder()
class UserGroup(MaasTimestampedBaseModel):
    name: str
    description: str | None = None


class UserGroupStatistics(MaasBaseModel):
    id: int
    user_count: int


class UserGroupsByUser(BaseModel):
    """Maps user ids to the groups each user is a member of."""

    groups_by_user: dict[int, list[UserGroup]] = Field(default_factory=dict)

    def for_user(self, user_id: int) -> list[UserGroup]:
        return self.groups_by_user.get(user_id, [])
