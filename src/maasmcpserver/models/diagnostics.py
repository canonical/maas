# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import BaseModel
from pydantic.config import ConfigDict


class MachineEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    created: str
    type: str
    description: str
    username: str | None = None


class ScriptResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    status: str
    exit_status: int | None = None
    output: str | None = None
    started: str | None = None
    ended: str | None = None
