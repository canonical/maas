from itertools import cycle

from maasserver.models import Pod

from .common import range_one


def make_vmhosts(count: int):

    power_types = cycle(("virsh", "lxd"))
    vmhosts = []

    for n in range_one(count):
        power_type = next(power_types)
        ip = f"10.10.10.{n}"
        if power_type == "virsh":
            power_parameters = {"power_address": f"qemu+ssh://{ip}/system"}
        else:
            power_parameters = {
                "power_address": f"{ip}:8443",
                "project": "maas",
            }
        vmhosts.append(
            Pod.objects.create(
                name=f"{power_type}{n}",
                power_type=power_type,
                power_parameters=power_parameters,
            )
        )
    return vmhosts
