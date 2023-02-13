from itertools import cycle

from maasserver.models import Pod

from .common import make_name


def make_vmhosts(count: int):
    power_types = cycle(("virsh", "lxd"))
    vmhosts = []

    for _ in range(count):
        power_type = next(power_types)
        hostname = make_name()
        if power_type == "virsh":
            power_parameters = {
                "power_address": f"qemu+ssh://{hostname}/system"
            }
        else:
            power_parameters = {
                "power_address": f"{hostname}:8443",
                "project": "maas",
            }
        vmhosts.append(
            Pod.objects.create(
                name=hostname,
                power_type=power_type,
                power_parameters=power_parameters,
            )
        )
    return vmhosts
