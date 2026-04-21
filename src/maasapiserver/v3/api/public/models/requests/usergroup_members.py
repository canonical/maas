# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Annotated

from pydantic import BaseModel, Field

from maasservicelayer.models.fields import UniqueList


class UserGroupMemberRequest(BaseModel):
    user_id: int = Field(description="The ID of the user to add to the group.")


class BulkGroupMemberRequest(BaseModel):
    user_ids: Annotated[UniqueList[int], Field(min_length=1)] = Field(  # pyright: ignore[reportInvalidTypeForm]
        description="The IDs of the users to add to the group."
    )
