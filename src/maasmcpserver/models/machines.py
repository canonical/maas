# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import BaseModel
from pydantic.config import ConfigDict


class InterfaceSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    type: str
    mac_address: str
    enabled: bool
    vlan_id: int | None = None
    ip_addresses: list[str]


class BlockDevice(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    type: str
    size_gb: float
    model: str | None = None
    serial: str | None = None


class MachineSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    system_id: str
    hostname: str
    status: str
    zone: str
    pool: str
    architecture: str
    cpu_count: int
    memory_mb: int
    owner: str | None = None
    power_state: str | None = None
    tags: list[str]


class MachineDetail(MachineSummary):
    model_config = ConfigDict(extra="ignore")

    interfaces: list[InterfaceSummary]
    block_devices: list[BlockDevice]
    bios_boot_method: str | None = None
    osystem: str | None = None
    distro_series: str | None = None
