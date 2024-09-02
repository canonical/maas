# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class Secret(BaseModel):
    created: datetime
    updated: datetime
    path: str
    value: Any
