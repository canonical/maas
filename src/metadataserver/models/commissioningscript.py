# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Custom commissioning scripts, and their database backing."""


__all__ = [
    'NODE_INFO_SCRIPTS',
    'CommissioningScript',
    'inject_lldp_result',
    'inject_lshw_result',
    'inject_result',
    ]

from functools import partial
from io import BytesIO
from itertools import chain
import json
import logging
import math
import os.path
import tarfile
from time import time as now

from django.db.models import (
    CharField,
    Manager,
    Model,
)
from lxml import etree
from maasserver.models import Fabric
from maasserver.models.interface import PhysicalInterface
from maasserver.models.physicalblockdevice import PhysicalBlockDevice
from maasserver.models.tag import Tag
from metadataserver import DefaultMeta
from metadataserver.enum import RESULT_TYPE
from metadataserver.fields import (
    Bin,
    BinaryField,
)
from metadataserver.models.noderesult import NodeResult
from provisioningserver.refresh.node_info_scripts import (
    LLDP_OUTPUT_NAME,
    LSHW_OUTPUT_NAME,
    NODE_INFO_SCRIPTS,
)
from provisioningserver.utils.ipaddr import parse_ip_addr


logger = logging.getLogger(__name__)


# Path prefix for commissioning scripts.  Commissioning scripts will be
# extracted into this directory.
ARCHIVE_PREFIX = "commissioning.d"

# Count the processors which do not declare their number of 'threads'
# as 1 processor.
_xpath_processor_count = """\
    sum(//node[@id='core']/
        node[@class='processor']
            [not(@disabled)]//setting[@id='threads']/@value) +
    count(//node[@id='core']/node[@class='processor']
        [not(@disabled)][not(configuration/setting[@id='threads'])])"""


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
        # Ignore lxcbr0 which is created by default on Xenial+.
        elif link['name'] == 'lxcbr0':
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
        cpu_count = evaluator(_xpath_processor_count)
        memory = evaluator(_xpath_memory_bytes)
        if not memory or math.isnan(memory):
            memory = 0
        node.cpu_count = cpu_count or 0
        node.memory = memory
        node.save()


def set_virtual_tag(node, output, exit_status):
    """Process the results of `VIRTUALITY_SCRIPT`.

    This adds or removes the *virtual* tag from the node, depending on
    the presence of the terms "notvirtual" or "virtual" in `output`.

    If `exit_status` is non-zero, this function returns without doing
    anything.
    """
    assert isinstance(output, bytes)
    if exit_status != 0:
        return
    tag, _ = Tag.objects.get_or_create(name='virtual')
    if b'notvirtual' in output:
        node.tags.remove(tag)
    elif b'virtual' in output:
        node.tags.add(tag)
    else:
        logger.warn(
            "Neither 'virtual' nor 'notvirtual' appeared in the "
            "captured VIRTUALITY_SCRIPT output for node %s.",
            node.system_id)


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
        if not id_path:
            # Fallback to the dev path if id_path missing.
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
NODE_INFO_SCRIPTS['00-maas-02-virtuality.out']['hook'] = set_virtual_tag
NODE_INFO_SCRIPTS['00-maas-07-block-devices.out']['hook'] = (
    update_node_physical_block_devices)
NODE_INFO_SCRIPTS['99-maas-03-network-interfaces.out']['hook'] = (
    update_node_network_information)


def add_script_to_archive(tarball, name, content, mtime):
    """Add a commissioning script to an archive of commissioning scripts."""
    assert isinstance(content, bytes), "Script content must be binary."
    tarinfo = tarfile.TarInfo(name=os.path.join(ARCHIVE_PREFIX, name))
    tarinfo.size = len(content)
    # Mode 0755 means: u=rwx,go=rx
    tarinfo.mode = 0o755
    # Modification time defaults to Epoch, which elicits annoying
    # warnings when decompressing.
    tarinfo.mtime = mtime
    tarball.addfile(tarinfo, BytesIO(content))


class CommissioningScriptManager(Manager):
    """Utility for the collection of `CommissioningScript`s."""

    def _iter_builtin_scripts(self):
        for script in NODE_INFO_SCRIPTS.values():
            yield script['name'], script['content']

    def _iter_user_scripts(self):
        for script in self.all():
            yield script.name, script.content

    def _iter_scripts(self):
        return chain(
            self._iter_builtin_scripts(),
            self._iter_user_scripts())

    def get_archive(self):
        """Produce a tar archive of all commissioning scripts.

        Each of the scripts will be in the `ARCHIVE_PREFIX` directory.
        """
        binary = BytesIO()
        scripts = sorted(self._iter_scripts())
        with tarfile.open(mode='w', fileobj=binary) as tarball:
            add_script = partial(add_script_to_archive, tarball, mtime=now())
            for name, content in scripts:
                add_script(name, content)
        return binary.getvalue()


class CommissioningScript(Model):
    """User-provided commissioning script.

    Actually a commissioning "script" could be a binary, e.g. because a
    hardware vendor supplied an update in the form of a binary executable.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    objects = CommissioningScriptManager()

    name = CharField(max_length=255, null=False, editable=True, unique=True)
    content = BinaryField(null=False)


def inject_result(node, name, output, exit_status=0):
    """Inject a `name` result and trigger related hooks, if any.

    `output` and `exit_status` are recorded as `NodeResult`
    instances with the `name` given. A built-in hook is then searched
    for; if found, it is invoked.
    """
    assert isinstance(output, bytes)
    NodeResult.objects.store_data(
        node, name, script_result=exit_status,
        result_type=RESULT_TYPE.COMMISSIONING, data=Bin(output))
    if name in NODE_INFO_SCRIPTS:
        postprocess_hook = NODE_INFO_SCRIPTS[name]['hook']
        postprocess_hook(node=node, output=output, exit_status=exit_status)


def inject_lshw_result(node, output, exit_status=0):
    """Convenience to call `inject_result(name=LSHW_OUTPUT_NAME, ...)`."""
    return inject_result(node, LSHW_OUTPUT_NAME, output, exit_status)


def inject_lldp_result(node, output, exit_status=0):
    """Convenience to call `inject_result(name=LLDP_OUTPUT_NAME, ...)`."""
    return inject_result(node, LLDP_OUTPUT_NAME, output, exit_status)
