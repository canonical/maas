# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import BaseModel


class UserInfoResponse(BaseModel):
    id: int
    username: str
    is_superuser: bool
