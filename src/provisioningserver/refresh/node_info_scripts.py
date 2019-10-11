# Copyright 2016-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Builtin node info scripts."""

__all__ = [
    "DHCP_EXPLORE_OUTPUT_NAME",
    "GET_FRUID_DATA_OUTPUT_NAME",
    "IPADDR_OUTPUT_NAME",
    "KERNEL_CMDLINE_OUTPUT_NAME",
    "LIST_MODALIASES_OUTPUT_NAME",
    "LLDP_INSTALL_OUTPUT_NAME",
    "LLDP_OUTPUT_NAME",
    "LSHW_OUTPUT_NAME",
    "LXD_OUTPUT_NAME",
    "NODE_INFO_SCRIPTS",
    "SERIAL_PORTS_OUTPUT_NAME",
    "SUPPORT_INFO_OUTPUT_NAME",
    "VIRTUALITY_OUTPUT_NAME",
]

from collections import OrderedDict
from datetime import timedelta
from inspect import getsource
import json
import os
from textwrap import dedent

# The name of the script, used throughout MAAS for data processing. Any script
# which is renamed will require a migration otherwise the user will see both
# the old name and new name as two seperate scripts. See
# 0014_rename_dhcp_unconfigured_ifaces.py
SUPPORT_INFO_OUTPUT_NAME = "00-maas-00-support-info"
LSHW_OUTPUT_NAME = "00-maas-01-lshw"
VIRTUALITY_OUTPUT_NAME = "00-maas-02-virtuality"
LLDP_INSTALL_OUTPUT_NAME = "00-maas-03-install-lldpd"
LIST_MODALIASES_OUTPUT_NAME = "00-maas-04-list-modaliases"
DHCP_EXPLORE_OUTPUT_NAME = "00-maas-05-dhcp-unconfigured-ifaces"
GET_FRUID_DATA_OUTPUT_NAME = "00-maas-06-get-fruid-api-data"
SERIAL_PORTS_OUTPUT_NAME = "00-maas-08-serial-ports"
IPADDR_OUTPUT_NAME = "40-maas-01-network-interfaces"
LXD_OUTPUT_NAME = "50-maas-01-commissioning"
LLDP_OUTPUT_NAME = "99-maas-01-capture-lldp"
KERNEL_CMDLINE_OUTPUT_NAME = "99-maas-05-kernel-cmdline"


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
    template = dedent(
        """\
    #!/usr/bin/python3
    # -*- coding: utf-8 -*-

    import json

    {function_source}

    if __name__ == '__main__':
        args = json.loads({function_args!r})
        kwargs = json.loads({function_kwargs!r})
        {function_name}(*args, **kwargs)
    """
    )
    script = template.format(
        function_name=function.__name__,
        function_source=dedent(getsource(function)).strip(),
        function_args=json.dumps(args),  # ASCII.
        function_kwargs=json.dumps(kwargs),  # ASCII.
    )
    return script.encode("utf-8")


# Built-in script to run lshw. This script runs both on the controller and
# on a commissioning machine. So the script must check itself if its running
# within a snap.
LSHW_SCRIPT = dedent(
    """\
    #!/bin/bash
    if [ -z "$SNAP" ]; then
        sudo -n /usr/bin/lshw -xml
    else
        $SNAP/usr/bin/lshw -xml
    fi
    """
)

LXD_SCRIPT = dedent(
    """\
    #!/bin/bash -e

    # When booting into the ephemeral environment root filesystem
    # is the retrieved from the rack controller.
    for i in $(cat /proc/cmdline); do
        arg=$(echo $i | cut -d '=' -f1)
        if [ "$arg" == "root" ]; then
            value=$(echo $i | cut -d '=' -f2-)
            # MAAS normally specifies the file has "filetype:url"
            filetype=$(echo $value | cut -d ':' -f1)
            if [ "$filetype" == "squash" ]; then
                url=$(echo $value | cut -d ':' -f2-)
            else
                url=$filetype
            fi
            break
        fi
    done

    # Get only the protocol, hostname, and port.
    url=$(echo "$url" | awk -F '/' ' { print $1 "//" $3 } ')

    if [ -z "$url" ] || $(echo "$url" | grep -vq "://"); then
        echo "ERROR: Unable to find rack controller URL!"
        exit 1
    fi

    BINARY="$(archdetect | cut -d '/' -f1 | sed 's/i386/386/g')"
    wget $url/machine-resources/$BINARY -O $DOWNLOAD_PATH/$BINARY 1>&2
    chmod +x $DOWNLOAD_PATH/$BINARY
    $DOWNLOAD_PATH/$BINARY
    """
)

# Built-in script to run `ip addr`
IPADDR_SCRIPT = dedent(
    """\
    #!/bin/bash
    ip addr
    """
)

# Built-in script to detect virtual instances.
VIRTUALITY_SCRIPT = dedent(
    """\
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
    """
)

SERIAL_PORTS_SCRIPT = dedent(
    """\
    #!/bin/bash
    find /sys/class/tty/ ! -type d -print0 2> /dev/null \
        | xargs -0 readlink -f \
        | sort -u
    # Do not fail commissioning if this fails.
    exit 0
    """
)

KERNEL_CMDLINE_SCRIPT = dedent(
    """\
    #!/bin/bash
    cat /proc/cmdline
    """
)

SUPPORT_SCRIPT = dedent(
    r"""#!/bin/bash
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
        # Filter out any base64 strings having to do with secrets or keys.
        curl -LSsv "$URL" 2>&1 | \
            sed '/_key: \|_secret: /'`
               `'s/: [a-zA-Z0-9/+=]\{12,128\}/: (withheld)/g'
        echo "-----END CLOUD CONFIG QUERY-----"
    fi
    echo ""
    echo "-----BEGIN CPU CORE COUNT AND MODEL-----"
    cat /proc/cpuinfo | grep '^model name' | cut -d: -f 2- | sort | uniq -c
    echo "-----BEGIN CPU CORE COUNT AND MODEL-----"
    if [ -x "$(which lspci)" ]; then
        echo ""
        echo "-----BEGIN PCI INFO-----"
        lspci -nn
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
    find /sys/devices/ -name modalias -print0 2> /dev/null | xargs -0 cat \
        | sort | uniq -c
    echo "-----END MODALIASES-----"
    echo ""
    echo "-----BEGIN SERIAL PORTS-----"
    find /sys/class/tty/ ! -type d -print0 2> /dev/null \
        | xargs -0 readlink -f \
        | sort -u | egrep -v 'devices/virtual|devices/platform'
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
        # Do not fail commissioning if this fails.
        exit 0
    fi
    if [ -x "$(which lsblk)" ]; then
        echo ""
        echo "-----BEGIN DETAILED BLOCK DEVICE INFO-----"
        # Note: excluding ramdisks, floppy drives, and loopback devices.
        lsblk --exclude 1,2,7 -d -P -x MAJ:MIN
        echo ""
        for dev in $(lsblk -n --exclude 1,2,7 --output KNAME); do
            if [ ! -e "/dev/$dev" ]; then
                # disk devices are not present in LXD containers
                echo "$dev device node not found, skipping"
                continue
            fi
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
        # (/dev/disk is not present in LXD containers, so skip in that case)
        if [ -d /dev/disk ]; then
            find /dev/disk -type l | xargs ls -ln \
                | awk '{ print $9, $10, $11 }' | sort -k2
        fi
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
    """
)


# Run `dhclient` on all the unconfigured interfaces.
# This is done to create records in the leases file for the
# NICs attached to unconfigured interfaces.  This way the leases
# parser will be able to connect these NICs and the networks
# MAAS knows about.
def dhcp_explore():
    from subprocess import call, check_output, Popen

    def get_iface_list(ifconfig_output):
        return [
            line.split()[1].split(b":")[0].split(b"@")[0]
            for line in ifconfig_output.splitlines()
        ]

    def has_ipv4_address(iface):
        output = check_output(("ip", "-4", "addr", "list", "dev", iface))
        for line in output.splitlines():
            if line.find(b" inet ") >= 0:
                return True
        return False

    def has_ipv6_address(iface):
        no_ipv6_found = True
        output = check_output(("ip", "-6", "addr", "list", "dev", iface))
        for line in output.splitlines():
            if line.find(b" inet6 ") >= 0:
                if line.find(b" inet6 fe80:") == -1:
                    return True
                no_ipv6_found = False
        # Bug 1640147: If there is no IPv6 address, then we consider this to be
        # a configured ipv6 interface, since ipv6 won't work there.
        return no_ipv6_found

    all_ifaces = get_iface_list(check_output(("ip", "-o", "link", "show")))
    configured_ifaces = get_iface_list(
        check_output(("ip", "-o", "link", "show", "up"))
    )
    configured_ifaces_4 = [
        iface for iface in configured_ifaces if has_ipv4_address(iface)
    ]
    configured_ifaces_6 = [
        iface for iface in configured_ifaces if has_ipv6_address(iface)
    ]
    unconfigured_ifaces_4 = set(all_ifaces) - set(configured_ifaces_4)
    unconfigured_ifaces_6 = set(all_ifaces) - set(configured_ifaces_6)
    # Run dhclient in the background to avoid blocking node_info.  We need to
    # run two dhclient processes (one for IPv6 and one for IPv4) and IPv6 will
    # run into issues if the link-local address has not finished
    # conflict-detection before it starts.  This is complicated by interaction
    # with dhclient -4 bringing the interface up, so we address the issue by
    # running dhclient -6 in a loop that only tries 10 times.  Per RFC 5227,
    # conflict-detection could take as long as 9 seconds, so we sleep 10.
    # See https://launchpad.net/bugs/1447715
    for iface in sorted(unconfigured_ifaces_4):
        call(["dhclient", "-nw", "-4", iface])
    for iface in sorted(unconfigured_ifaces_6):
        iface_str = iface.decode("utf-8")
        Popen(
            [
                "sh",
                "-c",
                "for idx in $(seq 10); do"
                " dhclient -6 %s && break || sleep 10; done" % iface_str,
            ]
        )
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
    from subprocess import check_call
    from codecs import open

    with open(config_file, "a", "ascii") as fd:
        fd.write("\n")  # Ensure there's a newline.
        fd.write("# Configured by MAAS:\n")
        fd.write('DAEMON_ARGS="-c -f -s -e -r"\n')
    check_call(("systemctl", "restart", "lldpd"))


# This function must be entirely self-contained. It must not use
# variables or imports from the surrounding scope.
def lldpd_capture(reference_file, time_delay):
    """Wait until `lldpd` has been running for `time_delay` seconds.

    On an Ubuntu system, `reference_file` is typically `lldpd`'s UNIX
    socket in `/var/run`. After waiting capture any output.

    """
    from os.path import getmtime
    from time import sleep, time
    from subprocess import check_call

    time_ref = getmtime(reference_file)
    time_remaining = time_ref + time_delay - time()
    if time_remaining > 0:
        # LP:1801152 - If the hardware clock is in the future when
        # 00-maas-03-install-lldpd runs and NTP corrects the clock
        # before this script runs time_remaining will be more then
        # the time_delay which may cause this script to timeout.
        sleep(min(time_remaining, time_delay))
    check_call(("lldpctl", "-f", "xml"))


LIST_MODALIASES_SCRIPT = dedent(
    """\
    #!/bin/bash
    find /sys/devices/ -name modalias -print0 | xargs -0 cat | sort -u
    """
)


GET_FRUID_DATA_SCRIPT = dedent(
    """\
    #!/bin/bash -x
    # Wait for interfaces to settle and get their IPs after the DHCP job.
    sleep 5
    for ifname in $(ls /sys/class/net); do
        if [ "$ifname" != "lo" ]; then
            curl --max-time 1 -s -f \
                "http://fe80::1%$ifname:8080/api/sys/mb/fruid"
        fi
    done
    # Do not fail commissioning if this fails.
    exit 0
    """
)


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
# metadataserver/builtin_scripts/hooks.py
#
# maasserver/status_monitor.py adds 1 minute to the timeout of all scripts for
# cleanup and signaling.
NODE_INFO_SCRIPTS = OrderedDict(
    [
        (
            SUPPORT_INFO_OUTPUT_NAME,
            {
                "content": SUPPORT_SCRIPT.encode("ascii"),
                "hook": null_hook,
                "timeout": timedelta(minutes=5),
                "run_on_controller": True,
            },
        ),
        (
            LSHW_OUTPUT_NAME,
            {
                "content": LSHW_SCRIPT.encode("ascii"),
                "hook": null_hook,
                "timeout": timedelta(minutes=5),
                "run_on_controller": True,
            },
        ),
        (
            LXD_OUTPUT_NAME,
            {
                "content": LXD_SCRIPT.encode("ascii"),
                "hook": null_hook,
                "packages": {"apt": ["archdetect-deb"]},
                "timeout": timedelta(minutes=1),
                "run_on_controller": True,
            },
        ),
        (
            VIRTUALITY_OUTPUT_NAME,
            {
                "content": VIRTUALITY_SCRIPT.encode("ascii"),
                "hook": null_hook,
                "timeout": timedelta(seconds=10),
                "run_on_controller": True,
            },
        ),
        (
            LLDP_INSTALL_OUTPUT_NAME,
            {
                "content": make_function_call_script(
                    lldpd_install, config_file="/etc/default/lldpd"
                ),
                "hook": null_hook,
                "packages": {"apt": ["lldpd"]},
                "timeout": timedelta(minutes=10),
                "run_on_controller": False,
            },
        ),
        (
            LIST_MODALIASES_OUTPUT_NAME,
            {
                "content": LIST_MODALIASES_SCRIPT.encode("ascii"),
                "hook": null_hook,
                "timeout": timedelta(seconds=10),
                "run_on_controller": True,
            },
        ),
        (
            DHCP_EXPLORE_OUTPUT_NAME,
            {
                "content": make_function_call_script(dhcp_explore),
                "hook": null_hook,
                "timeout": timedelta(minutes=5),
                "run_on_controller": False,
            },
        ),
        (
            GET_FRUID_DATA_OUTPUT_NAME,
            {
                "content": GET_FRUID_DATA_SCRIPT.encode("ascii"),
                "hook": null_hook,
                "timeout": timedelta(minutes=1),
                "run_on_controller": False,
            },
        ),
        (
            KERNEL_CMDLINE_OUTPUT_NAME,
            {
                "content": KERNEL_CMDLINE_SCRIPT.encode("ascii"),
                "hook": null_hook,
                "timeout": timedelta(seconds=10),
                "run_on_controller": False,
            },
        ),
        (
            SERIAL_PORTS_OUTPUT_NAME,
            {
                "content": SERIAL_PORTS_SCRIPT.encode("ascii"),
                "hook": null_hook,
                "timeout": timedelta(seconds=10),
                "run_on_controller": True,
            },
        ),
        (
            LLDP_OUTPUT_NAME,
            {
                "content": make_function_call_script(
                    lldpd_capture, "/var/run/lldpd.socket", time_delay=60
                ),
                "hook": null_hook,
                "timeout": timedelta(minutes=3),
                "run_on_controller": False,
            },
        ),
        (
            IPADDR_OUTPUT_NAME,
            {
                "content": IPADDR_SCRIPT.encode("ascii"),
                "hook": null_hook,
                "timeout": timedelta(seconds=10),
                "run_on_controller": False,
            },
        ),
    ]
)


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
