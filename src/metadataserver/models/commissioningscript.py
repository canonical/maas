# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Custom commissioning scripts, and their database backing."""


__all__ = [
    'NODE_INFO_SCRIPTS',
    'CommissioningScript',
    ]

import json
import logging
import math
import re

from django.db.models import (
    CharField,
    Model,
)
from lxml import etree
from maasserver.models import Fabric
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.models.interface import PhysicalInterface
from maasserver.models.physicalblockdevice import PhysicalBlockDevice
from maasserver.models.tag import Tag
from metadataserver import DefaultMeta
from metadataserver.fields import BinaryField
from provisioningserver.refresh.node_info_scripts import (
    LSHW_OUTPUT_NAME,
    NODE_INFO_SCRIPTS,
)
from provisioningserver.utils.ipaddr import parse_ip_addr


logger = logging.getLogger(__name__)


# Some machines have a <size> element in their memory <node> with the total
# amount of memory, and other machines declare the size of the memory in
# individual memory banks. This expression is mean to cope with both.
_xpath_memory_bytes = """\
    sum(//node[@id='memory']/size[@units='bytes'] |
        //node[starts-with(@id, 'memory:')]
            /node[starts-with(@id, 'bank:')]/size[@units='bytes'])
    div 1024 div 1024
"""


def _create_default_physical_interface(node, ifname, mac):
    """Assigns the specified interface to the specified Node.

    Creates or updates a PhysicalInterface that corresponds to the given MAC.

    :param node: Node model object
    :param ifname: the interface name (for example, 'eth0')
    :param mac: the Interface to update and associate
    """
    # We don't yet have enough information to put this newly-created Interface
    # into the proper Fabric/VLAN. (We'll do this on a "best effort" basis
    # later, if we are able to determine that the interface is on a particular
    # subnet due to a DHCP reply during commissioning.)
    fabric = Fabric.objects.get_default_fabric()
    vlan = fabric.get_default_vlan()
    interface = PhysicalInterface.objects.create(
        mac_address=mac, name=ifname, node=node, vlan=vlan)

    return interface


def update_node_network_information(node, output, exit_status):
    """Updates the network interfaces from the results of `IPADDR_SCRIPT`.

    Creates and deletes an Interface according to what we currently know about
    this node's hardware.

    If `exit_status` is non-zero, this function returns without doing
    anything.

    """
    assert isinstance(output, bytes)
    if exit_status != 0:
        return

    # Skip network configuration if set by the user.
    if node.skip_networking:
        return

    # Get the MAC addresses of all connected interfaces.
    ip_addr_info = parse_ip_addr(output)
    current_interfaces = set()

    for link in ip_addr_info.values():
        link_mac = link.get('mac')
        # Ignore loopback interfaces.
        if link_mac is None:
            continue
        else:
            ifname = link['name']
            try:
                interface = PhysicalInterface.objects.get(
                    mac_address=link_mac)
                if interface.node is not None and interface.node != node:
                    logger.warning(
                        "Interface with MAC %s moved from node %s to %s. "
                        "(The existing interface will be deleted.)" %
                        (interface.mac_address, interface.node.fqdn,
                         node.fqdn))
                    interface.delete()
                    interface = _create_default_physical_interface(
                        node, ifname, link_mac)
                else:
                    # Interface already exists on this Node, so just update
                    # the name.
                    interface.name = ifname
                    interface.save()
            except PhysicalInterface.DoesNotExist:
                interface = _create_default_physical_interface(
                    node, ifname, link_mac)

            current_interfaces.add(interface)
            ips = link.get('inet', []) + link.get('inet6', [])
            interface.update_ip_addresses(ips)

    for iface in PhysicalInterface.objects.filter(node=node):
        if iface not in current_interfaces:
            iface.delete()


def update_node_network_interface_tags(node, output, exit_status):
    """Updates the network interfaces tags from the results of `SRIOV_SCRIPT`.

    Creates and deletes a tag on an Interface according to what we currently
    know about this node's hardware.

    If `exit_status` is non-zero, this function returns without doing
    anything.

    """
    assert isinstance(output, bytes)
    if exit_status != 0:
        return

    decoded_output = output.decode("ascii")
    for iface in PhysicalInterface.objects.filter(node=node):
        if str(iface.mac_address) in decoded_output:
            if 'sriov' not in str(iface.tags):
                iface.tags.append("sriov")
                iface.save()


def set_switch_tags(node, output, exit_status):
    """Process the results of `SWITCH_DISCOVERY_SCRIPT`.

    This adds or removes the *switch* tag from the node, depending on
    whether a virtualization type is listed.

    If `exit_status` is non-zero, this function returns without doing
    anything.
    """
    assert isinstance(output, bytes)
    if exit_status != 0:
        return
    decoded_output = output.decode('ascii').strip()
    switch_tag, _ = Tag.objects.get_or_create(name='switch')
    if 'none' in decoded_output:
        node.tags.remove(switch_tag)
    elif decoded_output == '':
        logger.warning(
            "No switch type reported in SWITCH_DISCOVERY_SCRIPT output "
            "for node %s", node.system_id)
    else:
        node.tags.add(switch_tag)
        # Since we have discovered this to be a switch, we add a tag
        # based on the returned output, which is the switch model.
        model_tag, _ = Tag.objects.get_or_create(name=decoded_output)
        node.tags.add(model_tag)


def update_hardware_details(node, output, exit_status):
    """Process the results of `LSHW_SCRIPT`.

    Updates `node.cpu_count`, `node.memory`, and `node.storage`
    fields, and also evaluates all tag expressions against the given
    ``lshw`` XML.

    If `exit_status` is non-zero, this function returns without doing
    anything.
    """
    assert isinstance(output, bytes)
    if exit_status != 0:
        return
    try:
        doc = etree.XML(output)
    except etree.XMLSyntaxError:
        logger.exception("Invalid lshw data.")
    else:
        # Same document, many queries: use XPathEvaluator.
        evaluator = etree.XPathEvaluator(doc)
        memory = evaluator(_xpath_memory_bytes)
        if not memory or math.isnan(memory):
            memory = 0
        node.memory = memory
        node.save()


def parse_cpuinfo(node, output, exit_status):
    """Parse the output of /proc/cpuinfo."""
    assert isinstance(output, bytes)
    if exit_status != 0:
        return
    output = output.decode('ascii')
    cpu_count = len(
        re.findall(
            '^(?P<CPU>\d+),(?P<CORE>\d+),(?P<SOCKET>\d+)$',
            output, re.MULTILINE))
    node.cpu_count = cpu_count
    node.save()


def set_virtual_tag(node, output, exit_status):
    """Process the results of `VIRTUALITY_SCRIPT`.

    This adds or removes the *virtual* tag from the node, depending on
    whether a virtualization type is listed.

    If `exit_status` is non-zero, this function returns without doing
    anything.
    """
    assert isinstance(output, bytes)
    if exit_status != 0:
        return
    decoded_output = output.decode('ascii').strip()
    tag, _ = Tag.objects.get_or_create(name='virtual')
    if 'none' in decoded_output:
        node.tags.remove(tag)
    elif decoded_output == '':
        logger.warning(
            "No virtual type reported in VIRTUALITY_SCRIPT output for node "
            "%s", node.system_id)
    else:
        node.tags.add(tag)


_xpath_routers = "/lldp//id[@type='mac']/text()"


def extract_router_mac_addresses(raw_content):
    """Extract the routers' MAC Addresses from raw LLDP information."""
    if not raw_content:
        return None
    assert isinstance(raw_content, bytes)
    parser = etree.XMLParser()
    doc = etree.XML(raw_content.strip(), parser)
    return doc.xpath(_xpath_routers)


def get_tags_from_block_info(block_info):
    """Return array of tags that will populate the `PhysicalBlockDevice`.

    Tags block devices for:
        rotary: Storage device with a spinning disk.
        ssd: Storage device with flash storage.
        removable: Storage device that can be easily removed like a USB
            flash drive.
        sata: Storage device that is connected over SATA.
    """
    tags = []
    if block_info["ROTA"] == "1":
        tags.append("rotary")
    else:
        tags.append("ssd")
    if block_info["RM"] == "1":
        tags.append("removable")
    if "SATA" in block_info and block_info["SATA"] == "1":
        tags.append("sata")
    if "RPM" in block_info and block_info["RPM"] != "0":
        tags.append("%srpm" % block_info["RPM"])
    return tags


def get_matching_block_device(block_devices, serial=None, id_path=None):
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


def update_node_physical_block_devices(node, output, exit_status):
    """Process the results of `gather_physical_block_devices`.

    This updates the physical block devices that are attached to a node.

    If `exit_status` is non-zero, this function returns without doing
    anything.
    """
    assert isinstance(output, bytes)
    if exit_status != 0:
        return

    # Skip storage configuration if set by the user.
    if node.skip_storage:
        return

    try:
        blockdevs = json.loads(output.decode("ascii"))
    except ValueError as e:
        raise ValueError(e.message + ': ' + output)
    previous_block_devices = list(
        PhysicalBlockDevice.objects.filter(node=node).all())
    for block_info in blockdevs:
        # Skip the read-only devices. We keep them in the output for
        # the user to view but they do not get an entry in the database.
        if block_info["RO"] == "1":
            continue
        name = block_info["NAME"]
        model = block_info.get("MODEL", "")
        serial = block_info.get("SERIAL", "")
        id_path = block_info.get("ID_PATH", "")
        if not id_path or not serial:
            # Fallback to the dev path if id_path missing or there is no
            # serial number. (No serial number is a strong indicator that this
            # is a virtual disk, so it's unlikely that the ID_PATH would work.)
            id_path = block_info["PATH"]
        size = int(block_info["SIZE"])
        block_size = int(block_info["BLOCK_SIZE"])
        tags = get_tags_from_block_info(block_info)
        block_device = get_matching_block_device(
            previous_block_devices, serial, id_path)
        if block_device is not None:
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
            block_device.tags = tags
            block_device.save()
        else:
            # MAAS doesn't allow disks smaller than 4MiB so skip them
            if size <= MIN_BLOCK_DEVICE_SIZE:
                continue
            # Skip loopback devices as they won't be available on next boot
            if id_path.startswith('/dev/loop'):
                continue

            # First check if there is an existing device with the same name.
            # If so, we need to rename it. Its name will be changed back later,
            # when we loop around to it.
            existing = PhysicalBlockDevice.objects.filter(
                node=node, name=name).all()
            for device in existing:
                # Use the device ID to ensure a unique temporary name.
                device.name = "%s.%d" % (device.name, device.id)
                device.save()
            # New block device. Create it on the node.
            PhysicalBlockDevice.objects.create(
                node=node,
                name=name,
                id_path=id_path,
                size=size,
                block_size=block_size,
                tags=tags,
                model=model,
                serial=serial,
                )

    # Clear boot_disk if it is being removed.
    boot_disk = node.boot_disk
    if boot_disk is not None and boot_disk in previous_block_devices:
        boot_disk = None
    if node.boot_disk != boot_disk:
        node.boot_disk = boot_disk
        node.save()

    # Delete all the previous block devices that are no longer present
    # on the commissioned node.
    delete_block_device_ids = [
        bd.id
        for bd in previous_block_devices
    ]
    if len(delete_block_device_ids) > 0:
        PhysicalBlockDevice.objects.filter(
            id__in=delete_block_device_ids).delete()


# Register the post processing hooks.
NODE_INFO_SCRIPTS[LSHW_OUTPUT_NAME]['hook'] = update_hardware_details
NODE_INFO_SCRIPTS['00-maas-01-cpuinfo']['hook'] = parse_cpuinfo
NODE_INFO_SCRIPTS['00-maas-02-virtuality']['hook'] = set_virtual_tag
NODE_INFO_SCRIPTS['00-maas-02-switch-discovery']['hook'] = set_switch_tags
NODE_INFO_SCRIPTS['00-maas-07-block-devices']['hook'] = (
    update_node_physical_block_devices)
NODE_INFO_SCRIPTS['99-maas-03-network-interfaces']['hook'] = (
    update_node_network_information)
NODE_INFO_SCRIPTS['99-maas-04-network-interfaces-with-sriov']['hook'] = (
    update_node_network_interface_tags)


class CommissioningScript(Model):
    """User-provided commissioning script.

    Actually a commissioning "script" could be a binary, e.g. because a
    hardware vendor supplied an update in the form of a binary executable.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    name = CharField(max_length=255, null=False, editable=True, unique=True)
    content = BinaryField(null=False)
