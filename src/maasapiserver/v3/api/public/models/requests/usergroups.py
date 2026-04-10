# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from pydantic import BaseModel, Field

from maasapiserver.v3.api.public.models.requests.base import NamedBaseModel
from maasservicelayer.builders.usergroups import UserGroupBuilder
from maasservicelayer.db.filters import Clause
from maasservicelayer.db.repositories.usergroups import UserGroupsClauseFactory


class UserGroupsFiltersParam(BaseModel):
    group_name: Optional[str] = Field(
        default=None, title="Filter by group name"
    )

    def to_clause(self) -> Optional[Clause]:
        if self.group_name:
            return UserGroupsClauseFactory.with_name_like(self.group_name)
        return None

    def to_href_format(self) -> str:
        return f"&group_name={self.group_name}" if self.group_name else ""


class UserGroupRequest(NamedBaseModel):
    description: Optional[str] = Field(
        description="The description of the group.", default=None
    )

    def to_builder(self) -> UserGroupBuilder:
        return UserGroupBuilder(name=self.name, description=self.description)
