from typing import Any

from maasapiserver.v3.api.models.responses.machines import PowerTypeEnum
from maasapiserver.v3.models.bmc import Bmc
from maasapiserver.v3.models.machines import Machine
from maasapiserver.v3.models.users import User
from tests.fixtures.factories.node import create_test_machine_entry
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_machine(
    fixture: Fixture,
    bmc: Bmc,
    user: User,
    **extra_details: Any,
) -> Machine:
    created_machine = await create_test_machine_entry(
        fixture,
        bmc_id=bmc.id,
        owner_id=user.id,
        osystem="ubuntu",
        distro_series="jammy",
        archtecture="amd64",
        hwe_kernel="hwe-22.04",
        **extra_details,
    )
    created_machine["owner"] = user.username
    created_machine["power_type"] = PowerTypeEnum.virsh.name
    created_machine["fqdn"] = f"{created_machine['hostname']}."
    return Machine(
        **created_machine,
    )
