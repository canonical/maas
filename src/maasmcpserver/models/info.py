# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import BaseModel
from pydantic.config import ConfigDict


class RackController(BaseModel):
    model_config = ConfigDict(extra="ignore")

    hostname: str
    rack_id: str
    connection_state: str


class MAASInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    deployment_name: str
    rack_controllers: list[RackController]
