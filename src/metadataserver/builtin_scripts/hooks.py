# Copyright 2012-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Builtin script hooks, run upon receipt of ScriptResult"""

__all__ = [
    'NODE_INFO_SCRIPTS',
    'parse_lshw_nic_info',
    'update_node_network_information',
    ]

import fnmatch
import json
import logging
import math
import re

from lxml import etree
from maasserver.enum import NODE_METADATA
from maasserver.models import Fabric
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.models.interface import (
    Interface,
    PhysicalInterface,
)
from maasserver.models.nodemetadata import NodeMetadata
from maasserver.models.physicalblockdevice import PhysicalBlockDevice
from maasserver.models.switch import Switch
from maasserver.models.tag import Tag
from maasserver.utils.orm import get_one
from metadataserver.enum import SCRIPT_STATUS
from provisioningserver.refresh.node_info_scripts import (
    BLOCK_DEVICES_OUTPUT_NAME,
    CPUINFO_OUTPUT_NAME,
    GET_FRUID_DATA_OUTPUT_NAME,
    IPADDR_OUTPUT_NAME,
    LIST_MODALIASES_OUTPUT_NAME,
    LSHW_OUTPUT_NAME,
    NODE_INFO_SCRIPTS,
    SRIOV_OUTPUT_NAME,
    VIRTUALITY_OUTPUT_NAME,
)
from provisioningserver.utils.ipaddr import parse_ip_addr


logger = logging.getLogger(__name__)


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
SWITCH_OPENBMC_MAC = "02:00:00:00:00:02"


def _create_default_physical_interface(node, ifname, mac, **kwargs):
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
        mac_address=mac, name=ifname, node=node, vlan=vlan, **kwargs)

    return interface


def parse_lshw_nic_info(node):
    """Parse lshw output for additional NIC information."""
    nics = {}
    script_set = node.current_commissioning_script_set
    # Should never happen but just incase...
    if not script_set:
        return nics
    script_result = script_set.find_script_result(script_name=LSHW_OUTPUT_NAME)
    if not script_result or script_result.status != SCRIPT_STATUS.PASSED:
        logger.error(
            '%s: Unable to discover extended NIC information due to missing '
            'passed output from %s' % (node.hostname, LSHW_OUTPUT_NAME))
        return nics

    try:
        doc = etree.XML(script_result.stdout)
    except etree.XMLSyntaxError:
        logger.exception(
            '%s: Unable to discover extended NIC information due to %s output '
            'containing invalid XML' % (node.hostname, LSHW_OUTPUT_NAME))
        return nics

    evaluator = etree.XPathEvaluator(doc)

    for e in evaluator('//node[@class="network"]'):
        mac = e.find('serial')
        if mac is None:
            continue
        else:
            mac = mac.text
        # Bridged devices may appear multiple times but only one element
        # may contain firmware information.
        if mac not in nics:
            nics[mac] = {}
        for field in ['vendor', 'product']:
            value = get_xml_field_value(e.xpath, '//%s/text()' % field)
            if value:
                nics[mac][field] = value
        firmware_version = get_xml_field_value(
            e.xpath, "//configuration/setting[@id='firmware']/@value")
        if firmware_version:
            nics[mac]['firmware_version'] = firmware_version
    return nics


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
    extended_nic_info = parse_lshw_nic_info(node)

    for link in ip_addr_info.values():
        link_mac = link.get('mac')
        # Ignore loopback interfaces.
        if link_mac is None:
            continue
        elif link_mac == SWITCH_OPENBMC_MAC:
            # Ignore OpenBMC interfaces on switches which all share the same,
            # hard-coded OpenBMC MAC address.
            continue
        else:
            ifname = link['name']
            extra_info = extended_nic_info.get(link_mac, {})
            try:
                interface = PhysicalInterface.objects.get(
                    mac_address=link_mac)
                update_fields = []
                if interface.node is not None and interface.node != node:
                    logger.warning(
                        "Interface with MAC %s moved from node %s to %s. "
                        "(The existing interface will be deleted.)" %
                        (interface.mac_address, interface.node.fqdn,
                         node.fqdn))
                    interface.delete()
                    interface = _create_default_physical_interface(
                        node, ifname, link_mac, **extra_info)
                else:
                    # Interface already exists on this Node, so just update
                    # the name and NIC info.
                    update_fields = []
                    if interface.name != ifname:
                        interface.name = ifname
                        update_fields.append('name')
                    for k, v in extra_info.items():
                        if getattr(interface, k, v) != v:
                            setattr(interface, k, v)
                            update_fields.append(k)
                    if update_fields:
                        interface.save(
                            update_fields=['updated', *update_fields])
            except PhysicalInterface.DoesNotExist:
                interface = _create_default_physical_interface(
                    node, ifname, link_mac, **extra_info)

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


def get_xml_field_value(evaluator, expression):
    """Return an XML field or None if its not found."""
    field = evaluator(expression)
    # Supermicro uses 0123456789 as a place holder.
    if (isinstance(field, list) and len(field) > 0 and
            '0123456789' not in field[0].lower()):
        return field[0]
    else:
        return None


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

        # Some machines have a <size> element in their memory <node> with the
        # total amount of memory, and other machines declare the size of the
        # memory in individual memory banks. This expression is mean to cope
        # with both.
        memory = evaluator("""\
            sum(//node[@id='memory']/size[@units='bytes'] |
            //node[starts-with(@id, 'memory:')]
                /node[starts-with(@id, 'bank:')]/size[@units='bytes'])
            div 1024 div 1024
        """)
        if not memory or math.isnan(memory):
            memory = 0
        node.memory = memory
        node.save(update_fields=['memory'])

        # This gathers the system vendor, product, version, and serial. Custom
        # built machines and some Supermicro servers do not provide this
        # information.
        for key in ["vendor", "product", "version", "serial"]:
            value = get_xml_field_value(
                evaluator, "//node[@class='system']/%s/text()" % key)
            if value:
                NodeMetadata.objects.update_or_create(
                    node=node, key="system_%s" % key,
                    defaults={"value": value})

        # Gather the mainboard information, all systems should have this.
        for key in ["vendor", "product"]:
            value = get_xml_field_value(
                evaluator, "//node[@id='core']/%s/text()" % key)
            if value:
                NodeMetadata.objects.update_or_create(
                    node=node, key="mainboard_%s" % key,
                    defaults={"value": value})

        for key in ["version", "date"]:
            value = get_xml_field_value(
                evaluator,
                "//node[@id='core']/node[@id='firmware']/%s/text()" % key)
            if value:
                NodeMetadata.objects.update_or_create(
                    node=node, key="mainboard_firmware_%s" % key,
                    defaults={'value': value})


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

    # Some CPU vendors(Intel) include the speed in the model. If so use that
    # for the CPU speed as the speeds from lscpu are effected by CPU scaling.
    m = re.search(
        '^Model name:\s+(?P<model_name>.+)(\s@\s(?P<ghz>\d+\.\d+)GHz)$',
        output, re.MULTILINE)
    if m is not None:
        cpu_model = m.group('model_name')
        node.cpu_speed = int(float(m.group('ghz')) * 1000)
    else:
        m = re.search(
            '^Model name:\s+(?P<model_name>.+)$', output, re.MULTILINE)
        if m is not None:
            cpu_model = m.group('model_name')
        else:
            cpu_model = None
        # Try the max MHz if available.
        m = re.search(
            '^CPU max MHz:\s+(?P<mhz>\d+)(\.\d+)?$', output, re.MULTILINE)
        if m is not None:
            node.cpu_speed = int(m.group('mhz'))
        else:
            # Fall back on the current speed, round it to the nearest hundredth
            # as the number may be effected by CPU scaling.
            m = re.search(
                '^CPU MHz:\s+(?P<mhz>\d+)(\.\d+)?$', output, re.MULTILINE)
            if m is not None:
                node.cpu_speed = round(int(m.group('mhz')) / 100) * 100

    if cpu_model:
        NodeMetadata.objects.update_or_create(
            node=node, key='cpu_model', defaults={'value': cpu_model})

    node.save(update_fields=['cpu_count', 'cpu_speed'])


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
        firmware_version = block_info.get("FIRMWARE_VERSION")
        tags = get_tags_from_block_info(block_info)

        # First check if there is an existing device with the same name.
        # If so, we need to rename it. Its name will be changed back later,
        # when we loop around to it.
        existing = PhysicalBlockDevice.objects.filter(
            node=node, name=name).all()
        for device in existing:
            # Use the device ID to ensure a unique temporary name.
            device.name = "%s.%d" % (device.name, device.id)
            device.save(update_fields=['name'])

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
            block_device.firmware_version = firmware_version
            block_device.tags = tags
            block_device.save()
        else:
            # MAAS doesn't allow disks smaller than 4MiB so skip them
            if size <= MIN_BLOCK_DEVICE_SIZE:
                continue
            # Skip loopback devices as they won't be available on next boot
            if id_path.startswith('/dev/loop'):
                continue
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
                firmware_version=firmware_version,
                )

    # Clear boot_disk if it is being removed.
    boot_disk = node.boot_disk
    if boot_disk is not None and boot_disk in previous_block_devices:
        boot_disk = None
    if node.boot_disk != boot_disk:
        node.boot_disk = boot_disk
        node.save(update_fields=['boot_disk'])

    # XXX ltrager 11-16-2017 - Don't regenerate ScriptResults on controllers.
    # Currently this is not needed saving us 1 database query. However, if
    # commissioning is ever enabled for controllers regeneration will need
    # to be allowed on controllers others storage testing may break.
    if node.current_testing_script_set is not None and not node.is_controller:
        # LP: #1731353 - Regenerate ScriptResults before deleting
        # PhyscalBlockDevices. This creates a ScriptResult with proper
        # parameters for each storage device on the system. Storage devices no
        # long available will be delete which causes a casade delete on their
        # assoicated ScriptResults.
        node.current_testing_script_set.regenerate()

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
    NodeMetadata.objects.update_or_create(
        node=node, key=NODE_METADATA.VENDOR_NAME, defaults={"value": vendor})
    NodeMetadata.objects.update_or_create(
        node=node, key=NODE_METADATA.PHYSICAL_MODEL_NAME,
        defaults={"value": model})
    return switch


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
                node=node, key=node_key, defaults={"value": info[fruid_key]})


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


def filter_modaliases(
        modaliases_discovered, modaliases=None, pci=None, usb=None):
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
                vendor, device = pattern.split(':')
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
                    vendor=vendor, device=device))
    if usb is not None:
        for pattern in usb:
            try:
                vendor, product = pattern.split(':')
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
                    vendor=vendor, product=product))
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
NODE_INFO_SCRIPTS[CPUINFO_OUTPUT_NAME]['hook'] = parse_cpuinfo
NODE_INFO_SCRIPTS[VIRTUALITY_OUTPUT_NAME]['hook'] = set_virtual_tag
NODE_INFO_SCRIPTS[GET_FRUID_DATA_OUTPUT_NAME]['hook'] = (
    update_node_fruid_metadata)
NODE_INFO_SCRIPTS[BLOCK_DEVICES_OUTPUT_NAME]['hook'] = (
    update_node_physical_block_devices)
NODE_INFO_SCRIPTS[IPADDR_OUTPUT_NAME]['hook'] = (
    update_node_network_information)
NODE_INFO_SCRIPTS[SRIOV_OUTPUT_NAME]['hook'] = (
    update_node_network_interface_tags)
NODE_INFO_SCRIPTS[LIST_MODALIASES_OUTPUT_NAME]['hook'] = (
    create_metadata_by_modalias)
