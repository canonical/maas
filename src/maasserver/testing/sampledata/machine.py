from itertools import cycle
import json
import random
from typing import List

from django.contrib.auth.models import User

from maasserver.enum import NODE_STATUS
from maasserver.models import BMC, Machine, Pod, Tag
from maasserver.testing.commissioning import FakeCommissioningData
from metadataserver.builtin_scripts.hooks import (
    process_lxd_results,
    update_boot_interface,
)

from . import LOGGER
from .common import range_one
from .defs import MACHINE_ARCHES, MACHINE_STATUSES
from .script import make_scripts


def make_machine_infos(count: int, hostname_prefix: str):
    architectures = cycle(MACHINE_ARCHES)
    machine_infos = [
        FakeCommissioningData(
            server_name=f"{hostname_prefix}{n:05}",
            kernel_architecture=next(architectures),
        )
        for n in range_one(count)
    ]
    return machine_infos


def make_machines(
    machine_infos: List[FakeCommissioningData],
    vmhosts: List[Pod],
    tags: List[Tag],
    users: List[User],
    redfish_address: str,
):
    bmcs = cycle(vmhosts)
    owners = cycle(users)
    machines = []
    # ensure machines in a VM host have matching arches
    vmhost_ratio = len(MACHINE_ARCHES) * 2

    if redfish_address:
        redfish_bmc = BMC.objects.create(
            power_type="redfish",
            power_parameters={
                "power_address": redfish_address,
                "power_user": "redfish",
                "power_pass": "secret",
            },
        )
    else:
        redfish_bmc = None

    for n, machine_info in enumerate(machine_infos, 1):
        hostname = machine_info.environment["server_name"]
        if n % vmhost_ratio == 0:
            bmc = next(bmcs)
            instance_power_parameters = {
                (
                    "instance_name" if bmc.power_type == "lxd" else "power_id"
                ): hostname
            }
        elif redfish_bmc:
            bmc = redfish_bmc
            instance_power_parameters = {"node_id": hostname}
        else:
            bmc = BMC.objects.create(power_type="manual")
            instance_power_parameters = {}

        status = next(MACHINE_STATUSES)
        owner = (
            None
            if status in (NODE_STATUS.NEW, NODE_STATUS.READY)
            else next(owners)
        )
        machine = Machine.objects.create(
            hostname=hostname,
            architecture=machine_info.debian_architecture,
            bios_boot_method="uefi",
            bmc=bmc,
            instance_power_parameters=instance_power_parameters,
            status=status,
            owner=owner,
        )
        machine.tags.add(*random.choices(tags, k=10))
        lxd_info = json.dumps(machine_info.render()).encode()
        process_lxd_results(machine, lxd_info, 0)
        update_boot_interface(
            machine, machine_info.render_kernel_cmdline().encode(), 0
        )
        make_scripts(machine, lxd_info)
        machines.append(machine)
        if n % 10 == 0:
            LOGGER.info(f" created {n} machines")
    return machines
