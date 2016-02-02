# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Builtin node info scripts."""

__all__ = [
    'NODE_INFO_SCRIPTS',
    'LIST_MODALIASES_OUTPUT_NAME',
    'LLDP_OUTPUT_NAME',
    'LSHW_OUTPUT_NAME',
    ]

from collections import OrderedDict
from inspect import getsource
import json
import os
from textwrap import dedent

# Name of the file where the node info scripts store lshw output.
LSHW_OUTPUT_NAME = '00-maas-01-lshw.out'

# Name of the file where the node info scripts store LLDP output.
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
    #!/usr/bin/python3
    # -*- coding: utf-8 -*-

    import json

    {function_source}

    if __name__ == '__main__':
        args = json.loads({function_args!r})
        kwargs = json.loads({function_kwargs!r})
        {function_name}(*args, **kwargs)
    """)
    script = template.format(
        function_name=function.__name__,
        function_source=dedent(getsource(function)).strip(),
        function_args=json.dumps(args),  # ASCII.
        function_kwargs=json.dumps(kwargs),  # ASCII.
    )
    return script.encode("utf-8")


# Built-in script to run lshw.
LSHW_SCRIPT = dedent("""\
    #!/bin/sh
    sudo /usr/bin/lshw -xml
    """)

# Built-in script to run `ip addr`
IPADDR_SCRIPT = dedent("""\
    #!/bin/sh
    ip addr
    """)

# Built-in script to detect virtual instances. It will only detect QEMU
# for now and may need expanding/generalising at some point.
# XXX ltrager 2016-01-14 - Replace with virt-what
VIRTUALITY_SCRIPT = dedent("""\
    #!/bin/sh
    grep '^model name.*QEMU.*' /proc/cpuinfo >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "virtual"
    else
        echo "notvirtual"
    fi
    """)


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
        # Run dhclient in the background to avoid blocking node info.
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
    import os
    from subprocess import check_call
    check_call(("apt-get", "install", "--yes", "lldpd"))
    from codecs import open
    with open(config_file, "a", "ascii") as fd:
        fd.write('\n')  # Ensure there's a newline.
        fd.write('# Configured by MAAS:\n')
        fd.write('DAEMON_ARGS="-c -f -s -e -r"\n')
    # Reload initctl configuration in order to make sure that the
    # lldpd init script is available before restart, otherwise
    # it might cause gathering node info to fail. This is due bug
    # (LP: #882147) in the kernel.
    if os.path.isdir("/run/systemd/system"):
        check_call(("systemctl", "daemon-reload"))
    else:
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


LIST_MODALIASES_OUTPUT_NAME = '00-maas-04-list-modaliases.out'
LIST_MODALIASES_SCRIPT = dedent("""\
    #!/bin/sh
    find /sys -name modalias -print0 | xargs -0 cat | sort -u
    """)


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

    # XXX: Set LC_* and LANG environment variables to C.UTF-8 explicitly.

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
    block_list = block_list.decode("utf-8")
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
    del_blocks = set()
    seen_devices = set()
    for block_info in blockdevs:
        # Some RAID devices return the name of the device seperated with "!",
        # but udevadm expects it to be a "/".
        block_name = block_info["NAME"].replace("!", "/")
        udev_info = check_output(
            ("udevadm", "info", "-q", "all", "-n", block_name))
        udev_info = udev_info.decode("utf-8")
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
                del_blocks.add(block_name)
                break

        if block_name in del_blocks:
            continue

        # Skip duplicate (serial, model) for multipath.
        serial = block_info.get("SERIAL")
        if serial:
            model = block_info.get("MODEL", "").strip()
            if (serial, model) in seen_devices:
                del_blocks.add(block_name)
                continue
            seen_devices.add((serial, model))

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
            ("sudo", "blockdev", "--getsize64", block_path))
        device_block_size = check_output(
            ("sudo", "blockdev", "--getbsz", block_path))
        block_info["SIZE"] = device_size.decode("utf-8").strip()
        block_info["BLOCK_SIZE"] = device_block_size.decode("utf-8").strip()

    # Output block device information in json
    json_output = json.dumps(blockdevs, indent=True)
    print(json_output)  # json_outout is ASCII-only.


def null_hook(node, output, exit_status):
    """Intentionally do nothing.

    Use this to explicitly ignore the response from a built-in
    node info script.
    """

# Built-in node info scripts.  These go into the commissioning tarball
# together with user-provided commissioning scripts or are executed by the
# rack or region refresh process. To keep namespaces separated, names of the
# built-in scripts must be prefixed with "00-maas-" or "99-maas-".
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
# Post-processing hooks can't exist on the rack controller as the rack
# controller isn't running django. On the region controller we set the hooks in
# metadataserver/models/commissioningscript.py
NODE_INFO_SCRIPTS = OrderedDict([
    (LSHW_OUTPUT_NAME, {
        'content': LSHW_SCRIPT.encode('ascii'),
        'hook': null_hook,
    }),
    ('00-maas-02-virtuality.out', {
        'content': VIRTUALITY_SCRIPT.encode('ascii'),
        'hook': null_hook,
    }),
    ('00-maas-03-install-lldpd.out', {
        'content': make_function_call_script(
            lldpd_install, config_file="/etc/default/lldpd"),
        'hook': null_hook,
    }),
    (LIST_MODALIASES_OUTPUT_NAME, {
        'content': LIST_MODALIASES_SCRIPT.encode('ascii'),
        'hook': null_hook,
    }),
    ('00-maas-06-dhcp-unconfigured-ifaces', {
        'content': make_function_call_script(dhcp_explore),
        'hook': null_hook,
    }),
    ('00-maas-07-block-devices.out', {
        'content': make_function_call_script(gather_physical_block_devices),
        'hook': null_hook,
    }),
    ('99-maas-01-wait-for-lldpd.out', {
        'content': make_function_call_script(
            lldpd_wait, "/var/run/lldpd.socket", time_delay=60),
        'hook': null_hook,
    }),
    (LLDP_OUTPUT_NAME, {
        'content': make_function_call_script(lldpd_capture),
        'hook': null_hook,
    }),
    ('99-maas-03-network-interfaces.out', {
        'content': IPADDR_SCRIPT.encode('ascii'),
        'hook': null_hook,
    }),
])


def add_names_to_scripts(scripts):
    """Derive script names from the script output filename.

    Designed for working with the `NODE_INFO_SCRIPTS`
    structure.

    """
    for output_name, config in scripts.items():
        if "name" not in config:
            script_name = os.path.basename(output_name)
            script_name, _ = os.path.splitext(script_name)
            config["name"] = script_name


add_names_to_scripts(NODE_INFO_SCRIPTS)
