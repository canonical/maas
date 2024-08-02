#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any, Dict

from pydantic import BaseModel


class AppRoleLoginRequest(BaseModel):
    role_id: str
    secret_id: str


class KvV2WriteRequest(BaseModel):
    options: Dict[str, Any] | None = None
    data: Dict[str, Any]
