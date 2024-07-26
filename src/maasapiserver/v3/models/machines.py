from typing import Optional

from maasapiserver.v3.api.models.responses.base import BaseHal, BaseHref
from maasapiserver.v3.api.models.responses.machines import (
    MachineResponse,
    MachineStatusEnum,
    PowerTypeEnum,
)
from maasapiserver.v3.models.base import MaasTimestampedBaseModel


class Machine(MaasTimestampedBaseModel):
    system_id: str
    description: str
    owner: Optional[str]
    cpu_speed: int
    memory: int
    osystem: str
    architecture: Optional[str]
    distro_series: str
    hwe_kernel: Optional[str]
    locked: bool
    cpu_count: int
    status: MachineStatusEnum
    power_type: Optional[PowerTypeEnum]
    fqdn: str

    def to_response(self, self_base_hyperlink: str) -> MachineResponse:
        return MachineResponse(
            id=self.id,
            system_id=self.system_id,
            description=self.description,
            owner=self.owner,
            cpu_speed_MHz=self.cpu_speed,
            memory_MiB=self.memory,
            osystem=self.osystem,
            architecture=self.architecture,
            distro_series=self.distro_series,
            hwe_kernel=self.hwe_kernel,
            locked=self.locked,
            cpu_count=self.cpu_count,
            status=self.status,
            power_type=self.power_type,
            fqdn=self.fqdn,
            hal_links=BaseHal(
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{self.id}"
                )
            ),
        )
