# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Custom commissioning scripts, and their database backing."""


from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'BUILTIN_COMMISSIONING_SCRIPTS',
    'CommissioningScript',
    'inject_lldp_result',
    'inject_lshw_result',
    'inject_result',
    'LIST_MODALIASES_OUTPUT_NAME',
    'LLDP_OUTPUT_NAME',
    'LSHW_OUTPUT_NAME',
    ]

from functools import partial
from inspect import getsource
from io import BytesIO
from itertools import chain
import json
import logging
import math
import os.path
import tarfile
from textwrap import dedent
from time import time as now

from django.db.models import (
    CharField,
    Manager,
    Model,
)
from lxml import etree
from maasserver.fields import MAC
from maasserver.models.macaddress import MACAddress
from maasserver.models.physicalblockdevice import PhysicalBlockDevice
from maasserver.models.tag import Tag
from metadataserver import DefaultMeta
from metadataserver.enum import RESULT_TYPE
from metadataserver.fields import (
    Bin,
    BinaryField,
)
from metadataserver.models.noderesult import NodeResult


logger = logging.getLogger(__name__)


# Path prefix for commissioning scripts.  Commissioning scripts will be
# extracted into this directory.
ARCHIVE_PREFIX = "commissioning.d"

# Name of the file where the commissioning scripts store lshw output.
LSHW_OUTPUT_NAME = '00-maas-01-lshw.out'

# Name of the file where the commissioning scripts store LLDP output.
LLDP_OUTPUT_NAME = '99-maas-02-capture-lldp.out'


def make_function_call_script(function, *args, **kwargs):
    """Compose a Python script that calls the given function.

    The function's source will be obtained by inspection. Ensure that
    the function is fully self-contained; don't rely on variables or
    imports from the module in which it is defined.

    The given arguments will be used when calling the function in the
    composed script. They are serialised into JSON with the
    limitations on types that that implies.

    :return: `bytes`
    """
    template = dedent("""\
    #!/usr/bin/python
    # -*- coding: utf-8 -*-

    from __future__ import (
        absolute_import,
        print_function,
        unicode_literals,
        )

    import json

    __metaclass__ = type
    __all__ = [{function_name!r}]

    {function_source}

    if __name__ == '__main__':
        args = json.loads({function_args!r})
        kwargs = json.loads({function_kwargs!r})
        {function_name}(*args, **kwargs)
    """)
    script = template.format(
        function_name=function.__name__.decode('ascii'),
        function_source=dedent(getsource(function).decode('utf-8')).strip(),
        function_args=json.dumps(args).decode('utf-8'),
        function_kwargs=json.dumps(kwargs).decode('utf-8'),
    )
    return script.encode("utf-8")


# Built-in script to run lshw.
LSHW_SCRIPT = dedent("""\
    #!/bin/sh
    lshw -xml
    """)

# Built-in script to run `ip link`
IPLINK_SCRIPT = dedent("""\
    #!/bin/sh
    ip link
    """)

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


def update_node_network_information(node, output, exit_status):
    """Updates the network interfaces from the results of `IPLINK_SCRIPT`.

    Creates and deletes MACAddresses according to what we currently know about
    this node's hardware.

    If `exit_status` is non-zero, this function returns without doing
    anything.

    """
    assert isinstance(output, bytes)
    if exit_status != 0:
        return

    # Get the MAC addresses of all connected interfaces.
    hw_macaddresses = {
        MAC(line.split()[1]) for line in output.splitlines()
        if line.strip().startswith('link/ether')
    }

    # Important notice: hw_addresses contains MAC objects while
    # node.macaddress_set.all() contains MACAddress objects.

    # MAC addresses found in the hardware node but not on the db will be
    # created or reassigned.
    for address in hw_macaddresses:
        if address not in [MAC(m.mac_address)
                           for m in node.macaddress_set.all()]:
            try:
                mac_address = MACAddress.objects.get(mac_address=address)
                mac_address.node = node
                mac_address.save()
            except MACAddress.DoesNotExist:
                MACAddress(mac_address=address, node=node).save()

    # MAC addresses found in the db but not on the hardware node will be
    # deleted.
    for mac_address in node.macaddress_set.all():
        if MAC(mac_address.mac_address) not in hw_macaddresses:
            mac_address.delete()


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


# Built-in script to detect virtual instances. It will only detect QEMU
# for now and may need expanding/generalising at some point.
VIRTUALITY_SCRIPT = dedent("""\
    #!/bin/sh
    grep '^model name.*QEMU.*' /proc/cpuinfo >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "virtual"
    else
        echo "notvirtual"
    fi
    """)


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


# Run `dhclient` on all the unconfigured interfaces.
# This is done to create records in the leases file for the
# NICs attached to unconfigured interfaces.  This way the leases
# parser will be able to connect these NICs and the networks
# MAAS knows about.
def dhcp_explore():
    def get_iface_list(ifconfig_output):
        return [
            line.split()[0]
            for line in ifconfig_output.splitlines()[1:]]

    from subprocess import check_output, call
    all_ifaces = get_iface_list(check_output(("ifconfig", "-s", "-a")))
    configured_ifaces = get_iface_list(check_output(("ifconfig", "-s")))
    unconfigured_ifaces = set(all_ifaces) - set(configured_ifaces)
    for iface in sorted(unconfigured_ifaces):
        # Run dhclient in the background to avoid blocking the commissioning.
        call(["dhclient", "-nw", iface])
        # Ignore return value and continue running dhcplient on the
        # other interfaces.


# This function must be entirely self-contained. It must not use
# variables or imports from the surrounding scope.
def lldpd_install(config_file):
    """Installs and configures `lldpd` for passive capture.

    `config_file` refers to a shell script that is sourced by
    `lldpd`'s init script, i.e. it's Upstart config on Ubuntu.

    It selects the following options for the `lldpd` daemon:

    -c  Enable the support of CDP protocol to deal with Cisco routers
        that do not speak LLDP. If repeated, CDPv1 packets will be
        sent even when there is no CDP peer detected.

    -f  Enable the support of FDP protocol to deal with Foundry routers
        that do not speak LLDP. If repeated, FDP packets will be sent
        even when there is no FDP peer detected.

    -s  Enable the support of SONMP protocol to deal with Nortel
        routers and switches that do not speak LLDP. If repeated,
        SONMP packets will be sent even when there is no SONMP peer
        detected.

    -e  Enable the support of EDP protocol to deal with Extreme
        routers and switches that do not speak LLDP. If repeated, EDP
        packets will be sent even when there is no EDP peer detected.

    -r  Receive-only mode. With this switch, lldpd will not send any
        frame. It will only listen to neighbors.

    These flags are chosen so that we're able to capture information
    from a broad spectrum of equipment, but without advertising the
    node's temporary presence.

    """
    from subprocess import check_call
    check_call(("apt-get", "install", "--yes", "lldpd"))
    from codecs import open
    with open(config_file, "a", "ascii") as fd:
        fd.write('\n')  # Ensure there's a newline.
        fd.write('# Configured by MAAS:\n')
        fd.write('DAEMON_ARGS="-c -f -s -e -r"\n')
    # Reload initctl configuration in order to make sure that the
    # lldpd init script is available before restart, otherwise
    # it might cause commissioning to fail. This is due bug
    # (LP: #882147) in the kernel.
    check_call(("initctl", "reload-configuration"))
    check_call(("service", "lldpd", "restart"))


# This function must be entirely self-contained. It must not use
# variables or imports from the surrounding scope.
def lldpd_wait(reference_file, time_delay):
    """Wait until `lldpd` has been running for `time_delay` seconds.

    On an Ubuntu system, `reference_file` is typically `lldpd`'s UNIX
    socket in `/var/run`.

    """
    from os.path import getmtime
    time_ref = getmtime(reference_file)
    from time import sleep, time
    time_remaining = time_ref + time_delay - time()
    if time_remaining > 0:
        sleep(time_remaining)


# This function must be entirely self-contained. It must not use
# variables or imports from the surrounding scope.
def lldpd_capture():
    """Capture LLDP information from `lldpd` in XML form."""
    from subprocess import check_call
    check_call(("lldpctl", "-f", "xml"))


_xpath_routers = "/lldp//id[@type='mac']/text()"


def extract_router_mac_addresses(raw_content):
    """Extract the routers' MAC Addresses from raw LLDP information."""
    if not raw_content:
        return None
    assert isinstance(raw_content, bytes)
    parser = etree.XMLParser()
    doc = etree.XML(raw_content.strip(), parser)
    return doc.xpath(_xpath_routers)


def set_node_routers(node, output, exit_status):
    """Process recently captured raw LLDP information.

    The list of the routers' MAC Addresses is extracted from the raw LLDP
    information and stored on the given node.

    If `exit_status` is non-zero, this function returns without doing
    anything.
    """
    assert isinstance(output, bytes)
    if exit_status != 0:
        return
    routers = extract_router_mac_addresses(output)
    if routers is None:
        node.routers = None
    else:
        node.routers = [MAC(router) for router in routers]
    node.save()

LIST_MODALIASES_OUTPUT_NAME = '00-maas-04-list-modaliases.out'
LIST_MODALIASES_SCRIPT = \
    'find /sys -name modalias -print0 | xargs -0 cat | sort -u'


def gather_physical_block_devices(dev_disk_byid='/dev/disk/by-id/'):
    """Gathers information about a nodes physical block devices.

    The following commands are ran in order to gather the required information.

    lsblk       Gathers the initial block devices not including slaves or
                holders. Gets the name, read-only, removable, model, and
                if rotary.

    udevadm     Grabs the device path, serial number, if connected over
                SATA and rotational speed.

    blockdev    Grabs the block size and size of the disk in bytes.

    """
    import json
    import os
    import shlex
    from subprocess import check_output

    def _path_to_idpath(path):
        """Searches dev_disk_byid for a device symlinked to /dev/[path]"""
        if os.path.exists(dev_disk_byid):
            for link in os.listdir(dev_disk_byid):
                if os.path.exists(path) and os.path.samefile(
                        os.path.join(dev_disk_byid, link), path):
                    return os.path.join(dev_disk_byid, link)
        return None

    # Grab the block devices from lsblk.
    blockdevs = []
    block_list = check_output(
        ("lsblk", "-d", "-P", "-o", "NAME,RO,RM,MODEL,ROTA"))
    for blockdev in block_list.splitlines():
        tokens = shlex.split(blockdev)
        current_block = {}
        for token in tokens:
            k, v = token.split("=", 1)
            current_block[k] = v.strip()
        blockdevs.append(current_block)

    # Grab the device path, serial number, and sata connection.
    UDEV_MAPPINGS = {
        "DEVNAME": "PATH",
        "ID_SERIAL_SHORT": "SERIAL",
        "ID_ATA_SATA": "SATA",
        "ID_ATA_ROTATION_RATE_RPM": "RPM"
        }
    del_blocks = []
    for block_info in blockdevs:
        # Some RAID devices return the name of the device seperated with "!",
        # but udevadm expects it to be a "/".
        block_name = block_info["NAME"].replace("!", "/")
        udev_info = check_output(
            ("udevadm", "info", "-q", "all", "-n", block_name))
        for info_line in udev_info.splitlines():
            info_line = info_line.strip()
            if info_line == "":
                continue
            _, info = info_line.split(" ", 1)
            if "=" not in info:
                continue
            k, v = info.split("=", 1)
            if k in UDEV_MAPPINGS:
                block_info[UDEV_MAPPINGS[k]] = v.strip()
            if k == "ID_CDROM" and v == "1":
                # Remove any type of CDROM from the blockdevs, as we
                # cannot use this device for installation.
                del_blocks.append(block_name)

    # Remove any devices that need to be removed.
    blockdevs = [
        block_info
        for block_info in blockdevs
        if block_info["NAME"] not in del_blocks
        ]

    # Grab the size of the device, block size and id-path.
    for block_info in blockdevs:
        block_path = block_info["PATH"]
        id_path = _path_to_idpath(block_path)
        if id_path is not None:
            block_info["ID_PATH"] = id_path
        device_size = check_output(
            ("blockdev", "--getsize64", block_path))
        device_block_size = check_output(
            ("blockdev", "--getbsz", block_path))
        block_info["SIZE"] = device_size.strip()
        block_info["BLOCK_SIZE"] = device_block_size.strip()

    # Output block device information in json
    json_output = json.dumps(blockdevs, indent=True)
    print(json_output)


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


def update_node_physical_block_devices(node, output, exit_status):
    """Process the results of `gather_physical_block_devices`.

    This updates the physical block devices that are attached to a node.

    If `exit_status` is non-zero, this function returns without doing
    anything.
    """
    assert isinstance(output, bytes)
    if exit_status != 0:
        return
    try:
        blockdevs = json.loads(output)
    except ValueError as e:
        raise ValueError(e.message + ': ' + output)
    PhysicalBlockDevice.objects.filter(node=node).delete()
    for block_info in blockdevs:
        # Skip the read-only devices. We keep them in the output for
        # the user to view but they do not get an entry in the database.
        if block_info["RO"] == "1":
            continue
        model = block_info.get("MODEL", "")
        serial = block_info.get("SERIAL", "")
        tags = get_tags_from_block_info(block_info)
        PhysicalBlockDevice.objects.create(
            node=node,
            name=block_info["NAME"],
            path=block_info["PATH"],
            id_path=block_info.get("ID_PATH"),
            size=long(block_info["SIZE"]),
            block_size=int(block_info["BLOCK_SIZE"]),
            tags=tags,
            model=model,
            serial=serial,
            )


def null_hook(node, output, exit_status):
    """Intentionally do nothing.

    Use this to explicitly ignore the response from a built-in
    commissioning script.
    """


# Built-in commissioning scripts.  These go into the commissioning
# tarball together with user-provided commissioning scripts.
# To keep namespaces separated, names of the built-in scripts must be
# prefixed with "00-maas-" or "99-maas-".
#
# The dictionary is keyed on the output filename that the script
# produces. This is so it can be looked up later in the post-processing
# hook.
#
# The contents of each dictionary entry are another dictionary with
# keys:
#   "name" -> the script's name
#   "content" -> the actual script
#   "hook" -> a post-processing hook.
#
# The post-processing hook is a function that will be passed the node
# and the raw content of the script's output, e.g. "hook(node, raw_content)"
BUILTIN_COMMISSIONING_SCRIPTS = {
    LSHW_OUTPUT_NAME: {
        'content': LSHW_SCRIPT.encode('ascii'),
        'hook': update_hardware_details,
    },
    '00-maas-02-virtuality.out': {
        'content': VIRTUALITY_SCRIPT.encode('ascii'),
        'hook': set_virtual_tag,
    },
    '00-maas-03-install-lldpd.out': {
        'content': make_function_call_script(
            lldpd_install, config_file="/etc/default/lldpd"),
        'hook': null_hook,
    },
    LIST_MODALIASES_OUTPUT_NAME: {
        'content': LIST_MODALIASES_SCRIPT.encode('ascii'),
        'hook': null_hook,
    },
    '00-maas-05-network-interfaces.out': {
        'content': IPLINK_SCRIPT.encode('ascii'),
        'hook': update_node_network_information,
    },
    '00-maas-06-dhcp-unconfigured-ifaces': {
        'content': make_function_call_script(dhcp_explore),
        'hook': null_hook,
    },
    '00-maas-07-block-devices.out': {
        'content': make_function_call_script(gather_physical_block_devices),
        'hook': update_node_physical_block_devices,
    },
    '99-maas-01-wait-for-lldpd.out': {
        'content': make_function_call_script(
            lldpd_wait, "/var/run/lldpd.socket", time_delay=60),
        'hook': null_hook,
    },
    LLDP_OUTPUT_NAME: {
        'content': make_function_call_script(lldpd_capture),
        'hook': set_node_routers,
    },
}


def add_names_to_scripts(scripts):
    """Derive script names from the script output filename.

    Designed for working with the `BUILTIN_COMMISSIONING_SCRIPTS`
    structure.

    """
    for output_name, config in scripts.items():
        if "name" not in config:
            script_name = os.path.basename(output_name)
            script_name, _ = os.path.splitext(script_name)
            config["name"] = script_name


add_names_to_scripts(BUILTIN_COMMISSIONING_SCRIPTS)


def add_script_to_archive(tarball, name, content, mtime):
    """Add a commissioning script to an archive of commissioning scripts."""
    assert isinstance(content, bytes), "Script content must be binary."
    tarinfo = tarfile.TarInfo(name=os.path.join(ARCHIVE_PREFIX, name))
    tarinfo.size = len(content)
    # Mode 0755 means: u=rwx,go=rx
    tarinfo.mode = 0755
    # Modification time defaults to Epoch, which elicits annoying
    # warnings when decompressing.
    tarinfo.mtime = mtime
    tarball.addfile(tarinfo, BytesIO(content))


class CommissioningScriptManager(Manager):
    """Utility for the collection of `CommissioningScript`s."""

    def _iter_builtin_scripts(self):
        for script in BUILTIN_COMMISSIONING_SCRIPTS.itervalues():
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
    if name in BUILTIN_COMMISSIONING_SCRIPTS:
        postprocess_hook = BUILTIN_COMMISSIONING_SCRIPTS[name]['hook']
        postprocess_hook(node=node, output=output, exit_status=exit_status)


def inject_lshw_result(node, output, exit_status=0):
    """Convenience to call `inject_result(name=LSHW_OUTPUT_NAME, ...)`."""
    return inject_result(node, LSHW_OUTPUT_NAME, output, exit_status)


def inject_lldp_result(node, output, exit_status=0):
    """Convenience to call `inject_result(name=LLDP_OUTPUT_NAME, ...)`."""
    return inject_result(node, LLDP_OUTPUT_NAME, output, exit_status)
