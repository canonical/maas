# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from fastapi import Query
from pydantic import BaseModel, Field

from maasapiserver.v3.api.public.models.requests.base import NamedBaseModel
from maasservicelayer.builders.usergroups import UserGroupBuilder
from maasservicelayer.db.filters import Clause
from maasservicelayer.db.repositories.usergroups import UserGroupsClauseFactory


class UserGroupsFiltersParam(BaseModel):
    ids: list[int] | None = Field(
        Query(
            default=None,
            alias="id",
            description="Filter by Group ID",
        )
    )

    group_name: str | None = Field(
        Query(
            default=None,
            alias="group_name",
            description="Filter by Group Name",
        )
    )

    def to_clause(self) -> Clause | None:
        if self.ids is not None:
            return UserGroupsClauseFactory.with_ids(self.ids)
        if self.group_name is not None:
            return UserGroupsClauseFactory.with_name_like(self.group_name)
        return None

    def to_href_format(self) -> str | None:
        if self.ids is not None:
            return "&".join([f"id={id}" for id in self.ids])
        if self.group_name is not None:
            return f"group_name={self.group_name}"
        return None


class UserGroupRequest(NamedBaseModel):
    description: str | None = Field(
        description="The description of the group.", default=None
    )

    def to_builder(self) -> UserGroupBuilder:
        return UserGroupBuilder(name=self.name, description=self.description)
