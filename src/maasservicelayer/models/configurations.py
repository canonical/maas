# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from pydantic import BaseModel


class Configuration(BaseModel):
    id: int
    name: str
    value: Any
