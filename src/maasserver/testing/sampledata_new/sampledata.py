from django.db import transaction

from . import LOGGER
from .common import make_name
from .defs import (
    MACHINES_PER_FABRIC,
    TAG_COUNT,
    VLAN_PER_FABRIC_COUNT,
    VMHOST_COUNT,
)


@transaction.atomic
def generate(
    machine_count: int,
    hostname_prefix: str,
    tag_prefix: str,
    redfish_address: str,
):
    from .machine import make_machine_infos, make_machines, set_machine_status
    from .network import make_network_interfaces, make_networks
    from .storage import make_storage_setup
    from .tag import make_tags
    from .vmhost import make_vmhosts

    if not hostname_prefix:
        hostname_prefix = make_name()
        LOGGER.info(f"machine hostname prefix is '{hostname_prefix}'")
    if not tag_prefix:
        tag_prefix = make_name()
        LOGGER.info(f"tag prefix is '{tag_prefix}'")

    fabric_count = int(machine_count / MACHINES_PER_FABRIC) + 1
    LOGGER.info(
        f"creating {(VLAN_PER_FABRIC_COUNT + 1) * fabric_count} VLANs "
        f"on {fabric_count} fabrics"
    )
    vlans, ip_networks = make_networks(VLAN_PER_FABRIC_COUNT, fabric_count)
    LOGGER.info(f"creating {TAG_COUNT} tags")
    tags = make_tags(TAG_COUNT, tag_prefix)
    LOGGER.info(f"creating {VMHOST_COUNT} VM hosts")
    vmhosts = make_vmhosts(VMHOST_COUNT)
    LOGGER.info("creating machine resources data")
    machine_infos = make_machine_infos(machine_count, hostname_prefix)
    LOGGER.info("creating network interfaces")
    make_network_interfaces(machine_infos, vlans, ip_networks)
    make_storage_setup(machine_infos)
    LOGGER.info(f"creating {machine_count} machines")
    machines = make_machines(machine_infos, vmhosts, tags, redfish_address)
    set_machine_status(machines)
