# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import BaseModel, Field


class UserGroupMemberRequest(BaseModel):
    user_id: int = Field(description="The ID of the user to add to the group.")
