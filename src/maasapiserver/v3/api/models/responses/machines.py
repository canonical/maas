from enum import Enum
from typing import Optional

from maasapiserver.v3.api.models.responses.base import (
    BaseHal,
    HalResponse,
    TokenPaginatedResponse,
)
from maasserver.enum import NODE_STATUS_CHOICES
from provisioningserver.drivers.pod.lxd import LXDPodDriver
from provisioningserver.drivers.pod.virsh import VirshPodDriver
from provisioningserver.drivers.power.registry import power_drivers

MachineStatusEnum = Enum(
    "MachineStatus",
    dict({str(name).lower(): int(code) for code, name in NODE_STATUS_CHOICES}),
)
PowerTypeEnum = Enum(
    "PowerType",
    dict(
        {
            str(driver.name).lower(): str(driver.name).lower()
            for driver in power_drivers + [LXDPodDriver(), VirshPodDriver()]
        }
    ),
)


class MachineResponse(HalResponse[BaseHal]):
    kind = "Machine"
    id: int
    system_id: str
    description: str
    owner: Optional[str]
    cpu_speed_MHz: int
    memory_MiB: int
    osystem: str
    architecture: Optional[str]
    distro_series: str
    hwe_kernel: Optional[str]
    locked: bool
    cpu_count: int
    status: MachineStatusEnum
    power_type: Optional[PowerTypeEnum]
    fqdn: str


class MachinesListResponse(TokenPaginatedResponse[MachineResponse]):
    kind = "MachinesList"
