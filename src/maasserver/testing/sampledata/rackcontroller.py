from itertools import chain
import json
import random
from typing import List

from maasserver.enum import NODE_STATUS
from maasserver.models import ControllerInfo, RackController, Tag
from maasserver.testing.commissioning import FakeCommissioningData
from metadataserver.builtin_scripts.hooks import process_lxd_results
from provisioningserver.utils import version

from .common import range_one
from .script import make_scripts


def make_rackcontroller_infos(count: int, hostname_prefix: str):
    rackcontroller_infos = [
        FakeCommissioningData(
            server_name=f"{hostname_prefix}controller{n:05}",
            kernel_architecture="aarch64",
        )
        for n in range_one(count)
    ]
    return rackcontroller_infos


def make_rackcontrollers(
    rackcontroller_infos: List[FakeCommissioningData], tags: List[Tag]
):
    rackcontrollers = []
    running_version = version.get_running_version()

    for rackcontroller_info in rackcontroller_infos:
        hostname = rackcontroller_info.environment["server_name"]

        rackcontroller = RackController.objects.create(
            hostname=hostname,
            architecture=rackcontroller_info.debian_architecture,
            bios_boot_method="uefi",
            instance_power_parameters={},
            status=NODE_STATUS.DEPLOYED,
        )
        rackcontroller.tags.add(*random.choices(tags, k=10))
        lxd_info = json.dumps(rackcontroller_info.render()).encode()
        process_lxd_results(rackcontroller, lxd_info, 0)
        make_scripts(rackcontroller, lxd_info)
        rackcontrollers.append(rackcontroller)

        ControllerInfo.objects.create(
            node=rackcontroller, version=running_version
        )

    return rackcontrollers


def make_rackcontrollers_primary_or_secondary(rackcontrollers, vlans):
    rack_groups = (
        rackcontrollers[idx : idx + 2]
        for idx in range(0, len(rackcontrollers), 2)
    )
    for vlan in chain(*vlans.values()):
        try:
            racks = next(rack_groups)
            vlan.primary_rack = racks[0]
            if len(racks) == 2:
                vlan.secondary_rack = racks[1]
            vlan.save()
        except StopIteration:
            break
