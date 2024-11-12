# Copyright 2012-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Builtin script hooks, run upon receipt of ScriptResult"""


from collections import defaultdict
from datetime import timedelta
import fnmatch
import functools
from functools import partial
import json
import logging
import operator
from operator import itemgetter
import re
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from temporalio.common import RetryPolicy

from maascommon.workflows.configure import CONFIGURE_AGENT_WORKFLOW_NAME
from maasserver.enum import (
    NODE_DEVICE_BUS,
    NODE_METADATA,
    NODE_STATUS,
    NODE_TYPE,
)
from maasserver.models import (
    Event,
    Interface,
    Node,
    NodeDevice,
    NodeDeviceVPD,
    NodeMetadata,
    NUMANode,
    NUMANodeHugepages,
    PhysicalBlockDevice,
    PhysicalInterface,
)
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.models.subnet import Subnet
from maasserver.models.tag import Tag
from maasserver.storage_custom import (
    apply_layout_to_machine,
    get_storage_layout,
    UnappliableLayout,
)
from maasserver.utils.converters import human_readable_bytes
from maasserver.utils.orm import get_one
from maasserver.utils.osystems import get_release
from maasserver.workflow import start_workflow
from metadataserver.builtin_scripts.network import update_node_interfaces
from metadataserver.enum import HARDWARE_SYNC_ACTIONS, HARDWARE_TYPE
from provisioningserver.events import EVENT_TYPES
from provisioningserver.refresh.node_info_scripts import (
    COMMISSIONING_OUTPUT_NAME,
    GET_FRUID_DATA_OUTPUT_NAME,
    KERNEL_CMDLINE_OUTPUT_NAME,
    LIST_MODALIASES_OUTPUT_NAME,
    NODE_INFO_SCRIPTS,
)
from provisioningserver.utils.arch import kernel_to_debian_architecture
from provisioningserver.utils.ipaddr import is_ipoib_mac
from provisioningserver.utils.lxd import parse_lxd_cpuinfo, parse_lxd_networks

logger = logging.getLogger(__name__)


SWITCH_TAG_NAME = "switch"
SWITCH_HARDWARE = [
    # Seen on Facebook Wedge 40 switch:
    #     pci:v000014E4d0000B850sv000014E4sd0000B850bc02sc00i00
    #     (Broadcom Trident II ASIC)
    {
        "modaliases": ["pci:v000014E4d0000B850sv*sd*bc*sc*i*"],
        "tag": "bcm-trident2-asic",
        "comment": 'Broadcom High-Capacity StrataXGS "Trident II" '
        "Ethernet Switch ASIC",
    },
    # Seen on Facebook Wedge 100 switch:
    #     pci:v000014E4d0000B960sv000014E4sd0000B960bc02sc00i00
    #     (Broadcom Tomahawk ASIC)
    {
        "modaliases": ["pci:v000014E4d0000B960sv*sd*bc*sc*i*"],
        "tag": "bcm-tomahawk-asic",
        "comment": 'Broadcom High-Density 25/100 StrataXGS "Tomahawk" '
        "Ethernet Switch ASIC",
    },
]


def _parse_interface_speed(port):
    supported_modes = port.get("supported_modes")
    if supported_modes is None:
        return 0

    # Return the highest supported speed.
    return max(
        int(supported_mode.split("base")[0])
        for supported_mode in supported_modes
    )


def parse_interfaces(node, data):
    """Return a dict of interfaces keyed by MAC address."""
    interfaces = {}

    resources = data["resources"]
    ifaces_info = parse_lxd_networks(data["networks"])

    def process_port(card, port):
        mac = port.get("address")
        # See LP:1939456
        if is_ipoib_mac(mac):
            return
        interface = {
            "name": port.get("id"),
            "link_connected": port.get("link_detected"),
            "interface_speed": _parse_interface_speed(port),
            "link_speed": port.get("link_speed", 0),
            "numa_node": card.get("numa_node", 0),
            "vendor": card.get("vendor"),
            "product": card.get("product"),
            "firmware_version": card.get("firmware_version"),
            "sriov_max_vf": card.get("sriov", {}).get("maximum_vfs", 0),
            "pci_address": card.get("pci_address"),
            "usb_address": card.get("usb_address"),
        }
        # Assign the IP addresses to this interface
        link = ifaces_info.get(interface["name"])
        interface["ips"] = link["addresses"] if link else []

        interfaces[mac] = interface

    network_cards = resources.get("network", {}).get("cards", {})
    for card in network_cards:
        for port in card.get("ports", []):
            process_port(card, port)

        # don't sync VFs for deployed machines, MAAS has no way of representing
        # VFs, since they would persist when the machine is released and break
        # subsequent deploys.
        if node.status != NODE_STATUS.DEPLOYED:
            # entry can be present but None
            vfs = card.get("sriov", {}).get("vfs") or {}
            for vf in vfs:
                for vf_port in vf.get("ports", []):
                    process_port(vf, vf_port)

    return interfaces


def update_interface_details(interface, details):
    """Update details for an existing interface from commissioning data.

    This should be passed details from the parse_interfaces call.

    """
    iface_details = details.get(interface.mac_address)
    if not iface_details:
        return

    update_fields = []
    for field in (
        "name",
        "vendor",
        "product",
        "firmware_version",
        "link_speed",
        "interface_speed",
    ):
        value = iface_details.get(field, "")
        if getattr(interface, field) != value:
            setattr(interface, field, value)
        update_fields.append(field)

    sriov_max_vf = iface_details.get("sriov_max_vf")
    if interface.sriov_max_vf != sriov_max_vf:
        interface.sriov_max_vf = sriov_max_vf
        update_fields.append("sriov_max_vf")
    if update_fields:
        interface.save(update_fields=["updated", *update_fields])


BOOTIF_RE = re.compile(r"BOOTIF=\d\d-([0-9a-f]{2}([:-][0-9a-f]{2}){5})")


def parse_bootif_cmdline(cmdline):
    match = BOOTIF_RE.search(cmdline)
    return match[1].replace("-", ":").lower() if match else None


def update_boot_interface(node, output, exit_status):
    """Update the boot interface from the kernel command line.

    If a BOOTIF parameter is present, that's the interface the machine
    booted off.
    """
    if exit_status != 0:
        logger.error(
            "%s: kernel-cmdline failed with status: "
            "%s." % (node.hostname, exit_status)
        )
        return

    cmdline = output.decode("utf-8")
    boot_mac = parse_bootif_cmdline(cmdline)
    if boot_mac is None:
        # This is ok. For example, if a rack controller runs the
        # commissioning scripts, it won't have the BOOTIF parameter
        # there.
        return None

    try:
        node.boot_interface = node.current_config.interface_set.get(
            type="physical", mac_address=boot_mac
        )
    except Interface.DoesNotExist:
        logger.error(
            f"BOOTIF interface {boot_mac} doesn't exist for {node.fqdn}"
        )
    except Interface.MultipleObjectsReturned:
        logger.error(
            f"Multiple physical interfaces found with {boot_mac} for {node.fqdn}"
        )
    else:
        node.save(update_fields=["boot_interface"])


def update_node_network_information(node, data, numa_nodes):
    network_devices = {}
    # Skip network configuration if set by the user.
    if node.skip_networking:
        # Turn off skip_networking now that the hook has been called.
        node.skip_networking = False
        node.save(update_fields=["skip_networking"])
        return network_devices

    update_node_interfaces(node, data)
    interfaces_info = parse_interfaces(node, data)
    current_interfaces = set()

    for mac, iface in interfaces_info.items():
        link_connected = iface.get("link_connected")
        sriov_max_vf = iface.get("sriov_max_vf")

        try:
            interface = PhysicalInterface.objects.get(mac_address=mac)
        except PhysicalInterface.DoesNotExist:
            continue
        interface.numa_node = numa_nodes[iface["numa_node"]]

        if iface.get("pci_address"):
            network_devices[iface.get("pci_address")] = interface
        elif iface.get("usb_address"):
            network_devices[iface.get("usb_address")] = interface

        current_interfaces.add(interface)
        if sriov_max_vf:
            interface.add_tag("sriov")
            interface.save(update_fields=["tags"])

        if (
            not link_connected
            and not interface.ip_addresses.filter(
                subnet__vlan=interface.vlan
            ).exists()
        ):
            # This interface is now disconnected.
            if interface.vlan is not None:
                interface.vlan = None
                interface.save(update_fields=["vlan", "updated"])
        interface.save()

    # If a machine boots by UUID before commissioning(s390x) no boot_interface
    # will be set as interfaces existed during boot. Set it using the
    # boot_cluster_ip now that the interfaces have been created.
    if node.boot_interface is None and node.boot_cluster_ip is not None:
        subnet = Subnet.objects.get_best_subnet_for_ip(node.boot_cluster_ip)
        if subnet:
            node.boot_interface = node.current_config.interface_set.filter(
                vlan=subnet.vlan,
            ).first()
            node.save(update_fields=["boot_interface"])

    # Pods are already deployed. MAAS captures the network state, it does
    # not change it.
    if node.is_commissioning():
        # Only configured Interfaces are tested so configuration must be done
        # before regeneration.
        node.set_initial_networking_configuration()

        if node.current_testing_script_set is not None:
            # LP: #1731353 - Regenerate ScriptResults before deleting Interfaces.
            # This creates a ScriptResult with proper parameters for each interface
            # on the system. Interfaces no long available will be deleted which
            # causes a casade delete on their assoicated ScriptResults.
            node.current_testing_script_set.regenerate(
                storage=False, network=True
            )

    return network_devices


def _process_system_information(node, system_data):
    def validate_and_set_data(key, value):
        # Some vendors use placeholders when not setting data.
        if not value or value.lower() in ["0123456789", "none"]:
            value = None
        if value:
            NodeMetadata.objects.update_or_create(
                node=node, key=key, defaults={"value": value}
            )
        else:
            NodeMetadata.objects.filter(node=node, key=key).delete()

    uuid = system_data.get("uuid")
    if not uuid or not re.search(
        r"^[\da-f]{8}[\-]?([\da-f]{4}[\-]?){3}[\da-f]{12}$", uuid, re.I
    ):
        # Convert "" to None, so that the unique check isn't triggered.
        # Some vendors store the service tag as the UUID which is not unique,
        # if the UUID isn't a valid UUID ignore it.
        node.hardware_uuid = None
    else:
        # LP:1893690 - If the UUID is valid check that it isn't duplicated
        # with save so the check is atomic.
        node.hardware_uuid = uuid
        try:
            node.save()
        except ValidationError as e:
            # Check that the ValidationError is due to the hardware_uuid
            # other errors will be caught and logged later.
            if "hardware_uuid" in e.error_dict:
                node.hardware_uuid = None
                # If the UUID isn't really unique make sure it isn't stored on
                # any Node.
                Node.objects.filter(hardware_uuid=uuid).update(
                    hardware_uuid=None
                )

    # Gather system information. Custom built machines and some Supermicro
    # servers do not provide this information.
    for i in ["vendor", "product", "family", "version", "sku", "serial"]:
        validate_and_set_data(f"system_{i}", system_data.get(i))

    # Gather mainboard information, all systems should have this.
    motherboard = system_data.get("motherboard")
    # LP:1881116 - LXD will sometimes define the value as None.
    motherboard = motherboard if isinstance(motherboard, dict) else {}
    for i in ["vendor", "product", "serial", "version"]:
        validate_and_set_data(f"mainboard_{i}", motherboard.get(i))

    # Gather mainboard firmware information.
    firmware = system_data.get("firmware")
    firmware = firmware if isinstance(firmware, dict) else {}
    for i in ["vendor", "date", "version"]:
        validate_and_set_data(f"mainboard_firmware_{i}", firmware.get(i))

    # Gather chassis information.
    chassis = system_data.get("chassis")
    chassis = chassis if isinstance(chassis, dict) else {}
    for i in ["vendor", "type", "serial", "version"]:
        validate_and_set_data(f"chassis_{i}", chassis.get(i))

    # Set the virtual tag.
    system_type = system_data.get("type")
    tag, _ = Tag.objects.get_or_create(name="virtual")
    if not system_type or system_type == "physical":
        node.tags.remove(tag)
    else:
        node.tags.add(tag)


def _device_diff(
    old: NodeDevice,
    new: dict[str, Any],
    new_hardware_type: HARDWARE_TYPE,
    numa_node: int,
    physical_blockdevice: PhysicalBlockDevice,
    physical_interface: PhysicalInterface,
    commissioning_driver: str,
    device_vpd: dict[str, Any],
) -> bool:
    if not old:
        return True

    diff = not (
        old.hardware_type == new_hardware_type
        and old.numa_node == numa_node
        and old.physical_blockdevice == physical_blockdevice
        and old.physical_interface == physical_interface
        and old.vendor_name == new.get("vendor")
        and old.product_name == new.get("product")
        and old.commissioning_driver == commissioning_driver
    )

    for vpd in NodeDeviceVPD.objects.filter(node_device=old):
        diff = diff or (device_vpd.get(vpd.key) != vpd.value)
    return diff


def _add_or_update_node_device(
    node,
    numa_nodes,
    network_devices,
    storage_devices,
    gpu_devices,
    old_devices,
    bus,
    device,
    address,
    key,
    commissioning_driver,
):
    device_vpd = device.get("vpd", {}).get("entries", {})
    network_device = network_devices.get(address)
    storage_device = storage_devices.get(address)

    if network_device:
        hardware_type = HARDWARE_TYPE.NETWORK
    elif storage_device:
        hardware_type = HARDWARE_TYPE.STORAGE
    elif address in gpu_devices:
        hardware_type = HARDWARE_TYPE.GPU
    else:
        hardware_type = HARDWARE_TYPE.NODE

    if "numa_node" in device:
        numa_node = numa_nodes[device["numa_node"]]
    else:
        # LXD doesn't map USB devices to NUMA node nor does it map
        # USB devices to USB controller on the PCI bus. Map to the
        # default numa node in cache.
        numa_node = numa_nodes[0]

    if key in old_devices:
        node_device = old_devices.pop(key)

        if _device_diff(
            node_device,
            device,
            hardware_type,
            numa_node,
            storage_device,
            network_device,
            commissioning_driver,
            device_vpd,
        ):
            node_device.hardware_type = hardware_type
            node_device.numa_node = numa_node
            node_device.physical_block_device = storage_device
            node_device.physical_interface = network_device
            node_device.vendor_name = device.get("vendor")
            node_device.product_name = device.get("product")
            node_device.commissioning_driver = commissioning_driver
            node_device.save()
            _add_node_device_vpd(node_device, device_vpd)
            _hardware_sync_node_device_notify(
                node, node_device, HARDWARE_SYNC_ACTIONS.UPDATED
            )
    else:
        pci_address = device.get("pci_address")
        create_args = {
            "bus": bus,
            "hardware_type": hardware_type,
            "node_config": node.current_config,
            "numa_node": numa_node,
            "physical_blockdevice": storage_device,
            "physical_interface": network_device,
            "vendor_id": device["vendor_id"],
            "product_id": device["product_id"],
            "vendor_name": device.get("vendor"),
            "product_name": device.get("product"),
            "commissioning_driver": commissioning_driver,
            "bus_number": device.get("bus_address"),
            "device_number": device.get("device_address"),
            "pci_address": pci_address,
        }

        node_device = None
        try:
            node_device = NodeDevice.objects.create(**create_args)
        except ValidationError:
            # A device was replaced, delete the old one before creating
            # the new one.
            qs = NodeDevice.objects.filter(node_config=node.current_config)
            if pci_address is not None:
                identifier = {"pci_address": pci_address}
            else:
                identifier = {
                    "bus_number": device.get("bus_address"),
                    "device_number": device.get("device_address"),
                }
            if storage_device and network_device:
                qs = qs.filter(
                    Q(**identifier)
                    | Q(physical_blockdevice=storage_device)
                    | Q(physical_interface=network_device)
                )
            elif storage_device:
                qs = qs.filter(
                    Q(**identifier) | Q(physical_blockdevice=storage_device)
                )
            elif network_device:
                qs = qs.filter(
                    Q(**identifier) | Q(physical_interface=network_device)
                )
            else:
                qs = qs.filter(**identifier)
            qs.delete()
            node_device = NodeDevice.objects.create(**create_args)
        finally:
            _add_node_device_vpd(node_device, device_vpd)
            _hardware_sync_node_device_notify(
                node, node_device, HARDWARE_SYNC_ACTIONS.ADDED
            )


def _add_node_device_vpd(node_device, device_vpd):
    with transaction.atomic():
        NodeDeviceVPD.objects.filter(node_device=node_device).delete()

        NodeDeviceVPD.objects.bulk_create(
            NodeDeviceVPD(
                node_device=node_device,
                key=key,
                # the value might contain \x00 which isn't allowed by the database.
                value=value.encode("unicode-escape").decode("utf-8"),
            )
            for key, value in device_vpd.items()
        )


def _process_pcie_devices(add_func, data):
    for device in data.get("pci", {}).get("devices", []):
        key = (
            device["vendor_id"],
            device["product_id"],
            device["pci_address"],
        )
        add_func(
            NODE_DEVICE_BUS.PCIE,
            device,
            device["pci_address"],
            key,
            device.get("driver"),
        )


def _process_usb_devices(add_func, data):
    for device in data.get("usb", {}).get("devices", []):
        usb_address = "{}:{}".format(
            device["bus_address"],
            device["device_address"],
        )
        key = (device["vendor_id"], device["product_id"], usb_address)
        # the "interfaces" field can be present but None
        interfaces = device.get("interfaces") or []
        # USB devices can have different drivers for each
        # functionality. e.g a webcam has a video and audio driver.
        commissioning_driver = ", ".join(
            {
                interface["driver"]
                for interface in interfaces
                if "driver" in interface
            }
        )
        add_func(
            NODE_DEVICE_BUS.USB, device, usb_address, key, commissioning_driver
        )


def update_node_devices(
    node, data, numa_nodes, network_devices=None, storage_devices=None
):
    # network and storage devices are only passed if they were updated. If
    # configuration was skipped or running on a controller devices must be
    # loaded for mapping.
    if not network_devices:
        network_devices = {}
        mac_to_dev_ids = {}
        for card in data.get("network", {}).get("cards", []):
            for port in card.get("ports", []):
                if "address" not in port:
                    continue
                if "pci_address" in card:
                    mac_to_dev_ids[port["address"]] = card["pci_address"]
                elif "usb_address" in card:
                    mac_to_dev_ids[port["address"]] = card["usb_address"]
        for iface in node.current_config.interface_set.filter(
            mac_address__in=mac_to_dev_ids.keys()
        ):
            network_devices[mac_to_dev_ids[iface.mac_address]] = iface

    if not storage_devices:
        storage_devices = {}
        name_to_dev_ids = {}
        for disk in _condense_luns(data.get("storage", {}).get("disks", [])):
            if "pci_address" in disk:
                name_to_dev_ids[disk["id"]] = disk["pci_address"]
            elif "usb_address" in disk:
                name_to_dev_ids[disk["id"]] = disk["usb_address"]
        for block_dev in node.physicalblockdevice_set.filter(
            name__in=name_to_dev_ids.keys()
        ):
            storage_devices[name_to_dev_ids[block_dev.name]] = block_dev

    # Gather the list of GPUs for setting the type.
    gpu_devices = set()
    for card in data.get("gpu", {}).get("cards", []):
        if "pci_address" in card:
            gpu_devices.add(card["pci_address"])
        elif "usb_address" in card:
            gpu_devices.add(card["usb_address"])

    old_devices = {
        (
            node_device.vendor_id,
            node_device.product_id,
            (
                node_device.pci_address
                if node_device.bus == NODE_DEVICE_BUS.PCIE
                else f"{node_device.bus_number}:{node_device.device_number}"
            ),
        ): node_device
        for node_device in node.current_config.nodedevice_set.all()
    }

    add_func = partial(
        _add_or_update_node_device,
        node,
        numa_nodes,
        network_devices,
        storage_devices,
        gpu_devices,
        old_devices,
    )

    _process_pcie_devices(add_func, data)
    _process_usb_devices(add_func, data)

    _hardware_sync_node_devices_notify(
        node, old_devices.values(), HARDWARE_SYNC_ACTIONS.REMOVED
    )

    NodeDevice.objects.filter(
        id__in=[node_device.id for node_device in old_devices.values()]
    ).delete()


def _process_lxd_resources(node, data):
    """Process the resources results of the `COMMISSIONING_OUTPUT_NAME` script."""
    resources = data["resources"]
    update_deployment_resources = node.status == NODE_STATUS.DEPLOYED
    # Update CPU details.
    old_cpu_count = node.cpu_count
    node.cpu_count, node.cpu_speed, cpu_model, numa_nodes = parse_lxd_cpuinfo(
        resources
    )

    old_memory = node.memory
    # Update memory.
    node.memory, hugepages_size, numa_nodes_info = _parse_memory(
        resources.get("memory", {}), numa_nodes
    )

    if old_memory != node.memory:
        _hardware_sync_memory_notify(node, old_memory)

    # Create or update NUMA nodes. This must be kept as a dictionary as not all
    # systems maintain linear continuity. e.g the PPC64 machine in our CI uses
    # 0, 1, 16, 17.
    numa_nodes = {}
    for numa_index, numa_data in numa_nodes_info.items():
        numa_node, _ = NUMANode.objects.update_or_create(
            node=node,
            index=numa_index,
            defaults={"memory": numa_data.memory, "cores": numa_data.cores},
        )
        if update_deployment_resources and hugepages_size:
            NUMANodeHugepages.objects.update_or_create(
                numanode=numa_node,
                page_size=hugepages_size,
                defaults={"total": numa_data.hugepages},
            )
        numa_nodes[numa_index] = numa_node

    network_devices = update_node_network_information(node, data, numa_nodes)
    storage_devices = _update_node_physical_block_devices(
        node,
        resources,
        numa_nodes,
        custom_storage_config=data.get("storage-extra"),
    )

    update_node_devices(
        node, resources, numa_nodes, network_devices, storage_devices
    )

    if cpu_model:
        _, created = NodeMetadata.objects.update_or_create(
            node=node, key="cpu_model", defaults={"value": cpu_model}
        )

        # in the case of hardware sync for a cpu, a new one is added if this value has been updated
        if created and old_cpu_count > 0:
            _hardware_sync_cpu_notify(
                node, cpu_model, HARDWARE_SYNC_ACTIONS.ADDED
            )

    _process_system_information(node, resources.get("system", {}))
    _link_dpu(node)


def _process_machine_extra(node, extra):
    if extra is None:
        logger.warning(
            f"Machine configuration extra for `{node.system_id}` is None"
        )
        return

    if "platform" in extra:
        node.architecture = (
            f'{node.architecture.split("/", 2)[0]}/{extra["platform"]}'
        )

    node.save()


def _parse_memory(memory, numa_nodes):
    total_memory = memory.get("total", 0)
    # currently LXD only supports default size for hugepages
    hugepages_size = memory.get("hugepages_size")
    default_numa_node = {"numa_node": 0, "total": total_memory}

    # fill NUMA nodes info
    for memory_node in memory.get("nodes", [default_numa_node]):
        numa_node = numa_nodes[memory_node["numa_node"]]
        numa_node.memory = int(memory_node.get("total", 0) / 1024**2)
        numa_node.hugepages = memory_node.get("hugepages_total", 0)

    return int(total_memory / 1024**2), hugepages_size, numa_nodes


def _get_tags_from_block_info(block_info):
    """Return array of tags that will populate the `PhysicalBlockDevice`.

    Tags block devices for:
        rotary: Storage device with a spinning disk.
        ssd: Storage device with flash storage.
        removable: Storage device that can be easily removed like a USB
            flash drive.
        sata: Storage device that is connected over SATA.
    """
    tags = []
    if block_info["rpm"]:
        tags.append("rotary")
        tags.append("%srpm" % block_info["rpm"])
    elif not block_info.get("maas_multipath"):
        tags.append("ssd")
    if block_info.get("maas_multipath"):
        tags.append("multipath")
    if block_info["removable"]:
        tags.append("removable")
    if block_info["type"] == "sata":
        tags.append("sata")
    return tags


def _get_matching_block_device(block_devices, serial=None, id_path=None):
    """Return the matching block device based on `serial` or `id_path` from
    the provided list of `block_devices`."""
    if serial:
        for block_device in block_devices:
            if block_device.serial == serial:
                return block_device
    elif id_path:
        for block_device in block_devices:
            if block_device.id_path == id_path:
                return block_device
    return None


_MP_PATH_ID = {
    "fc": [re.compile(r"^(?P<port>\w+)-(?P<lun>lun-(0x)?[\da-fA-F]+)$")],
    "vmbus": [re.compile(r"^(?P<guid>\w+)-(?P<lun>lun-(0x)?[\da-fA-F]+)$")],
    "sas": [
        re.compile(
            r"^(?P<sas_addr>0x[\da-fA-F]+)-(?P<lun>lun-(0x)?[\da-fA-F]+)$"
        ),
        re.compile(
            r"^exp0x[\da-fA-F]+-phy(?P<phy_id>(0x)?[\da-fA-F]+)-(?P<lun>lun-(0x)?[\da-fA-F]+)$"
        ),
        re.compile(
            r"^phy(?P<phy_id>(0x)?[\da-fA-F]+)-(?P<lun>lun-(0x)?[\da-fA-F]+)$"
        ),
    ],
    "ip": [
        re.compile(
            r"^[\.\-\w:]+-iscsi-(?P<target>[\.\-\w:]+)-(?P<lun>lun-(0x)?[\da-fA-F]+)$"
        )
    ],
}

_DEV_PATH = re.compile(
    r"^(?P<bus>\w+)-(?P<bus_addr>[\da-fA-F:\.]+)-(?P<proto>\w+)-(?P<device>.*)$"
)


def _condense_luns(disks):
    """Condense disks by LUN.

    LUNs are used in multipath devices to identify a single storage source
    for the operating system to use. Multiple disks may still show up on the
    system pointing to the same source using different paths. MAAS should only
    model one storage source and ignore the paths. On deployment Curtin will
    detect multipath and properly set it up.
    """
    serial_lun_map = defaultdict(list)
    processed_disks = []
    for disk in disks:
        dev_match = _DEV_PATH.match(disk.get("device_path", ""))
        if dev_match is None or dev_match["proto"] == "usb":
            processed_disks.append(disk)
            continue

        proto = dev_match["proto"]
        device = dev_match["device"]

        if dev_match["bus"] == "pci" and "pci_address" not in disk:
            disk["pci_address"] = dev_match["bus_addr"]

        if disk.get("serial") and (rexp_list := _MP_PATH_ID.get(proto)):
            for r in rexp_list:
                if m := r.match(device):
                    serial_lun_map[(disk["serial"], m["lun"])].append(disk)
                    break
            else:
                processed_disks.append(disk)
        else:
            processed_disks.append(disk)

    for (serial, lun), paths in serial_lun_map.items():
        mpaths = sorted(paths, key=itemgetter("id"))
        condensed_disk = mpaths[0]
        if len(mpaths) > 1:
            condensed_disk["maas_multipath"] = True
        for path in mpaths[1:]:
            if not condensed_disk.get("device_id") and path.get("device_id"):
                condensed_disk["device_id"] = path["device_id"]
        processed_disks.append(condensed_disk)

    return sorted(processed_disks, key=itemgetter("id"))


def _hardware_sync_notify(
    ev_type, node, device_name, action, device_type=None
):
    """
    creates an event for hardware sync detectd updates
    """
    if not (node.enable_hw_sync and node.status == NODE_STATUS.DEPLOYED):
        return

    description = f"{device_name} was {action} on node {node.system_id}"
    if device_type:
        description = f"{device_type} " + description

    Event.objects.create_node_event(
        node.system_id,
        ev_type,
        event_action=action,
        event_description=description,
    )


def _hardware_sync_block_device_notify(node, block_device, action):
    _hardware_sync_notify(
        EVENT_TYPES.NODE_HARDWARE_SYNC_BLOCK_DEVICE,
        node,
        block_device.name,
        action,
        device_type="block device",
    )


def _hardware_sync_block_devices_notify(node, block_devices, action):
    [
        _hardware_sync_block_device_notify(node, bd, action)
        for bd in block_devices
    ]


def _hardware_sync_PCI_device_notify(node, pci_device, action):
    _hardware_sync_notify(
        EVENT_TYPES.NODE_HARDWARE_SYNC_PCI_DEVICE,
        node,
        pci_device.device_number,
        action,
        device_type="pci device",
    )


def _hardware_sync_USB_device_notify(node, usb_device, action):
    _hardware_sync_notify(
        EVENT_TYPES.NODE_HARDWARE_SYNC_USB_DEVICE,
        node,
        usb_device.device_number,
        action,
        device_type="usb device",
    )


def _hardware_sync_node_device_notify(node, device, action):
    if device.is_pcie:
        _hardware_sync_PCI_device_notify(node, device, action)
    else:
        _hardware_sync_USB_device_notify(node, device, action)


def _hardware_sync_node_devices_notify(node, devices, action):
    [
        _hardware_sync_node_device_notify(node, device, action)
        for device in devices
    ]


def _hardware_sync_cpu_notify(node, cpu_model, action):
    _hardware_sync_notify(
        EVENT_TYPES.NODE_HARDWARE_SYNC_CPU,
        node,
        cpu_model,
        action,
        device_type="cpu",
    )


def _hardware_sync_memory_notify(node, old_size):
    diff = node.memory - old_size
    _hardware_sync_notify(
        EVENT_TYPES.NODE_HARDWARE_SYNC_MEMORY,
        node,
        f"{human_readable_bytes(diff)} of memory",
        (
            HARDWARE_SYNC_ACTIONS.ADDED
            if diff > 0
            else HARDWARE_SYNC_ACTIONS.REMOVED
        ),
    )


def _update_node_physical_block_devices(
    node, data, numa_nodes, custom_storage_config=None
):
    # ensure the same node object is referenced so that updates to the node are
    # visible to objects related to the node config, such as block devices, that
    # access the node
    node.current_config.node = node

    custom_layout = None
    if custom_storage_config:
        # generating the layout also validates the config
        custom_layout = get_storage_layout(custom_storage_config)

    block_devices = {}
    # Skip storage configuration if set by the user.
    if node.skip_storage:
        # Turn off skip_storage now that the hook has been called.
        node.skip_storage = False
        node.save(update_fields=["skip_storage"])
        return block_devices

    previous_block_devices = list(
        PhysicalBlockDevice.objects.filter(
            node_config=node.current_config
        ).all()
    )
    for block_info in _condense_luns(data.get("storage", {}).get("disks", [])):
        # Skip the read-only devices or cdroms. We keep them in the output
        # for the user to view but they do not get an entry in the database.
        if block_info["read_only"] or block_info["type"] == "cdrom":
            continue
        name = block_info["id"]
        model = block_info.get("model", "")
        serial = block_info.get("serial", "")
        id_path = block_info.get("device_id", "")
        if id_path:
            id_path = f"/dev/disk/by-id/{id_path}"
        if not id_path or not serial:
            # Fallback to the dev path if device_path missing or there is
            # no serial number. (No serial number is a strong indicator that
            # this is a virtual disk, so it's unlikely that the device_path
            # would work.)
            id_path = "/dev/" + block_info.get("id")
        size = block_info.get("size")
        block_size = block_info.get("block_size")
        # If block_size is 0, set it to minimum default of 512.
        if not block_size:
            block_size = 512
        firmware_version = block_info.get("firmware_version")
        numa_index = block_info.get("numa_node")
        tags = _get_tags_from_block_info(block_info)

        # First check if there is an existing device with the same name.
        # If so, we need to rename it. Its name will be changed back later,
        # when we loop around to it.
        existing = PhysicalBlockDevice.objects.filter(
            node_config=node.current_config, name=name
        ).all()
        for device in existing:
            # Use the device ID to ensure a unique temporary name.
            device.name = "%s.%d" % (device.name, device.id)
            device.save(update_fields=["name"])

        block_device = _get_matching_block_device(
            previous_block_devices, serial, id_path
        )
        if block_device is not None:
            # Refresh, since it might have been temporarily renamed
            # above.
            block_device.refresh_from_db()
            # Already exists for the node. Keep the original object so the
            # ID doesn't change and if its set to the boot_disk that FK will
            # not need to be updated.
            previous_block_devices.remove(block_device)
            block_device.name = name
            block_device.model = model
            block_device.serial = serial
            block_device.id_path = id_path
            block_device.size = size
            block_device.block_size = block_size
            block_device.firmware_version = firmware_version
            block_device.tags = tags
            block_device.save()
            _hardware_sync_block_device_notify(
                node, block_device, HARDWARE_SYNC_ACTIONS.UPDATED
            )
        else:
            # MAAS doesn't allow disks smaller than 4MiB so skip them
            if size <= MIN_BLOCK_DEVICE_SIZE:
                continue
            # Skip loopback devices as they won't be available on next boot
            if id_path.startswith("/dev/loop"):
                continue

            # New block device. Create it on the node.
            block_device = PhysicalBlockDevice.objects.create(
                node_config=node.current_config,
                numa_node=numa_nodes[numa_index],
                name=name,
                id_path=id_path,
                size=size,
                block_size=block_size,
                tags=tags,
                model=model,
                serial=serial,
                firmware_version=firmware_version,
            )
            _hardware_sync_block_device_notify(
                node, block_device, HARDWARE_SYNC_ACTIONS.ADDED
            )

        if block_info.get("pci_address"):
            block_devices[block_info["pci_address"]] = block_device
        elif block_info.get("usb_address"):
            block_devices[block_info["usb_address"]] = block_device

    # Clear boot_disk if it's being removed.
    if node.boot_disk in previous_block_devices:
        node.boot_disk = None
        node.save(update_fields=["boot_disk"])

    # XXX ltrager 11-16-2017 - Don't regenerate ScriptResults on controllers.
    # Currently this is not needed saving us 1 database query. However, if
    # commissioning is ever enabled for controllers regeneration will need
    # to be allowed on controllers otherwise storage testing may break.
    if node.current_testing_script_set is not None and not node.is_controller:
        # LP: #1731353 - Regenerate ScriptResults before deleting
        # PhyscalBlockDevices. This creates a ScriptResult with proper
        # parameters for each storage device on the system. Storage devices no
        # long available will be deleted which causes a casade delete on their
        # assoicated ScriptResults.
        node.current_testing_script_set.regenerate(storage=True, network=False)

    # Delete all the previous block devices that are no longer present
    # on the commissioned node.
    delete_block_device_ids = [bd.id for bd in previous_block_devices]
    if delete_block_device_ids:
        PhysicalBlockDevice.objects.filter(
            id__in=delete_block_device_ids
        ).delete()
        _hardware_sync_block_devices_notify(
            node, previous_block_devices, HARDWARE_SYNC_ACTIONS.REMOVED
        )

    if node.is_commissioning():
        # Layouts need to be set last so removed disks aren't included in the
        # applied layout. Deployed Pods should not have a layout set as the
        # layout of the deployed system is unknown.
        if custom_layout:
            _try_apply_custom_storage_layout(custom_layout, node)
        else:
            node.set_default_storage_layout()

    return block_devices


def _try_apply_custom_storage_layout(layout, node):
    try:
        with transaction.atomic():
            apply_layout_to_machine(layout, node)
    except (IntegrityError, UnappliableLayout, ValidationError) as e:
        Event.objects.create_node_event(
            system_id=node,
            event_type=EVENT_TYPES.CONFIGURING_STORAGE,
            event_description=(f"Cannot apply custom layout: {e}"),
        )


def _process_lxd_environment(node, data):
    """Process the environment results from the `COMMISSIONING_OUTPUT_NAME` script."""
    # Verify the architecture is set correctly. This is how the architecture
    # gets set on controllers.
    cur_arch, cur_subarch = node.split_arch()
    arch, subarch = kernel_to_debian_architecture(
        data["kernel_architecture"]
    ).split("/")
    if cur_arch == arch and subarch == "generic" and cur_subarch != "generic":
        # keep the previous subarch since it's more specific
        subarch = cur_subarch
    node.architecture = f"{arch}/{subarch}"

    # When a machine is commissioning the OS will always be the ephemeral
    # environment. Controllers run the machine-resources binary directly
    # on the running machine and LXD Pods are getting this data from LXD
    # on the running machine. In those cases the information gathered below
    # is correct.
    if (
        not node.is_commissioning()
        and data.get("os_name")
        and data.get("os_version")
    ):
        # MAAS always stores OS information in lower case
        node.osystem = data["os_name"].lower()
        node.distro_series = data["os_version"].lower()
        # LXD always gives the OS version while MAAS stores Ubuntu releases
        # by release codename. e.g LXD gives 20.04 MAAS stores focal.
        if node.osystem == "ubuntu":
            release = get_release(node.distro_series)
            if release:
                node.distro_series = release["series"]


def process_lxd_results(node, output, exit_status):
    """Process the results of the `COMMISSIONING_OUTPUT_NAME` script.

    If `exit_status` is non-zero, this function returns without doing
    anything.
    """

    def log_failure_event(reason):
        Event.objects.create_node_event(
            system_id=node,
            event_type=EVENT_TYPES.SCRIPT_RESULT_ERROR,
            event_description=(
                f"Failed processing commissioning data: {reason}"
            ),
        )

    if exit_status != 0:
        logger.error(
            "%s: lxd script failed with status: "
            "%s." % (node.hostname, exit_status)
        )
        return
    assert isinstance(output, bytes)
    try:
        data = json.loads(output.decode("utf-8"))
    except ValueError as e:
        log_failure_event("invalid JSON data")
        raise ValueError(f"{e}: {output}")

    assert data.get("api_version") == "1.0", "Data not from LXD API 1.0!"

    # resources_network_usb and resources_disk_address are needed for mapping
    # between NodeDevices and Interfaces and BlockDevices. It is not included
    # on this list so MAAS can still use LXD < 4.9 as a VM host where this
    # information isn't necessary.
    required_extensions = {
        "resources",
        "resources_v2",
        "api_os",
        "resources_system",
        "resources_usb_pci",
    }
    missing_extensions = required_extensions - set(
        data.get("api_extensions", ())
    )
    assert (
        not missing_extensions
    ), f"Missing required LXD API extensions {sorted(missing_extensions)}"

    # If there is a change in the Rack controller configuration, we should
    # trigger configure-agent workflow execution, so MAAS Agent can consume
    # workflows from certain task queues.
    configuration_required = False
    if node.node_type in (
        NODE_TYPE.RACK_CONTROLLER,
        NODE_TYPE.REGION_AND_RACK_CONTROLLER,
    ):
        configuration_required = True
        old_vlans = set(
            node.current_config.interface_set.values_list("vlan", flat=True)
        )

    try:
        _process_lxd_environment(node, data["environment"])
        _process_lxd_resources(node, data)
        _process_machine_extra(node, data.get("machine-extra", None))
    except Exception as e:
        log_failure_event(str(e))
        raise

    node.save()

    if configuration_required:
        new_vlans = set(
            node.current_config.interface_set.values_list("vlan", flat=True)
        )
        if new_vlans != old_vlans:
            start_workflow(
                CONFIGURE_AGENT_WORKFLOW_NAME,
                param={
                    "system_id": node.system_id,
                    "task_queue": f"{node.system_id}@agent:main",
                },
                task_queue="region",
                retry_policy=RetryPolicy(maximum_attempts=1),
                execution_timeout=timedelta(seconds=120),
            )

    for pod in node.get_hosted_pods():
        pod.sync_hints_from_nodes()


def create_metadata_by_modalias(node, output: bytes, exit_status):
    """Tags the node based on discovered hardware, determined by modaliases.

    :param node: The node whose tags to set.
    :param output: Output from the LIST_MODALIASES_OUTPUT_NAME script
        (one modalias per line).
    :param exit_status: The exit status of the commissioning script.
    """
    if exit_status != 0:
        logger.error(
            "%s: modalias discovery script failed with status: %s"
            % (node.hostname, exit_status)
        )
        return
    assert isinstance(output, bytes)
    modaliases = output.decode("utf-8").splitlines()
    switch_tags_added, _ = retag_node_for_hardware_by_modalias(
        node, modaliases, SWITCH_TAG_NAME, SWITCH_HARDWARE
    )
    if switch_tags_added:
        dmi_data = get_dmi_data(modaliases)
        vendor, model = detect_switch_vendor_model(dmi_data)
        add_switch_vendor_model_tags(node, vendor, model)


def add_switch_vendor_model_tags(node, vendor, model):
    if vendor is not None:
        vendor_tag, _ = Tag.objects.get_or_create(name=vendor)
        node.tags.add(vendor_tag)
        logger.info(
            "%s: Added vendor tag '%s' for detected switch hardware."
            % (node.hostname, vendor)
        )
    if model is not None:
        kernel_opts = None
        if model == "wedge40":
            kernel_opts = "console=tty0 console=ttyS1,57600n8"
        elif model == "wedge100":
            kernel_opts = "console=tty0 console=ttyS4,57600n8"
        model_tag, _ = Tag.objects.get_or_create(
            name=model, defaults={"kernel_opts": kernel_opts}
        )
        node.tags.add(model_tag)
        logger.info(
            "%s: Added model tag '%s' for detected switch hardware."
            % (node.hostname, model)
        )


def update_node_fruid_metadata(node, output: bytes, exit_status):
    try:
        data = json.loads(output.decode("utf-8"))
    except json.decoder.JSONDecodeError:
        return

    # Attempt to map metadata provided by Facebook Wedge 100 FRUID API
    # to SNMP OID-like metadata describing physical nodes (see
    # http://www.ietf.org/rfc/rfc2737.txt).
    key_name_map = {
        "Product Name": NODE_METADATA.PHYSICAL_MODEL_NAME,
        "Product Serial Number": NODE_METADATA.PHYSICAL_SERIAL_NUM,
        "Product Version": NODE_METADATA.PHYSICAL_HARDWARE_REV,
        "System Manufacturer": NODE_METADATA.PHYSICAL_MFG_NAME,
    }
    info = data.get("Information", {})
    for fruid_key, node_key in key_name_map.items():
        if fruid_key in info:
            NodeMetadata.objects.update_or_create(
                node=node, key=node_key, defaults={"value": info[fruid_key]}
            )


def detect_switch_vendor_model(dmi_data):
    # This is based on:
    #    https://github.com/lool/sonic-snap/blob/master/common/id-switch
    vendor = None
    if "svnIntel" in dmi_data and "pnEPGSVR" in dmi_data:
        # XXX this seems like a suspicious assumption.
        vendor = "accton"
    elif "svnJoytech" in dmi_data and "pnWedge-AC-F20-001329" in dmi_data:
        vendor = "accton"
    elif "svnMellanoxTechnologiesLtd." in dmi_data:
        vendor = "mellanox"
    elif "svnTobefilledbyO.E.M." in dmi_data:
        if "rnPCOM-B632VG-ECC-FB-ACCTON-D" in dmi_data:
            vendor = "accton"
    # Now that we know the manufacturer, see if we can identify the model.
    model = None
    if vendor == "mellanox":
        if 'pn"MSN2100-CB2FO"' in dmi_data:
            model = "sn2100"
    elif vendor == "accton":
        if "pnEPGSVR" in dmi_data:
            model = "wedge40"
        elif "pnWedge-AC-F20-001329" in dmi_data:
            model = "wedge40"
        elif "pnTobefilledbyO.E.M." in dmi_data:
            if "rnPCOM-B632VG-ECC-FB-ACCTON-D" in dmi_data:
                model = "wedge100"
    return vendor, model


def get_dmi_data(modaliases):
    """Given the list of modaliases, returns the set of DMI data.

    An empty set will be returned if no DMI data could be found.

    The DMI data will be stripped of whitespace and have a prefix indicating
    what value they represent. Prefixes can be found in
    drivers/firmware/dmi-id.c in the Linux source:

        { "bvn", DMI_BIOS_VENDOR },
        { "bvr", DMI_BIOS_VERSION },
        { "bd",  DMI_BIOS_DATE },
        { "svn", DMI_SYS_VENDOR },
        { "pn",  DMI_PRODUCT_NAME },
        { "pvr", DMI_PRODUCT_VERSION },
        { "rvn", DMI_BOARD_VENDOR },
        { "rn",  DMI_BOARD_NAME },
        { "rvr", DMI_BOARD_VERSION },
        { "cvn", DMI_CHASSIS_VENDOR },
        { "ct",  DMI_CHASSIS_TYPE },
        { "cvr", DMI_CHASSIS_VERSION },

    The following is an example of what the set might look like:

        {'bd09/18/2014',
         'bvnAmericanMegatrendsInc.',
         'bvrMF1_2A04',
         'ct0',
         'cvnIntel',
         'cvrTobefilledbyO.E.M.',
         'pnEPGSVR',
         'pvrTobefilledbyO.E.M.',
         'rnTobefilledbyO.E.M.',
         'rvnTobefilledbyO.E.M.',
         'rvrTobefilledbyO.E.M.',
         'svnIntel'}

    :return: set
    """
    for modalias in modaliases:
        if modalias.startswith("dmi:"):
            return frozenset(data for data in modalias.split(":")[1:] if data)
    return frozenset()


def filter_modaliases(
    modaliases_discovered, modaliases=None, pci=None, usb=None
):
    """Determines which candidate modaliases match what was discovered.

    :param modaliases_discovered: The list of modaliases found on the node.
    :param modaliases: The candidate modaliases to match against. This
        parameter must be iterable. Wildcards are accepted.
    :param pci: A list of strings in the format <vendor>:<device>. May include
        wildcards.
    :param usb: A list of strings in the format <vendor>:<product>. May include
        wildcards.
    :return: The list of modaliases on the node matching the candidate(s).
    """
    patterns = []
    if modaliases is not None:
        patterns.extend(modaliases)
    if pci is not None:
        for pattern in pci:
            try:
                vendor, device = pattern.split(":")
            except ValueError:
                # Ignore malformed patterns.
                continue
            vendor = vendor.upper()
            device = device.upper()
            # v: vendor
            # d: device
            # sv: subvendor
            # sd: subdevice
            # bc: bus class
            # sc: bus subclass
            # i: interface
            patterns.append(
                "pci:v0000{vendor}d0000{device}sv*sd*bc*sc*i*".format(
                    vendor=vendor, device=device
                )
            )
    if usb is not None:
        for pattern in usb:
            try:
                vendor, product = pattern.split(":")
            except ValueError:
                # Ignore malformed patterns.
                continue
            vendor = vendor.upper()
            product = product.upper()
            # v: vendor
            # p: product
            # d: bcdDevice (device release number)
            # dc: device class
            # dsc: device subclass
            # dp: device protocol
            # ic: interface class
            # isc: interface subclass
            # ip: interface protocol
            patterns.append(
                "usb:v{vendor}p{product}d*dc*dsc*dp*ic*isc*ip*".format(
                    vendor=vendor, product=product
                )
            )
    matches = []
    for pattern in patterns:
        new_matches = fnmatch.filter(modaliases_discovered, pattern)
        for match in new_matches:
            if match not in matches:
                matches.append(match)
    return matches


def determine_hardware_matches(modaliases, hardware_descriptors):
    """Determines which hardware descriptors match the given modaliases.

    :param modaliases: List of modaliases found on the node.
    :param hardware_descriptors: Dictionary of information about each hardware
        component that can be discovered. This method requires a 'modaliases'
        entry to be present (with a list of modalias globs that might match
        the hardware on the node).
    :returns: A tuple whose first element contains the list of discovered
        hardware descriptors (with an added 'matches' element to specify which
        modaliases matched), and whose second element the list of any hardware
        that has been ruled out (so that the caller may remove those tags).
    """
    discovered_hardware = []
    ruled_out_hardware = []
    for candidate in hardware_descriptors:
        matches = filter_modaliases(modaliases, candidate["modaliases"])
        if matches:
            candidate = candidate.copy()
            candidate["matches"] = matches
            discovered_hardware.append(candidate)
        else:
            ruled_out_hardware.append(candidate)
    return discovered_hardware, ruled_out_hardware


def retag_node_for_hardware_by_modalias(
    node, modaliases, parent_tag_name, hardware_descriptors
):
    """Adds or removes tags on a node based on its modaliases.

    Returns the Tag model objects added and removed, respectively.

    :param node: The node whose tags to modify.
    :param modaliases: The modaliases discovered on the node.
    :param parent_tag_name: The tag name for the hardware type given in the
        `hardware_descriptors` list. For example, if switch ASICs are being
        discovered, the string "switch" might be appropriate. Then, if switch
        hardware is found, the node will be tagged with the matching
        descriptors' tag(s), *and* with the more general "switch" tag.
    :param hardware_descriptors: A list of hardware descriptor dictionaries.

    :returns: tuple of (tags_added, tags_removed)
    """
    # Don't unconditionally create the tag. Check for it with a filter first.
    parent_tag = get_one(Tag.objects.filter(name=parent_tag_name))
    tags_added = set()
    tags_removed = set()
    discovered_hardware, ruled_out_hardware = determine_hardware_matches(
        modaliases, hardware_descriptors
    )
    if discovered_hardware:
        if parent_tag is None:
            # Create the tag "just in time" if we found matching hardware, and
            # we hadn't created the tag yet.
            parent_tag = Tag(name=parent_tag_name)
            parent_tag.save()
        node.tags.add(parent_tag)
        tags_added.add(parent_tag)
        logger.info(
            "%s: Added tag '%s' for detected hardware type."
            % (node.hostname, parent_tag_name)
        )
        for descriptor in discovered_hardware:
            tag = descriptor["tag"]
            comment = descriptor["comment"]
            matches = descriptor["matches"]
            hw_tag, _ = Tag.objects.get_or_create(
                name=tag, defaults={"comment": comment}
            )
            node.tags.add(hw_tag)
            tags_added.add(hw_tag)
            logger.info(
                "%s: Added tag '%s' for detected hardware: %s "
                "(Matched: %s)." % (node.hostname, tag, comment, matches)
            )
    else:
        if parent_tag is not None:
            node.tags.remove(parent_tag)
            tags_removed.add(parent_tag)
            logger.info(
                "%s: Removed tag '%s'; machine does not match hardware "
                "description." % (node.hostname, parent_tag_name)
            )
    for descriptor in ruled_out_hardware:
        tag_name = descriptor["tag"]
        existing_tag = get_one(node.tags.filter(name=tag_name))
        if existing_tag is not None:
            node.tags.remove(existing_tag)
            tags_removed.add(existing_tag)
            logger.info(
                "%s: Removed tag '%s'; hardware is missing."
                % (node.hostname, tag_name)
            )
    return tags_added, tags_removed


def _link_dpu(node):
    """Create a parent-child relation between nodes.

    E.g. Data Processing Unit (DPU) itself is identified as a Node in MAAS,
    but it is a dependant resource. Linking is achieved through setting
    parent_id for the dependant node.
    """

    system_families = ("BlueField",)
    vendor_ids = ("15b3",)  # Mellanox Technologies

    # find DPU related NodeDevice VPD data for the Node, this data will be used
    # to find other Nodes that have the same NodeDevices discovered.
    matching_node_devices = NodeDeviceVPD.objects.filter(
        node_device__in=NodeDevice.objects.filter(
            node_config=node.current_config, vendor_id__in=vendor_ids
        ),
        key="SN",
    ).values_list("node_device__product_id", "value")

    if not matching_node_devices:
        return

    query = Q(
        current_config__nodedevice__nodedevicevpd__key="SN",
        current_config__nodedevice__vendor_id__in=vendor_ids,
    ) & functools.reduce(
        # (product_id = % AND value = %) OR (product_id = % AND value = %)
        operator.or_,
        (
            Q(
                current_config__nodedevice__product_id=product_id,
                current_config__nodedevice__nodedevicevpd__value=sn,
            )
            for product_id, sn in matching_node_devices
        ),
    )

    if node.get_metadata().get("system_family") not in system_families:
        # this node can only be a parent node
        query &= Q(
            nodemetadata__key="system_family",
            nodemetadata__value__in=system_families,
        )
        Node.objects.filter(query).exclude(id=node.id).update(parent=node)
    else:
        # this is a child node, thus we look for a node that can be a parent one
        query &= ~Q(
            nodemetadata__key="system_family",
            nodemetadata__value__in=system_families,
        )
        try:
            parent = Node.objects.get(query)
        except Node.MultipleObjectsReturned:
            logger.warning(
                f"Multiple possible parent nodes for the node {node}"
            )
        except Node.DoesNotExist:
            pass
        else:
            node.parent = parent
            node.save()


# Register the post processing hooks.
NODE_INFO_SCRIPTS[GET_FRUID_DATA_OUTPUT_NAME][
    "hook"
] = update_node_fruid_metadata
NODE_INFO_SCRIPTS[LIST_MODALIASES_OUTPUT_NAME][
    "hook"
] = create_metadata_by_modalias
NODE_INFO_SCRIPTS[COMMISSIONING_OUTPUT_NAME]["hook"] = process_lxd_results
NODE_INFO_SCRIPTS[KERNEL_CMDLINE_OUTPUT_NAME]["hook"] = update_boot_interface
