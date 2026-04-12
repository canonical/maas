# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

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

    def to_clause(self) -> Clause | None:
        if self.ids is not None:
            return UserGroupsClauseFactory.with_ids(self.ids)
        return None

    def to_href_format(self) -> str | None:
        if self.ids is not None:
            return "&".join([f"id={id}" for id in self.ids])
        return None


class UserGroupRequest(NamedBaseModel):
    description: Optional[str] = Field(
        description="The description of the group.", default=None
    )

    def to_builder(self) -> UserGroupBuilder:
        return UserGroupBuilder(name=self.name, description=self.description)
