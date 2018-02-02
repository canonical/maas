# Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test node info scripts."""

__all__ = []

from inspect import getsource
from io import StringIO
import json
import os.path
from pathlib import Path
import random
import subprocess
from subprocess import (
    CalledProcessError,
    check_output,
    STDOUT,
)
import sys
from textwrap import dedent
import time
from unittest.mock import call

from fixtures import EnvironmentVariableFixture
from maastesting.factory import factory
from maastesting.fixtures import TempDirectory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
)
from maastesting.testcase import MAASTestCase
from provisioningserver.refresh import node_info_scripts as node_info_module
from provisioningserver.refresh.node_info_scripts import (
    make_function_call_script,
    VIRTUALITY_SCRIPT,
)
from provisioningserver.utils import typed
from provisioningserver.utils.shell import get_env_with_locale
from testtools.content import text_content
from testtools.matchers import (
    Equals,
    HasLength,
    MatchesAny,
    Not,
)


class TestMakeFunctionCallScript(MAASTestCase):

    def run_script(self, script):
        script_filename = self.make_file("test.py", script)
        os.chmod(script_filename, 0o700)
        try:
            return check_output((script_filename,), stderr=STDOUT)
        except CalledProcessError as error:
            self.addDetail("output", text_content(
                error.output.decode("ascii", "replace")))
            raise

    def test_basic(self):
        def example_function():
            print("Hello, World!", end="")
        script = make_function_call_script(example_function)
        self.assertEqual(b"Hello, World!", self.run_script(script))

    def test_positional_args_get_passed_through(self):
        def example_function(a, b):
            print("a=%s, b=%d" % (a, b), end="")
        script = make_function_call_script(example_function, "foo", 12345)
        self.assertEqual(b"a=foo, b=12345", self.run_script(script))

    def test_keyword_args_get_passed_through(self):
        def example_function(a, b):
            print("a=%s, b=%d" % (a, b), end="")
        script = make_function_call_script(example_function, a="foo", b=12345)
        self.assertEqual(b"a=foo, b=12345", self.run_script(script))

    def test_positional_and_keyword_args_get_passed_through(self):
        def example_function(a, b):
            print("a=%s, b=%d" % (a, b), end="")
        script = make_function_call_script(example_function, "foo", b=12345)
        self.assertEqual(b"a=foo, b=12345", self.run_script(script))

    def test_non_ascii_positional_args_are_passed_without_corruption(self):
        def example_function(text):
            from sys import stdout
            stdout.buffer.write(text.encode("utf-8"))
        script = make_function_call_script(example_function, "abc\u1234")
        self.assertEqual("abc\u1234", self.run_script(script).decode("utf-8"))

    def test_non_ascii_keyword_args_are_passed_without_corruption(self):
        def example_function(text):
            from sys import stdout
            stdout.buffer.write(text.encode("utf-8"))
        script = make_function_call_script(example_function, text="abc\u1234")
        self.assertEqual("abc\u1234", self.run_script(script).decode("utf-8"))

    def test_structured_arguments_are_passed_though_too(self):
        # Anything that can be JSON serialized can be passed.
        def example_function(arg):
            if arg == {"123": "foo", "bar": [4, 5, 6]}:
                print("Equal")
            else:
                print("Unequal, got %s" % repr(arg))
        script = make_function_call_script(
            example_function, {"123": "foo", "bar": [4, 5, 6]})
        self.assertEqual(b"Equal\n", self.run_script(script))


def isolate_function(function, namespace=None):
    """Recompile the given function in the given namespace.

    :param namespace: A dict to use as the namespace. If not provided, and
        empty namespace will be used.
    """
    source = dedent(getsource(function))
    modcode = compile(source, "isolated.py", "exec")
    namespace = {} if namespace is None else namespace
    if '__file__' not in namespace:
        namespace['__file__'] = __file__
    exec(modcode, namespace)
    return namespace[function.__name__]


class TestLLDPScripts(MAASTestCase):

    def test_install_script_installs_configures_and_restarts_upstart(self):
        config_file = self.make_file("config", "# ...")
        check_call = self.patch(subprocess, "check_call")
        self.patch(os.path, "isdir").return_value = False
        lldpd_install = isolate_function(node_info_module.lldpd_install)
        lldpd_install(config_file)
        # lldpd is installed and restarted.
        self.assertEqual(
            check_call.call_args_list,
            [
                call(("initctl", "reload-configuration")),
                call(("service", "lldpd", "restart"))
            ])
        # lldpd's config was updated to include an updated DAEMON_ARGS
        # setting. Note that the new comment is on a new line, and
        # does not interfere with existing config.
        config_expected = dedent("""\
            # ...
            # Configured by MAAS:
            DAEMON_ARGS="-c -f -s -e -r"
            """).encode("ascii")
        with open(config_file, "rb") as fd:
            config_observed = fd.read()
        self.assertEqual(config_expected, config_observed)

    def test_install_script_installs_configures_and_restarts_systemd(self):
        config_file = self.make_file("config", "# ...")
        check_call = self.patch(subprocess, "check_call")
        self.patch(os.path, "isdir").return_value = True
        lldpd_install = isolate_function(node_info_module.lldpd_install)
        lldpd_install(config_file)
        # lldpd is installed and restarted.
        self.assertEqual(
            check_call.call_args_list,
            [
                call(("systemctl", "restart", "lldpd")),
            ])
        # lldpd's config was updated to include an updated DAEMON_ARGS
        # setting. Note that the new comment is on a new line, and
        # does not interfere with existing config.
        config_expected = dedent("""\
            # ...
            # Configured by MAAS:
            DAEMON_ARGS="-c -f -s -e -r"
            """).encode("ascii")
        with open(config_file, "rb") as fd:
            config_observed = fd.read()
        self.assertEqual(config_expected, config_observed)

    def test_capture_lldpd_script_waits_for_lldpd(self):
        reference_file = self.make_file("reference")
        time_delay = 8.98  # seconds
        lldpd_capture = isolate_function(node_info_module.lldpd_capture)
        # Do the patching as late as possible, because the setup may call
        # one of the patched functions somewhere in the plumbing.  We've had
        # spurious test failures over this: bug 1283918.
        self.patch(os.path, "getmtime").return_value = 10.65
        self.patch(time, "time").return_value = 14.12
        self.patch(time, "sleep")
        self.patch(subprocess, "check_call")

        lldpd_capture(reference_file, time_delay)

        # lldpd_wait checks the mtime of the reference file,
        self.assertThat(os.path.getmtime, MockCalledOnceWith(reference_file))
        # and gets the current time,
        self.assertThat(time.time, MockCalledOnceWith())
        # then sleeps until time_delay seconds has passed since the
        # mtime of the reference file.
        self.assertThat(time.sleep, MockCalledOnceWith(
            os.path.getmtime.return_value + time_delay -
            time.time.return_value))

    def test_capture_lldpd_calls_lldpdctl(self):
        reference_file = self.make_file("reference")
        check_call = self.patch(subprocess, "check_call")
        lldpd_capture = isolate_function(node_info_module.lldpd_capture)
        lldpd_capture(reference_file, 0.0)
        self.assertEqual(
            check_call.call_args_list,
            [call(("lldpctl", "-f", "xml"))])


# The two following example outputs differ because eth2 and eth1 are not
# configured and thus 'ifconfig -s -a' returns a list with both 'eth1'
# and 'eth2' while 'ifconfig -s' does not contain them.

# Example output of 'ifconfig -s -a':
ifconfig_all = b"""\
Iface   MTU Met   RX-OK RX-ERR RX-DRP RX-OVR    TX-OK TX-ERR TX-DRP
eth2       1500 0         0      0      0 0             0      0
eth1       1500 0         0      0      0 0             0      0
eth0       1500 0   1366127      0      0 0        831110      0
eth4       1500 0         0      0      0 0             0      0
eth5       1500 0         0      0      0 0             0      0
eth6       1500 0         0      0      0 0             0      0
lo        65536 0     38075      0      0 0         38075      0
virbr0     1500 0         0      0      0 0             0      0
wlan0      1500 0   2304695      0      0 0       1436049      0
"""

# Example output of 'ifconfig -s':
ifconfig_config = b"""\
Iface   MTU Met   RX-OK RX-ERR RX-DRP RX-OVR    TX-OK TX-ERR TX-DRP
eth0       1500 0   1366127      0      0 0        831110      0
eth4       1500 0   1366127      0      0 0        831110      0
eth5       1500 0   1366127      0      0 0        831110      0
eth6       1500 0   1366127      0      0 0        831110      0
lo        65536 0     38115      0      0 0         38115      0
virbr0     1500 0         0      0      0 0             0      0
wlan0      1500 0   2304961      0      0 0       1436319      0
"""

# Example output of 'ip addr list dev XX':
ip_eth0 = b"""\
3: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP ...
    link/ether 00:01:02:03:04:03 brd ff:ff:ff:ff:ff:ff
    inet 192.168.0.1/24 brd 192.168.0.255 scope global eth0
       valid_lft forever preferred_lft forever
    inet6 2001:db8::32/64 scope global
       valid_lft forever preferred_lft forever
    inet6 fe80::0201:02ff:fe03:0403/64 scope link
       valid_lft forever preferred_lft forever
"""
ip_eth4 = b"""\
4: eth4: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP ...
    link/ether 00:01:02:03:04:04 brd ff:ff:ff:ff:ff:ff
    inet 192.168.4.1/24 brd 192.168.4.255 scope global eth4
       valid_lft forever preferred_lft forever
    inet6 fe80::0201:02ff:fe03:0404/64 scope link
       valid_lft forever preferred_lft forever
"""
ip_eth5 = b"""\
6: eth5: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP ...
    link/ether 00:01:02:03:04:06 brd ff:ff:ff:ff:ff:ff
    inet 192.168.5.1/24 brd 192.168.4.255 scope global eth4
       valid_lft forever preferred_lft forever
"""
ip_eth6 = b"""\
6: eth6: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP ...
    link/ether 00:01:02:03:04:06 brd ff:ff:ff:ff:ff:ff
    inet6 2001:db8:0:6::32/64 scope global
       valid_lft forever preferred_lft forever
    inet6 fe80::0201:02ff:fe03:0406/64 scope link
       valid_lft forever preferred_lft forever
"""
ip_lo = b"""\
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN ...
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
    inet6 ::1/128 scope host
       valid_lft forever preferred_lft forever
"""
ip_virbr0 = b"""\
2: virbr0: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN ...
    link/ether 00:01:02:03:04:02 brd ff:ff:ff:ff:ff:ff
    inet 192.168.122.1/24 brd 192.168.122.255 scope global virbr0
       valid_lft forever preferred_lft forever
    inet6 fe80::0201:02ff:fe03:0402/64 scope link
       valid_lft forever preferred_lft forever
"""
ip_wlan0 = b"""\
5: wlan0: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN ...
    link/ether 00:01:02:03:04:05 brd ff:ff:ff:ff:ff:ff
    inet 192.168.3.1/24 brd 192.168.3.255 scope global virbr0
       valid_lft forever preferred_lft forever
    inet6 fe80::0201:02ff:fe03:0405/64 scope link
       valid_lft forever preferred_lft forever
"""


DHCP6_TEMPLATE = (
    "for idx in $(seq 10); do dhclient -6 %s && break || sleep 10; done")


class TestDHCPExplore(MAASTestCase):

    def test_calls_dhclient_on_unconfigured_interfaces(self):
        check_output = self.patch(subprocess, "check_output")
        check_output.side_effect = [
            ifconfig_all, ifconfig_config,
            ip_eth0, ip_eth4, ip_eth5, ip_eth6, ip_lo, ip_virbr0, ip_wlan0,
            ip_eth0, ip_eth4, ip_eth5, ip_eth6, ip_lo, ip_virbr0, ip_wlan0
            ]
        mock_call = self.patch(subprocess, "call")
        mock_popen = self.patch(subprocess, "Popen")
        dhcp_explore = isolate_function(node_info_module.dhcp_explore)
        dhcp_explore()
        self.assertThat(
            mock_call,
            MockCallsMatch(
                call(["dhclient", "-nw", "-4", b"eth1"]),
                call(["dhclient", "-nw", "-4", b"eth2"]),
                call(["dhclient", "-nw", "-4", b"eth6"])))
        self.assertThat(
            mock_popen,
            MockCallsMatch(
                call(["sh", "-c", DHCP6_TEMPLATE % "eth1"]),
                call(["sh", "-c", DHCP6_TEMPLATE % "eth2"]),
                call(["sh", "-c", DHCP6_TEMPLATE % "eth4"]),
                call(["sh", "-c", DHCP6_TEMPLATE % "virbr0"]),
                call(["sh", "-c", DHCP6_TEMPLATE % "wlan0"])))


class TestGatherPhysicalBlockDevices(MAASTestCase):

    @typed
    def make_lsblk_output(
            self, name=None, read_only=False, removable=False,
            model=None, rotary=True, maj_min=None) -> bytes:
        if name is None:
            name = factory.make_name('name')
        if model is None:
            model = factory.make_name('model')
        if maj_min is None:
            maj_min = (random.randint(0, 255), random.randint(0, 255))
        read_only = "1" if read_only else "0"
        removable = "1" if removable else "0"
        rotary = "1" if rotary else "0"
        output = (
            'NAME="%s" RO="%s" RM="%s" MODEL="%s" ROTA="%s" MAJ:MIN="%s"' % (
                name, read_only, removable, model, rotary, '%s:%s' % maj_min))
        return output.encode("ascii")

    @typed
    def make_udevadm_output(
            self, name, serial=None, sata=True, cdrom=False,
            dev='/dev', firmware_version=None) -> bytes:
        if serial is None:
            serial = factory.make_name('serial')
        if firmware_version is None:
            firmware_version = factory.make_name('firmware_version')
        sata = "1" if sata else "0"
        output = dedent("""\
            P: /devices/pci0000:00/ata3/host2/target2:0:0/2:0:0:0/block/{name}
            N: {name}
            E: DEVNAME={dev}/{name}
            E: DEVTYPE=disk
            E: ID_ATA_SATA={sata}
            E: ID_SERIAL_SHORT={serial}
            E: ID_REVISION={firmware_version}
            """).format(dev=os.path.abspath(dev), name=name,
                        serial=serial, sata=sata,
                        firmware_version=firmware_version)
        if cdrom:
            output += "E: ID_CDROM=1"
        else:
            output += "E: ID_ATA_ROTATION_RATE_RPM=5400"
        return output.encode("ascii")

    def call_gather_physical_block_devices(
            self, dev_disk_byid='/dev/disk/by-id/', file_path=None):
        output = StringIO()

        def neutered_print(*args, **kwargs):
            file = kwargs.pop('file', None)
            if file is not None and file == sys.stderr:
                return
            return print(*args, **kwargs, file=output)

        namespace = {"print": neutered_print}
        if file_path is not None:
            namespace['__file__'] = file_path
        gather_physical_block_devices = isolate_function(
            node_info_module.gather_physical_block_devices, namespace)
        gather_physical_block_devices(dev_disk_byid=dev_disk_byid)
        return json.loads(output.getvalue())

    def make_output(
            self, name, maj_min, model, serial, size, block_size,
            firmware_version, drive_path=None, device_id_path=None,
            rotary=True, removable=False, read_only=False, sata=True):
        if drive_path is None:
            drive_path = '/dev/%s' % name
        ret = {
            'NAME': name,
            'PATH': drive_path,
            'MAJ:MIN': '%s:%s' % maj_min,
            'RO': '1' if read_only else '0',
            'RM': '1' if removable else '0',
            'MODEL': model,
            'ROTA': '1' if rotary else '0',
            'SATA': '1' if sata else '0',
            'SERIAL': serial,
            'SIZE': str(size),
            'BLOCK_SIZE': str(block_size),
            'RPM': '5400',
            'FIRMWARE_VERSION': firmware_version,
        }
        if device_id_path is not None:
            ret['ID_PATH'] = device_id_path
        return ret

    def test__calls_lsblk(self):
        check_output = self.patch(subprocess, "check_output")
        check_output.return_value = b""
        self.call_gather_physical_block_devices()
        self.assertThat(check_output, MockCalledOnceWith((
            "lsblk", "--exclude", "1,2,7", "-d", "-P",
            "-o", "NAME,RO,RM,MODEL,ROTA,MAJ:MIN")))

    def test__returns_empty_list_when_no_disks(self):
        check_output = self.patch(subprocess, "check_output")
        check_output.return_value = b""
        self.assertEqual([], self.call_gather_physical_block_devices())

    def test__calls_lsblk_then_udevadm(self):
        name = factory.make_name('name')
        check_output = self.patch(subprocess, "check_output")
        check_output.side_effect = [
            self.make_lsblk_output(
                name=name),
            self.make_udevadm_output(
                name, cdrom=True),
            ]
        self.call_gather_physical_block_devices()
        self.assertThat(check_output, MockCallsMatch(
            call((
                "lsblk", "--exclude", "1,2,7", "-d", "-P",
                "-o", "NAME,RO,RM,MODEL,ROTA,MAJ:MIN")),
            call(("udevadm", "info", "-q", "all", "-n", name))))

    def test__returns_empty_list_when_cdrom_only(self):
        name = factory.make_name('name')
        check_output = self.patch(subprocess, "check_output")
        check_output.side_effect = [
            self.make_lsblk_output(
                name=name),
            self.make_udevadm_output(
                name, cdrom=True),
            ]
        self.assertEqual([], self.call_gather_physical_block_devices())

    def test__calls_lsblk_udevadm_then_blockdev(self):
        name = factory.make_name('name')
        model = factory.make_name('model')
        serial = factory.make_name('serial')
        size = random.randint(3000 * 1000, 1000 * 1000 * 1000)
        block_size = random.choice([512, 1024, 4096])

        check_output = self.patch(subprocess, "check_output")
        check_output.side_effect = [
            self.make_lsblk_output(name=name, model=model),
            self.make_udevadm_output(name, serial=serial),
            b'%d' % size,
            b'%d' % block_size,
            ]
        self.call_gather_physical_block_devices()
        self.assertThat(check_output, MockCallsMatch(
            call((
                "lsblk", "--exclude", "1,2,7", "-d", "-P",
                "-o", "NAME,RO,RM,MODEL,ROTA,MAJ:MIN")),
            call(("udevadm", "info", "-q", "all", "-n", name)),
            call(("sudo", "-n", "blockdev", "--getsize64", "/dev/%s" % name)),
            call(("sudo", "-n", "blockdev", "--getbsz", "/dev/%s" % name))))

    def test__calls_lsblk_udevadm_then_blockdev_snap_without_sudo(self):
        self.useFixture(EnvironmentVariableFixture('SNAP', ''))
        name = factory.make_name('name')
        model = factory.make_name('model')
        serial = factory.make_name('serial')
        size = random.randint(3000 * 1000, 1000 * 1000 * 1000)
        block_size = random.choice([512, 1024, 4096])
        check_output = self.patch(subprocess, "check_output")
        check_output.side_effect = [
            self.make_lsblk_output(name=name, model=model),
            self.make_udevadm_output(name, serial=serial),
            b'%d' % size,
            b'%d' % block_size,
            ]
        self.call_gather_physical_block_devices()
        self.assertThat(check_output, MockCallsMatch(
            call((
                "lsblk", "--exclude", "1,2,7", "-d", "-P",
                "-o", "NAME,RO,RM,MODEL,ROTA,MAJ:MIN")),
            call(("udevadm", "info", "-q", "all", "-n", name)),
            call(("blockdev", "--getsize64", "/dev/%s" % name)),
            call(("blockdev", "--getbsz", "/dev/%s" % name))))

    def test__returns_sorted_block_devices(self):
        output = []
        check_output_side_effects = []
        # Create simulated /dev tree
        devroot = self.make_dir()
        os.mkdir(os.path.join(devroot, 'disk'))
        byidroot = os.path.join(devroot, 'disk', 'by_id')
        os.mkdir(byidroot)
        for _ in range(3):
            name = factory.make_name('name')
            model = factory.make_name('model')
            serial = factory.make_name('serial')
            size = random.randint(3000 * 1000, 1000 * 1000 * 1000)
            block_size = random.choice([512, 1024, 4096])
            maj_min = (random.randint(0, 255), random.randint(0, 255))
            firmware_version = factory.make_name('firmware_version')

            # Create simulated /dev tree
            drive_path = os.path.join(devroot, name)
            os.mknod(drive_path)
            device_id_path = os.path.join(
                byidroot, factory.make_name('deviceid'))
            os.symlink(drive_path, device_id_path)

            check_output_side_effects += [
                self.make_lsblk_output(
                    name=name, model=model, maj_min=maj_min),
                self.make_udevadm_output(
                    name, serial=serial, dev=devroot,
                    firmware_version=firmware_version),
                b'%d' % size,
                b'%d' % block_size,
            ]
            output.append(
                self.make_output(
                    name, maj_min, model, serial, size, block_size,
                    firmware_version, drive_path, device_id_path))

        check_output = self.patch(subprocess, "check_output")
        check_output.side_effect = check_output_side_effects

        for ref, out in zip(
                output, self.call_gather_physical_block_devices(byidroot)):
            self.assertDictEqual(ref, out)

    def test__removes_duplicate_block_device_same_serial_and_model(self):
        """Multipath disks get multiple IDs, but same serial/model is same
        device and should only be enumerated once."""
        name = factory.make_name('name')
        model = factory.make_name('model')
        serial = factory.make_name('serial')
        size = random.randint(3000 * 1000, 1000 * 1000 * 1000)
        block_size = random.choice([512, 1024, 4096])
        firmware_version = factory.make_name('firmware_version')
        maj_min = (random.randint(0, 255), random.randint(0, 255))
        check_output = self.patch(subprocess, "check_output")

        name2 = factory.make_name('name')

        # Create simulated /dev tree.
        devroot = self.make_dir()
        os.mkdir(os.path.join(devroot, 'disk'))
        byidroot = os.path.join(devroot, 'disk', 'by_id')
        os.mkdir(byidroot)

        drive_path = os.path.join(devroot, name)
        os.mknod(drive_path)
        device_id_path = os.path.join(byidroot, 'deviceid')
        os.symlink(os.path.join(devroot, name), device_id_path)

        os.mknod(os.path.join(devroot, name2))
        device_id_path2 = os.path.join(byidroot, 'deviceid2')
        os.symlink(os.path.join(devroot, name2), device_id_path2)

        check_output.side_effect = [
            b"\n".join([
                self.make_lsblk_output(
                    name=name, model=model, maj_min=maj_min),
                self.make_lsblk_output(
                    name=name2, model=model, maj_min=maj_min)]),
            self.make_udevadm_output(
                name, firmware_version=firmware_version, serial=serial,
                dev=devroot),
            self.make_udevadm_output(
                name2, firmware_version=firmware_version, serial=serial,
                dev=devroot),
            b'%d' % size,
            b'%d' % block_size,
            b'%d' % size,
            b'%d' % block_size,
        ]

        self.assertItemsEqual(
            [self.make_output(
                name, maj_min, model, serial, size, block_size,
                firmware_version, drive_path, device_id_path)],
            self.call_gather_physical_block_devices(byidroot))

    def test__keeps_block_device_same_serial_different_model(self):
        """Multipath disks get multiple IDs, but same serial is same device."""
        name = factory.make_name('name')
        model = factory.make_name('model')
        maj_min = (0, 0)
        serial = factory.make_name('serial')
        size = random.randint(3000 * 1000, 1000 * 1000 * 1000)
        firmware_version = factory.make_name('firmware_version')
        block_size = random.choice([512, 1024, 4096])
        check_output = self.patch(subprocess, "check_output")

        name2 = factory.make_name('name')
        model2 = factory.make_name('model')
        maj_min2 = (1, 1)

        # Create simulated /dev tree.
        devroot = self.make_dir()
        os.mkdir(os.path.join(devroot, 'disk'))
        byidroot = os.path.join(devroot, 'disk', 'by_id')
        os.mkdir(byidroot)

        drive_path = os.path.join(devroot, name)
        os.mknod(drive_path)
        device_id_path = os.path.join(byidroot, 'deviceid')
        os.symlink(os.path.join(devroot, name), device_id_path)

        drive_path2 = os.path.join(devroot, name2)
        os.mknod(drive_path2)
        device_id_path2 = os.path.join(byidroot, 'deviceid2')
        os.symlink(os.path.join(devroot, name2), device_id_path2)

        check_output.side_effect = [
            b"\n".join([
                self.make_lsblk_output(
                    name=name, model=model, maj_min=maj_min),
                self.make_lsblk_output(
                    name=name2, model=model2, maj_min=maj_min2)
                ]),
            self.make_udevadm_output(
                name, firmware_version=firmware_version, serial=serial,
                dev=devroot),
            self.make_udevadm_output(
                name2, firmware_version=firmware_version, serial=serial,
                dev=devroot),
            b'%d' % size,
            b'%d' % block_size,
            b'%d' % size,
            b'%d' % block_size,
        ]

        for ref, out in zip(
                [
                    self.make_output(
                        name, maj_min, model, serial, size, block_size,
                        firmware_version, drive_path, device_id_path),
                    self.make_output(
                        name2, maj_min2, model2, serial, size, block_size,
                        firmware_version, drive_path2, device_id_path2),
                ], self.call_gather_physical_block_devices(byidroot)):
            self.assertDictEqual(ref, out)

    def test__keeps_block_device_blank_serial_same_model(self):
        """Multipath disks get multiple IDs, but same serial is same device."""
        name = factory.make_name('name')
        model = factory.make_name('model')
        maj_min = (0, 0)
        serial = ''
        size = random.randint(3000 * 1000, 1000 * 1000 * 1000)
        block_size = random.choice([512, 1024, 4096])
        firmware_version = factory.make_name('firmware_version')
        check_output = self.patch(subprocess, "check_output")

        name2 = factory.make_name('name')
        maj_min2 = (1, 1)

        # Create simulated /dev tree.
        devroot = self.make_dir()
        os.mkdir(os.path.join(devroot, 'disk'))
        byidroot = os.path.join(devroot, 'disk', 'by_id')
        os.mkdir(byidroot)

        drive_path = os.path.join(devroot, name)
        os.mknod(drive_path)
        device_id_path = os.path.join(byidroot, 'deviceid')
        os.symlink(os.path.join(devroot, name), device_id_path)

        drive_path2 = os.path.join(devroot, name2)
        os.mknod(drive_path2)
        device_id_path2 = os.path.join(byidroot, 'deviceid2')
        os.symlink(os.path.join(devroot, name2), device_id_path2)

        check_output.side_effect = [
            b"\n".join([
                self.make_lsblk_output(
                    name=name, model=model, maj_min=maj_min),
                self.make_lsblk_output(
                    name=name2, model=model, maj_min=maj_min2)]),
            self.make_udevadm_output(
                name, firmware_version=firmware_version, serial=serial,
                dev=devroot),
            self.make_udevadm_output(
                name2, firmware_version=firmware_version, serial=serial,
                dev=devroot),
            b'%d' % size,
            b'%d' % block_size,
            b'%d' % size,
            b'%d' % block_size,
        ]

        for ref, out in zip(
                [
                    self.make_output(
                        name, maj_min, model, serial, size, block_size,
                        firmware_version, drive_path, device_id_path),
                    self.make_output(
                        name2, maj_min2, model, serial, size, block_size,
                        firmware_version, drive_path2, device_id_path2),
                ], self.call_gather_physical_block_devices(byidroot)):
            self.assertDictEqual(ref, out)

    def test__returns_block_device_without_id_path(self):
        """Block devices without by-id links should not have ID_PATH key"""
        name = factory.make_name('name')
        model = factory.make_name('model')
        maj_min = (random.randint(0, 255), random.randint(0, 255))
        serial = factory.make_name('serial')
        size = random.randint(3000 * 1000, 1000 * 1000 * 1000)
        block_size = random.choice([512, 1024, 4096])
        check_output = self.patch(subprocess, "check_output")
        firmware_version = factory.make_name('firmware_version')

        # Create simulated /dev tree without by-id link
        devroot = self.make_dir()
        os.mkdir(os.path.join(devroot, 'disk'))
        byidroot = os.path.join(devroot, 'disk', 'by_id')
        os.mkdir(byidroot)
        drive_path = os.path.join(devroot, name)
        os.mknod(drive_path)

        check_output.side_effect = [
            self.make_lsblk_output(name=name, model=model, maj_min=maj_min),
            self.make_udevadm_output(
                name, firmware_version=firmware_version, serial=serial,
                dev=devroot),
            b'%d' % size,
            b'%d' % block_size,
            ]
        for ref, out in zip(
                [
                    self.make_output(
                        name, maj_min, model, serial, size, block_size,
                        firmware_version, drive_path),
                ], self.call_gather_physical_block_devices(byidroot)):
            self.assertDictEqual(ref, out)

    def test__returns_block_device_readonly(self):
        name = factory.make_name('name')
        model = factory.make_name('model')
        maj_min = (random.randint(0, 255), random.randint(0, 255))
        serial = factory.make_name('serial')
        size = random.randint(3000 * 1000, 1000 * 1000 * 1000)
        block_size = random.choice([512, 1024, 4096])
        firmware_version = factory.make_name('firmware_version')
        check_output = self.patch(subprocess, "check_output")
        check_output.side_effect = [
            self.make_lsblk_output(
                name=name, model=model, read_only=True, maj_min=maj_min),
            self.make_udevadm_output(
                name, firmware_version=firmware_version, serial=serial),
            b'%d' % size,
            b'%d' % block_size,
            ]
        for ref, out in zip(
                [
                    self.make_output(
                        name, maj_min, model, serial, size,
                        block_size, firmware_version, read_only=True),
                ], self.call_gather_physical_block_devices()):
            self.assertDictEqual(ref, out)

    def test__returns_block_device_ssd(self):
        name = factory.make_name('name')
        model = factory.make_name('model')
        maj_min = (random.randint(0, 255), random.randint(0, 255))
        serial = factory.make_name('serial')
        size = random.randint(3000 * 1000, 1000 * 1000 * 1000)
        block_size = random.choice([512, 1024, 4096])
        firmware_version = factory.make_name('firmware_version')
        check_output = self.patch(subprocess, "check_output")
        check_output.side_effect = [
            self.make_lsblk_output(
                name=name, model=model, rotary=False, maj_min=maj_min),
            self.make_udevadm_output(
                name, firmware_version=firmware_version, serial=serial),
            b'%d' % size,
            b'%d' % block_size,
            ]
        for ref, out in zip(
                [
                    self.make_output(
                        name, maj_min, model, serial, size, block_size,
                        firmware_version, rotary=False),
                ], self.call_gather_physical_block_devices()):
            self.assertDictEqual(ref, out)

    def test__returns_block_device_not_sata(self):
        name = factory.make_name('name')
        model = factory.make_name('model')
        maj_min = (random.randint(0, 255), random.randint(0, 255))
        serial = factory.make_name('serial')
        size = random.randint(3000 * 1000, 1000 * 1000 * 1000)
        block_size = random.choice([512, 1024, 4096])
        firmware_version = factory.make_name('firmware_version')
        check_output = self.patch(subprocess, "check_output")
        check_output.side_effect = [
            self.make_lsblk_output(name=name, model=model, maj_min=maj_min),
            self.make_udevadm_output(
                name, firmware_version=firmware_version, serial=serial,
                sata=False),
            b'%d' % size,
            b'%d' % block_size,
            ]
        for ref, out in zip(
                [
                    self.make_output(
                        name, maj_min, model, serial, size, block_size,
                        firmware_version, sata=False),
                ], self.call_gather_physical_block_devices()):
            self.assertDictEqual(ref, out)

    def test__returns_block_device_removable(self):
        name = factory.make_name('name')
        model = factory.make_name('model')
        maj_min = (random.randint(0, 255), random.randint(0, 255))
        serial = factory.make_name('serial')
        size = random.randint(3000 * 1000, 1000 * 1000 * 1000)
        block_size = random.choice([512, 1024, 4096])
        firmware_version = factory.make_name('firmware_version')
        check_output = self.patch(subprocess, "check_output")
        check_output.side_effect = [
            self.make_lsblk_output(
                name=name, model=model, removable=True, maj_min=maj_min),
            self.make_udevadm_output(
                name, firmware_version=firmware_version, serial=serial),
            b'%d' % size,
            b'%d' % block_size,
            ]
        for ref, out in zip(
                [
                    self.make_output(
                        name, maj_min, model, serial, size, block_size,
                        firmware_version, removable=True),
                ], self.call_gather_physical_block_devices()):
            self.assertDictEqual(ref, out)

    def test__quietly_exits_in_container(self):
        script_dir = self.useFixture(TempDirectory()).path
        script_path = os.path.join(script_dir, '00-maas-07-block-devices')
        virtuality_result_path = os.path.join(script_dir, 'out')
        os.makedirs(virtuality_result_path)
        virtuality_result_path = os.path.join(
            virtuality_result_path, '00-maas-02-virtuality')
        open(virtuality_result_path, 'w').write('lxc\n')
        self.assertItemsEqual(
            [], self.call_gather_physical_block_devices(file_path=script_path))


class TestVirtualityScript(MAASTestCase):
    """Tests for `VIRTUALITY_SCRIPT`."""

    def setUp(self):
        super(TestVirtualityScript, self).setUp()
        # Set up a binaries directory which contains all the script deps.
        self.bindir = Path(self.make_dir())
        self.sysdv = self.bindir.joinpath("systemd-detect-virt")
        self.sysdv.symlink_to("/usr/bin/systemd-detect-virt")
        self.grep = self.bindir.joinpath("grep")
        self.grep.symlink_to("/bin/grep")
        self.which = self.bindir.joinpath("which")
        self.which.symlink_to("/bin/which")

    def run_script(self):
        script = self.bindir.joinpath("virtuality")
        script.write_text(VIRTUALITY_SCRIPT, "ascii")
        script.chmod(0o700)
        env = get_env_with_locale()
        env["PATH"] = str(self.bindir)
        try:
            return check_output((str(script),), stderr=STDOUT, env=env)
        except CalledProcessError as error:
            self.addDetail("output", text_content(
                error.output.decode("utf-8", "replace")))
            raise

    def test_runs_locally(self):
        self.assertThat(self.run_script().strip(), Not(HasLength(0)))

    def test_runs_successfully_when_systemd_detect_virt_returns_nonzero(self):
        # Replace symlink to systemd-detect-virt with a script of our making.
        self.sysdv.unlink()
        sysdv_name = factory.make_name("virt")
        with self.sysdv.open("w") as fd:
            fd.write("#!/bin/bash\n")
            fd.write("echo %s\n" % sysdv_name)
            fd.write("exit 1\n")
        self.sysdv.chmod(0o700)
        # The name echoed from our script is returned.
        self.assertThat(
            self.run_script(), Equals(
                sysdv_name.encode("ascii") + b"\n"))

    def test_runs_successfully_when_systemd_detect_virt_not_found(self):
        # Remove symlink to systemd-detect-virt.
        self.sysdv.unlink()
        # Either "none" or "qemu" will be returned here depending on the host
        # running these tests.
        self.assertThat(
            self.run_script(), MatchesAny(
                Equals(b"none\n"), Equals(b"qemu\n")))
