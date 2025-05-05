from django.db import transaction

from ...sqlalchemy import service_layer
from . import LOGGER
from .common import make_name
from .defs import (
    ADMIN_COUNT,
    EVENT_PER_MACHINE,
    EVENT_TYPE_COUNT,
    MACHINES_PER_FABRIC,
    OWNERDATA_PER_MACHINE_COUNT,
    RACKCONTROLLER_COUNT,
    TAG_COUNT,
    USER_COUNT,
    VLAN_PER_FABRIC_COUNT,
    VMHOST_COUNT,
)


@transaction.atomic
def generate(
    machine_count: int,
    hostname_prefix: str,
    ownerdata_prefix: str,
    tag_prefix: str,
    redfish_address: str,
):
    service_layer.init()
    from metadataserver.builtin_scripts import load_builtin_scripts

    from .devices import make_pci_devices
    from .event import make_event_types, make_events
    from .machine import make_machine_infos, make_machines
    from .network import make_network_interfaces, make_networks
    from .ownerdata import make_ownerdata
    from .rackcontroller import (
        make_rackcontroller_infos,
        make_rackcontrollers,
        make_rackcontrollers_primary_or_secondary,
    )
    from .storage import make_storage_setup
    from .tag import make_tags
    from .user import make_users
    from .vmhost import make_vmhosts

    if not hostname_prefix:
        hostname_prefix = make_name()
        LOGGER.info(f"machine hostname prefix is '{hostname_prefix}'")
    if not ownerdata_prefix:
        ownerdata_prefix = make_name()
        LOGGER.info(f"ownerdata prefix is '{ownerdata_prefix}'")
    if not tag_prefix:
        tag_prefix = make_name()
        LOGGER.info(f"tag prefix is '{tag_prefix}'")

    LOGGER.info(f"creating {EVENT_TYPE_COUNT} event types")
    event_types = make_event_types(EVENT_TYPE_COUNT)

    fabric_count = int(machine_count / MACHINES_PER_FABRIC) + 1
    LOGGER.info(
        f"creating {(VLAN_PER_FABRIC_COUNT + 1) * fabric_count} VLANs "
        f"on {fabric_count} fabrics"
    )
    vlans, ip_networks = make_networks(VLAN_PER_FABRIC_COUNT, fabric_count)

    LOGGER.info(f"creating {ADMIN_COUNT} admins and {USER_COUNT} users")
    users = make_users(ADMIN_COUNT, USER_COUNT)

    LOGGER.info(f"creating {TAG_COUNT} tags")
    tags = make_tags(TAG_COUNT, tag_prefix)

    LOGGER.info(f"creating {VMHOST_COUNT} VM hosts")
    vmhosts = make_vmhosts(VMHOST_COUNT)

    LOGGER.info("creating builtin scripts")
    load_builtin_scripts()

    LOGGER.info("creating machine resources data")
    machine_infos = make_machine_infos(machine_count, hostname_prefix)

    LOGGER.info("creating rackcontroller resources data")
    rackcontroller_infos = make_rackcontroller_infos(
        RACKCONTROLLER_COUNT, hostname_prefix
    )

    LOGGER.info("creating network interfaces")
    make_network_interfaces(machine_infos, vlans, ip_networks)
    make_network_interfaces(rackcontroller_infos, vlans, ip_networks)

    LOGGER.info(f"creating {RACKCONTROLLER_COUNT} rack controllers")
    make_storage_setup(rackcontroller_infos)
    rackcontrollers = make_rackcontrollers(rackcontroller_infos, tags)
    make_rackcontrollers_primary_or_secondary(rackcontrollers, vlans)

    LOGGER.info(f"creating {machine_count} machines")
    make_storage_setup(machine_infos)
    machines = make_machines(
        machine_infos, vmhosts, tags, users, redfish_address
    )

    LOGGER.info("creating 5 pci devices per machine")
    make_pci_devices(machines)

    LOGGER.info(f"creating {OWNERDATA_PER_MACHINE_COUNT} owner data")
    make_ownerdata(OWNERDATA_PER_MACHINE_COUNT, ownerdata_prefix, machines)

    LOGGER.info("creating machine events")
    make_events(EVENT_PER_MACHINE, event_types, machines)
    service_layer.close()
