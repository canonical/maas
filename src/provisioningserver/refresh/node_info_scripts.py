# Copyright 2016-2017 Canonical Ltd.  This software is licensed under the
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
LSHW_OUTPUT_NAME = '00-maas-01-lshw'

# Name of the file where the node info scripts store LLDP output.
LLDP_OUTPUT_NAME = '99-maas-02-capture-lldp'


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
    #!/bin/bash
    sudo -n /usr/bin/lshw -xml
    """)

# Built-in script to run `ip addr`
IPADDR_SCRIPT = dedent("""\
    #!/bin/bash
    ip addr
    """)

# Built-in script to detect virtual instances.
VIRTUALITY_SCRIPT = dedent("""\
    #!/bin/bash
    # In Bourne Shell `type -p` does not work; `which` is closest.
    if which systemd-detect-virt > /dev/null; then
        # systemd-detect-virt prints "none" and returns nonzero if
        # virtualisation is not detected. We suppress the exit code so that
        # the calling machinery does not think there was a failure, and rely
        # on the "none" token instead.
        systemd-detect-virt || true
    elif grep -q '^model name.*QEMU.*' /proc/cpuinfo; then
        # Fall back if systemd-detect-virt isn't available. This method only
        # detects QEMU virtualization not including KVM.
        echo "qemu"
    else
        echo "none"
    fi
    """)

CPUINFO_SCRIPT = dedent("""\
    #!/bin/bash
    # Gather the standard output as it has some extra info
    lscpu
    # Gather the machine readable output for processing
    lscpu -p=cpu,core,socket
    """)

SERIAL_PORTS_SCRIPT = dedent("""\
    #!/bin/bash
    # Do not fail commissioning if this fails.
    set +e
    find /sys/class/tty/ ! -type d -print0 2> /dev/null \
        | xargs -0 readlink -f \
        | sort -u
    exit 0
    """)

SRIOV_SCRIPT = dedent("""\
    #!/bin/bash
    for file in $(find /sys/devices/ -name sriov_numvfs); do
        dir=$(dirname "$file")
        for eth in $(ls "$dir/net/"); do
            mac=`cat "$(dirname $file)/net/$eth/address"`
            echo "$eth $mac"
        done
    done
    """)

SUPPORT_SCRIPT = dedent("""\
    #!/bin/bash
    # Do not fail commissioning if this fails.
    set +e
    echo "-----BEGIN KERNEL INFO-----"
    uname -a
    echo "-----END KERNEL INFO-----"
    echo ""
    echo "-----BEGIN KERNEL COMMAND LINE-----"
    cat /proc/cmdline
    echo "-----END KERNEL COMMAND LINE-----"
    CMDLINE="$(cat /proc/cmdline)"
    CLOUD_CONFIG="$(echo $CMDLINE | xargs -n1 echo | grep cloud-config-url)"
    URL="$(echo $CLOUD_CONFIG | grep -o http.*)"
    if [ "$URL" != "" ]; then
        echo ""
        echo "-----BEGIN CLOUD CONFIG QUERY-----"
        curl -v "$URL" 2>&1
        echo "-----END CLOUD CONFIG QUERY-----"
    fi
    echo ""
    echo "-----BEGIN CPU CORE COUNT AND MODEL-----"
    cat /proc/cpuinfo | grep '^model name' | cut -d: -f 2- | sort | uniq -c
    echo "-----BEGIN CPU CORE COUNT AND MODEL-----"
    if [ -x "$(which lspci)" ]; then
        echo ""
        echo "-----BEGIN PCI INFO-----"
        lspci -nnv
        echo "-----END PCI INFO-----"
    fi
    if [ -x "$(which lsusb)" ]; then
        echo ""
        echo "-----BEGIN USB INFO-----"
        lsusb
        echo "-----END USB INFO-----"
    fi
    echo ""
    echo "-----BEGIN MODALIASES-----"
    find /sys -name modalias -print0 2> /dev/null | xargs -0 cat | sort \
        | uniq -c
    echo "-----END MODALIASES-----"
    echo ""
    echo "-----BEGIN SERIAL PORTS-----"
    find /sys/class/tty/ ! -type d -print0 2> /dev/null \
        | xargs -0 readlink -f \
        | sort -u
    echo "-----END SERIAL PORTS-----"
    echo ""
    echo "-----BEGIN NETWORK INTERFACES-----"
    ip -o link
    echo "-----END NETWORK INTERFACES-----"
    if [ -x "$(which lsblk)" ]; then
        echo ""
        echo "-----BEGIN BLOCK DEVICE SUMMARY-----"
        lsblk
        echo "-----END BLOCK DEVICE SUMMARY-----"
    fi
    # The remainder of this script only runs as root (during commissioning).
    if [ "$(id -u)" != "0" ]; then
        exit 0
    fi
    if [ -x "$(which lsblk)" ]; then
        echo ""
        echo "-----BEGIN DETAILED BLOCK DEVICE INFO-----"
        # Note: excluding ramdisks, floppy drives, and loopback devices.
        lsblk --exclude 1,2,7 -d -P -x MAJ:MIN
        echo ""
        for dev in $(lsblk -n --exclude 1,2,7 --output KNAME); do
            echo "$dev:"
            udevadm info -q all -n $dev
            size64="$(blockdev --getsize64 /dev/$dev 2> /dev/null || echo ?)"
            bsz="$(blockdev --getbsz /dev/$dev 2> /dev/null || echo ?)"
            echo ""
            echo "    size64: $size64"
            echo "       bsz: $bsz"
        done
        echo ""
        # Enumerate the mappings that were generated (by device).
        find /dev/disk -type l | xargs ls -ln | awk '{ print $9, $10, $11 }' \
            | sort -k2
        echo "-----END DETAILED BLOCK DEVICE INFO-----"
    fi
    if [ -x "$(which dmidecode)" ]; then
        DMI_OUTFILE=/root/dmi.bin
        echo ""
        dmidecode -u --dump-bin $DMI_OUTFILE && (
            echo "-----BEGIN DMI DATA-----" ;
            base64 $DMI_OUTFILE
            echo "-----END DMI DATA-----"
        ) || (echo "Unable to read DMI information."; exit 0)
        echo ""
        echo "-----BEGIN FULL DMI DECODE-----"
        dmidecode -u --from-dump $DMI_OUTFILE
        echo "-----END FULL DMI DECODE-----"
        # via http://git.savannah.nongnu.org/cgit/dmidecode.git/tree/dmiopt.c
        DMI_STRINGS="
            bios-vendor
            bios-version
            bios-release-date
            system-manufacturer
            system-product-name
            system-version
            system-serial-number
            system-uuid
            baseboard-manufacturer
            baseboard-product-name
            baseboard-version
            baseboard-serial-number
            baseboard-asset-tag
            chassis-manufacturer
            chassis-type
            chassis-version
            chassis-serial-number
            chassis-asset-tag
            processor-family
            processor-manufacturer
            processor-version
            processor-frequency
        "
        echo ""
        echo "-----BEGIN DMI KEYPAIRS-----"
        for key in $DMI_STRINGS; do
            value=$(dmidecode --from-dump $DMI_OUTFILE -s $key)
            printf "%s=%s\\n" "$key" "$(echo $value)"
        done
        echo "-----END DMI KEYPAIRS-----"
    fi
    # Do not fail commissioning if this fails.
    exit 0
    """)


# Run `dhclient` on all the unconfigured interfaces.
# This is done to create records in the leases file for the
# NICs attached to unconfigured interfaces.  This way the leases
# parser will be able to connect these NICs and the networks
# MAAS knows about.
def dhcp_explore():
    from subprocess import call, check_output, Popen

    def get_iface_list(ifconfig_output):
        return [
            line.split()[0]
            for line in ifconfig_output.splitlines()[1:]]

    def has_ipv4_address(iface):
        output = check_output(('ip', '-4', 'addr', 'list', 'dev', iface))
        for line in output.splitlines():
            if line.find(b' inet ') >= 0:
                return True
        return False

    def has_ipv6_address(iface):
        no_ipv6_found = True
        output = check_output(('ip', '-6', 'addr', 'list', 'dev', iface))
        for line in output.splitlines():
            if line.find(b' inet6 ') >= 0:
                if line.find(b' inet6 fe80:') == -1:
                    return True
                no_ipv6_found = False
        # Bug 1640147: If there is no IPv6 address, then we consider this to be
        # a configured ipv6 interface, since ipv6 won't work there.
        return no_ipv6_found

    all_ifaces = get_iface_list(check_output(("ifconfig", "-s", "-a")))
    configured_ifaces = get_iface_list(check_output(("ifconfig", "-s")))
    configured_ifaces_4 = [
        iface for iface in configured_ifaces if has_ipv4_address(iface)]
    configured_ifaces_6 = [
        iface for iface in configured_ifaces if has_ipv6_address(iface)]
    unconfigured_ifaces_4 = set(all_ifaces) - set(configured_ifaces_4)
    unconfigured_ifaces_6 = set(all_ifaces) - set(configured_ifaces_6)
    # Run dhclient in the background to avoid blocking node_info.  We need to
    # run two dhclient processes (one for IPv6 and one for IPv4) and IPv6 will
    # run into issues if the link-local address has not finished
    # conflict-detection before it starts.  This is complicated by interaction
    # with dhclient -4 bringing the interface up, so we address the issue by
    # running dhclient -6 in a loop.  See https://launchpad.net/bugs/1447715
    for iface in sorted(unconfigured_ifaces_4):
        call(["dhclient", "-nw", "-4", iface])
    for iface in sorted(unconfigured_ifaces_6):
        iface_str = iface.decode('utf-8')
        Popen([
            "sh", "-c",
            "while ! dhclient -6 %s; do sleep .05; done" % iface_str])
        # Ignore return value and continue running dhclient on the
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


LIST_MODALIASES_OUTPUT_NAME = '00-maas-04-list-modaliases'
LIST_MODALIASES_SCRIPT = dedent("""\
    #!/bin/bash
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
    import sys
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

    running_dir = os.path.dirname(__file__)
    # Results are stored differently when being run as part of node
    # commissioning vs controller refresh.
    virtuality_result_paths = [
        os.path.join(running_dir, '..', '..', 'out', '00-maas-02-virtuality'),
        os.path.join(running_dir, 'out', '00-maas-02-virtuality'),
    ]
    # This script doesn't work in containers as they don't have any block
    # device. If the virtuality script detected its in one don't report
    # anything.
    for virtuality_result_path in virtuality_result_paths:
        if not os.path.exists(virtuality_result_path):
            continue
        virtuality_result = open(virtuality_result_path, 'r').read().strip()
        # Names from man SYSTEMD-DETECT-VIRT(1)
        if virtuality_result in {
                'openvz', 'lxc', 'lxc-libvirt', 'systemd-nspawn', 'docker',
                'rkt'}:
            print(
                'Unable to detect block devices while running in container!',
                file=sys.stderr)
            print('[]')
            return

    # Grab the block devices from lsblk. Excludes RAM devices
    # (default for lsblk), floppy disks, and loopback devices.
    blockdevs = []
    block_list = check_output((
        "lsblk", "--exclude", "1,2,7", "-d", "-P",
        "-o", "NAME,RO,RM,MODEL,ROTA,MAJ:MIN", "-x", "MAJ:MIN"))
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
            ("sudo", "-n", "blockdev", "--getsize64", block_path))
        device_block_size = check_output(
            ("sudo", "-n", "blockdev", "--getbsz", block_path))
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
    ('00-maas-00-support-info', {
        'content': SUPPORT_SCRIPT.encode('ascii'),
        'hook': null_hook,
        'run_on_controller': True,
    }),
    (LSHW_OUTPUT_NAME, {
        'content': LSHW_SCRIPT.encode('ascii'),
        'hook': null_hook,
        'run_on_controller': True,
    }),
    ('00-maas-01-cpuinfo', {
        'content': CPUINFO_SCRIPT.encode('ascii'),
        'hook': null_hook,
        'run_on_controller': True,
    }),
    ('00-maas-02-virtuality', {
        'content': VIRTUALITY_SCRIPT.encode('ascii'),
        'hook': null_hook,
        'run_on_controller': True,
    }),
    ('00-maas-03-install-lldpd', {
        'content': make_function_call_script(
            lldpd_install, config_file="/etc/default/lldpd"),
        'hook': null_hook,
        'run_on_controller': False,
    }),
    (LIST_MODALIASES_OUTPUT_NAME, {
        'content': LIST_MODALIASES_SCRIPT.encode('ascii'),
        'hook': null_hook,
        'run_on_controller': True,
    }),
    ('00-maas-06-dhcp-unconfigured-ifaces', {
        'content': make_function_call_script(dhcp_explore),
        'hook': null_hook,
        'run_on_controller': False,
    }),
    ('00-maas-07-block-devices', {
        'content': make_function_call_script(gather_physical_block_devices),
        'hook': null_hook,
        'run_on_controller': True,
    }),
    ('00-maas-08-serial-ports', {
        'content': SERIAL_PORTS_SCRIPT.encode('ascii'),
        'hook': null_hook,
        'run_on_controller': True,
    }),
    ('99-maas-01-wait-for-lldpd', {
        'content': make_function_call_script(
            lldpd_wait, "/var/run/lldpd.socket", time_delay=60),
        'hook': null_hook,
        'run_on_controller': False,
    }),
    (LLDP_OUTPUT_NAME, {
        'content': make_function_call_script(lldpd_capture),
        'hook': null_hook,
        'run_on_controller': False,
    }),
    ('99-maas-03-network-interfaces', {
        'content': IPADDR_SCRIPT.encode('ascii'),
        'hook': null_hook,
        'run_on_controller': False,
    }),
    ('99-maas-04-network-interfaces-with-sriov', {
        'content': SRIOV_SCRIPT.encode('ascii'),
        'hook': null_hook,
        'run_on_controller': False,
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
