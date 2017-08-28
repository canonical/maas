# Copyright 2012-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Builtin script hooks, run upon receipt of ScriptResult"""

__all__ = [
    'NODE_INFO_SCRIPTS',
    'update_node_network_information',
    ]

import fnmatch
import json
import logging
import math
import re

from lxml import etree
from maasserver.models import Fabric
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.models.interface import (
    Interface,
    PhysicalInterface,
)
from maasserver.models.physicalblockdevice import PhysicalBlockDevice
from maasserver.models.switch import Switch
from maasserver.models.tag import Tag
from maasserver.utils.orm import get_one
from provisioningserver.refresh.node_info_scripts import (
    IPADDR_OUTPUT_NAME,
    LIST_MODALIASES_OUTPUT_NAME,
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

SWITCH_TAG_NAME = "switch"
SWITCH_HARDWARE = [
    # Seen on Facebook Wedge 40 switch:
    #     pci:v000014E4d0000B850sv000014E4sd0000B850bc02sc00i00
    #     (Broadcom Trident II ASIC)
    {
        'modaliases': [
            'pci:v000014E4d0000B850sv*sd*bc*sc*i*',
        ],
        'tag': 'bcm-trident2-asic',
        'comment':
            'Broadcom High-Capacity StrataXGS "Trident II" '
            'Ethernet Switch ASIC'
    },
    # Seen on Facebook Wedge 100 switch:
    #     pci:v000014E4d0000B960sv000014E4sd0000B960bc02sc00i00
    #     (Broadcom Tomahawk ASIC)
    {
        'modaliases': [
            'pci:v000014E4d0000B960sv*sd*bc*sc*i*',
        ],
        'tag': 'bcm-tomahawk-asic',
        'comment':
            'Broadcom High-Density 25/100 StrataXGS "Tomahawk" '
            'Ethernet Switch ASIC'
    },
]


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
    if exit_status != 0:
        logger.error(
            "%s: node network information script failed with status: %s." % (
                node.hostname, exit_status))
        return
    assert isinstance(output, bytes)

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
                    if interface.name != ifname:
                        interface.name = ifname
                        interface.save(update_fields=['name', 'updated'])
            except PhysicalInterface.DoesNotExist:
                interface = _create_default_physical_interface(
                    node, ifname, link_mac)

            current_interfaces.add(interface)
            ips = link.get('inet', []) + link.get('inet6', [])
            interface.update_ip_addresses(ips)
            if 'NO-CARRIER' in link.get('flags', []):
                # This interface is now disconnected.
                if interface.vlan is not None:
                    interface.vlan = None
                    interface.save(update_fields=['vlan', 'updated'])

    for iface in Interface.objects.filter(node=node):
        if iface not in current_interfaces:
            iface.delete()


def update_node_network_interface_tags(node, output, exit_status):
    """Updates the network interfaces tags from the results of `SRIOV_SCRIPT`.

    Creates and deletes a tag on an Interface according to what we currently
    know about this node's hardware.

    If `exit_status` is non-zero, this function returns without doing
    anything.

    """
    if exit_status != 0:
        logger.error("%s: SR-IOV detection script failed with status: %s." % (
            node.hostname, exit_status))
        return
    assert isinstance(output, bytes)

    decoded_output = output.decode("ascii")
    for iface in PhysicalInterface.objects.filter(node=node):
        if str(iface.mac_address) in decoded_output:
            if 'sriov' not in str(iface.tags):
                iface.tags.append("sriov")
                iface.save()


def update_hardware_details(node, output, exit_status):
    """Process the results of `LSHW_SCRIPT`.

    Updates `node.cpu_count`, `node.memory`, and `node.storage`
    fields, and also evaluates all tag expressions against the given
    ``lshw`` XML.

    If `exit_status` is non-zero, this function returns without doing
    anything.
    """
    if exit_status != 0:
        logger.error(
            "%s: lshw script failed with status: %s." % (
                node.hostname, exit_status))
        return
    assert isinstance(output, bytes)
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
    if exit_status != 0:
        logger.error(
            "%s: cpuinfo script failed with status: %s." % (
                node.hostname, exit_status))
        return
    assert isinstance(output, bytes)
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
    if exit_status != 0:
        logger.error(
            "%s: virtual machine detection script failed with status: %s." % (
                node.hostname, exit_status))
        return
    assert isinstance(output, bytes)
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
    if exit_status != 0:
        logger.error(
            "%s: physical block device detection script failed with status: "
            "%s." % (node.hostname, exit_status))
        return
    assert isinstance(output, bytes)

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


def create_metadata_by_modalias(node, output: bytes, exit_status):
    """Tags the node based on discovered hardware, determined by modaliases.
    If nodes are detected as supported switches, they also get Switch objects.

    :param node: The node whose tags to set.
    :param output: Output from the LIST_MODALIASES_SCRIPT
        (one modalias per line).
    :param exit_status: The exit status of the commissioning script.
    """
    if exit_status != 0:
        logger.error("%s: modalias discovery script failed with status: %s" % (
            node.hostname, exit_status))
        return
    assert isinstance(output, bytes)
    modaliases = output.decode('utf-8').splitlines()
    switch_tags_added, _ = retag_node_for_hardware_by_modalias(
        node, modaliases, SWITCH_TAG_NAME, SWITCH_HARDWARE)
    if len(switch_tags_added) > 0:
        dmi_data = get_dmi_data(modaliases)
        vendor, model = detect_switch_vendor_model(dmi_data)
        add_switch_vendor_model_tags(node, vendor, model)
        add_switch(node, vendor, model)


def add_switch_vendor_model_tags(node, vendor, model):
    if vendor is not None:
        vendor_tag, _ = Tag.objects.get_or_create(name=vendor)
        node.tags.add(vendor_tag)
        logger.info(
            "%s: Added vendor tag '%s' for detected switch hardware." % (
                node.hostname, vendor))
    if model is not None:
        kernel_opts = None
        if model == "wedge40":
            kernel_opts = "console=tty0 console=ttyS1,57600n8"
        elif model == "wedge100":
            kernel_opts = "console=tty0 console=ttyS4,57600n8"
        model_tag, _ = Tag.objects.get_or_create(
            name=model, defaults={
                'kernel_opts': kernel_opts
            })
        node.tags.add(model_tag)
        logger.info(
            "%s: Added model tag '%s' for detected switch hardware." % (
                node.hostname, model))


def add_switch(node, vendor, model):
    """Add Switch object representing the switch hardware."""
    switch, created = Switch.objects.get_or_create(node=node)
    logger.info("%s: detected as a switch." % node.hostname)
    return switch


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
        if 'pnEPGSVR' in dmi_data:
            model = "wedge40"
        elif 'pnWedge-AC-F20-001329' in dmi_data:
            model = "wedge40"
        elif 'pnTobefilledbyO.E.M.' in dmi_data:
            if 'rnPCOM-B632VG-ECC-FB-ACCTON-D' in dmi_data:
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
            return frozenset(
                [data for data in modalias.split(':')[1:] if len(data) > 0])
    return frozenset()


def filter_modaliases(modaliases_discovered, candidates):
    """Determines which candidate modaliases match what was discovered.

    :param modaliases_discovered: The list of modaliases found on the node.
    :param candidates: The candidate modaliases to match against. This
        parameter must be iterable. Wildcards are accepted.
    :return: The list of modaliases on the node matching the candidate(s).
    """
    matches = []
    for candidate in candidates:
        new_matches = fnmatch.filter(
            modaliases_discovered, candidate)
        matches.extend(new_matches)
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
        matches = filter_modaliases(modaliases, candidate['modaliases'])
        if len(matches) > 0:
            candidate = candidate.copy()
            candidate['matches'] = matches
            discovered_hardware.append(candidate)
        else:
            ruled_out_hardware.append(candidate)
    return discovered_hardware, ruled_out_hardware


def retag_node_for_hardware_by_modalias(
        node, modaliases, parent_tag_name, hardware_descriptors):
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
        modaliases, hardware_descriptors)
    if len(discovered_hardware) > 0:
        if parent_tag is None:
            # Create the tag "just in time" if we found matching hardware, and
            # we hadn't created the tag yet.
            parent_tag = Tag(name=parent_tag_name)
            parent_tag.save()
        node.tags.add(parent_tag)
        tags_added.add(parent_tag)
        logger.info(
            "%s: Added tag '%s' for detected hardware type." % (
                node.hostname, parent_tag_name))
        for descriptor in discovered_hardware:
            tag = descriptor['tag']
            comment = descriptor['comment']
            matches = descriptor['matches']
            hw_tag, _ = Tag.objects.get_or_create(name=tag, defaults={
                'comment': comment
            })
            node.tags.add(hw_tag)
            tags_added.add(hw_tag)
            logger.info(
                "%s: Added tag '%s' for detected hardware: %s "
                "(Matched: %s)." % (node.hostname, tag, comment, matches))
    else:
        if parent_tag is not None:
            node.tags.remove(parent_tag)
            tags_removed.add(parent_tag)
            logger.info(
                "%s: Removed tag '%s'; machine does not match hardware "
                "description." % (node.hostname, parent_tag_name))
    for descriptor in ruled_out_hardware:
        tag_name = descriptor['tag']
        existing_tag = get_one(node.tags.filter(name=tag_name))
        if existing_tag is not None:
            node.tags.remove(existing_tag)
            tags_removed.add(existing_tag)
            logger.info(
                "%s: Removed tag '%s'; hardware is missing." % (
                    node.hostname, tag_name))
    return tags_added, tags_removed


# Register the post processing hooks.
NODE_INFO_SCRIPTS[LSHW_OUTPUT_NAME]['hook'] = update_hardware_details
NODE_INFO_SCRIPTS['00-maas-01-cpuinfo']['hook'] = parse_cpuinfo
NODE_INFO_SCRIPTS['00-maas-02-virtuality']['hook'] = set_virtual_tag
NODE_INFO_SCRIPTS['00-maas-07-block-devices']['hook'] = (
    update_node_physical_block_devices)
NODE_INFO_SCRIPTS[IPADDR_OUTPUT_NAME]['hook'] = (
    update_node_network_information)
NODE_INFO_SCRIPTS['99-maas-04-network-interfaces-with-sriov']['hook'] = (
    update_node_network_interface_tags)
NODE_INFO_SCRIPTS[LIST_MODALIASES_OUTPUT_NAME]['hook'] = (
    create_metadata_by_modalias)
