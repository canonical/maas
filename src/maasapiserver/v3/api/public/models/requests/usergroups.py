# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from pydantic import Field

from maasapiserver.v3.api.public.models.requests.base import NamedBaseModel
from maasservicelayer.builders.usergroups import UserGroupBuilder


class UserGroupRequest(NamedBaseModel):
    description: Optional[str] = Field(
        description="The description of the group.", default=None
    )

    def to_builder(self) -> UserGroupBuilder:
        return UserGroupBuilder(name=self.name, description=self.description)
