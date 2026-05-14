# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import BaseModel
from pydantic.config import ConfigDict


class Fabric(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    class_type: str | None = None
    description: str | None = None


class VLAN(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    vid: int
    name: str | None = None
    fabric: str
    mtu: int
    dhcp_on: bool


class Subnet(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    cidr: str
    gateway_ip: str | None = None
    dns_servers: list[str]
    vlan: int
    fabric: str
