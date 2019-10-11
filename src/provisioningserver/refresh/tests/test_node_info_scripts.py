# Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test node info scripts."""

__all__ = []

from inspect import getsource
import os.path
from pathlib import Path
import subprocess
from subprocess import CalledProcessError, check_output, STDOUT
from textwrap import dedent
import time
from unittest.mock import call

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith, MockCallsMatch
from maastesting.testcase import MAASTestCase
from provisioningserver.refresh import node_info_scripts as node_info_module
from provisioningserver.refresh.node_info_scripts import (
    make_function_call_script,
    VIRTUALITY_SCRIPT,
)
from provisioningserver.utils.shell import get_env_with_locale
from testtools.content import text_content
from testtools.matchers import Equals, HasLength, MatchesAny, Not


class TestMakeFunctionCallScript(MAASTestCase):
    def run_script(self, script):
        script_filename = self.make_file("test.py", script)
        os.chmod(script_filename, 0o700)
        try:
            return check_output((script_filename,), stderr=STDOUT)
        except CalledProcessError as error:
            self.addDetail(
                "output", text_content(error.output.decode("ascii", "replace"))
            )
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
            example_function, {"123": "foo", "bar": [4, 5, 6]}
        )
        self.assertEqual(b"Equal\n", self.run_script(script))


def isolate_function(function, namespace=None):
    """Recompile the given function in the given namespace.

    :param namespace: A dict to use as the namespace. If not provided, and
        empty namespace will be used.
    """
    source = dedent(getsource(function))
    modcode = compile(source, "isolated.py", "exec")
    namespace = {} if namespace is None else namespace
    if "__file__" not in namespace:
        namespace["__file__"] = __file__
    exec(modcode, namespace)
    return namespace[function.__name__]


class TestLLDPScripts(MAASTestCase):
    def test_install_script_installs_configures_and_restarts_systemd(self):
        config_file = self.make_file("config", "# ...")
        check_call = self.patch(subprocess, "check_call")
        self.patch(os.path, "isdir").return_value = True
        lldpd_install = isolate_function(node_info_module.lldpd_install)
        lldpd_install(config_file)
        # lldpd is installed and restarted.
        self.assertEqual(
            check_call.call_args_list,
            [call(("systemctl", "restart", "lldpd"))],
        )
        # lldpd's config was updated to include an updated DAEMON_ARGS
        # setting. Note that the new comment is on a new line, and
        # does not interfere with existing config.
        config_expected = dedent(
            """\
            # ...
            # Configured by MAAS:
            DAEMON_ARGS="-c -f -s -e -r"
            """
        ).encode("ascii")
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
        self.assertThat(
            time.sleep,
            MockCalledOnceWith(
                os.path.getmtime.return_value
                + time_delay
                - time.time.return_value
            ),
        )

    def test_capture_lldpd_script_doesnt_waits_for_more_than_sixty_secs(self):
        # Regression test for LP:1801152
        reference_file = self.make_file("reference")
        lldpd_capture = isolate_function(node_info_module.lldpd_capture)
        self.patch(os.path, "getmtime").return_value = 1000.1
        self.patch(time, "time").return_value = 10.25
        self.patch(time, "sleep")
        self.patch(subprocess, "check_call")

        lldpd_capture(reference_file, 60)

        self.assertThat(time.sleep, MockCalledOnceWith(60))

    def test_capture_lldpd_calls_lldpdctl(self):
        reference_file = self.make_file("reference")
        check_call = self.patch(subprocess, "check_call")
        lldpd_capture = isolate_function(node_info_module.lldpd_capture)
        lldpd_capture(reference_file, 0.0)
        self.assertEqual(
            check_call.call_args_list, [call(("lldpctl", "-f", "xml"))]
        )


# The two following example outputs differ because eth2 and eth1 are not
# configured and thus 'ip -o link show' returns a list with both 'eth1'
# and 'eth2' while 'ip -o link show up' does not contain them.

# Example output of 'ip -o link show':
ip_link_show_all = b"""\
1: eth2: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state DOWN mode DEFAULT \
 group default qlen 1000\\    link/ether 00:01:02:03:04:08 brd \
 ff:ff:ff:ff:ff:ff
2: eth1: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state DOWN mode DEFAULT \
 group default qlen 1000\\    link/ether 00:01:02:03:04:07 brd \
 ff:ff:ff:ff:ff:ff
3: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP mode \
 DEFAULT group default qlen 1000\\    link/ether 00:01:02:03:04:03 brd \
 ff:ff:ff:ff:ff:ff
4: eth4: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state DOWN mode DEFAULT \
 group default qlen 1000\\    link/ether 00:01:02:03:04:04 brd \
 ff:ff:ff:ff:ff:ff
5: eth5: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state DOWN mode DEFAULT \
 group default qlen 1000\\    link/ether 00:01:02:03:04:06 brd \
 ff:ff:ff:ff:ff:ff
6: eth6: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state DOWN mode DEFAULT \
 group default qlen 1000\\    link/ether 00:01:02:03:04:06 brd \
 ff:ff:ff:ff:ff:ff
7: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN mode \
 DEFAULT group default qlen 1000\\    link/loopback 00:00:00:00:00:00 brd \
 00:00:00:00:00:00
8: virbr0: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state DOWN mode DEFAULT \
 group default qlen 1000\\    link/ether 00:01:02:03:04:02 brd \
 ff:ff:ff:ff:ff:ff
9: wlan0: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state DOWN mode DEFAULT \
 group default qlen 1000\\    link/ether 00:01:02:03:04:05 brd \
 ff:ff:ff:ff:ff:ff
"""

# Example output of 'ip -o link show up':
ip_link_show = b"""\
1: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP mode \
 DEFAULT group default qlen 1000\\    link/ether 00:01:02:03:04:03 brd \
 ff:ff:ff:ff:ff:ff
2: eth4: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state UP mode DEFAULT \
 group default qlen 1000\\    link/ether 00:01:02:03:04:04 brd \
 ff:ff:ff:ff:ff:ff
3: eth5: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state UP mode DEFAULT \
 group default qlen 1000\\    link/ether 00:01:02:03:04:06 brd \
 ff:ff:ff:ff:ff:ff
4: eth6: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state UP mode DEFAULT \
 group default qlen 1000\\    link/ether 00:01:02:03:04:06 brd \
 ff:ff:ff:ff:ff:ff
5: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN mode \
 DEFAULT group default qlen 1000\\    link/loopback 00:00:00:00:00:00 \
 brd 00:00:00:00:00:00
6: virbr0: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state UP mode DEFAULT \
 group default qlen 1000\\    link/ether 00:01:02:03:04:02 brd \
 ff:ff:ff:ff:ff:ff
7: wlan0: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state UP mode DEFAULT \
 group default qlen 1000\\    link/ether 00:01:02:03:04:05 brd \
 ff:ff:ff:ff:ff:ff
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
    "for idx in $(seq 10); do dhclient -6 %s && break || sleep 10; done"
)


class TestDHCPExplore(MAASTestCase):
    def test_calls_dhclient_on_unconfigured_interfaces(self):
        check_output = self.patch(subprocess, "check_output")
        check_output.side_effect = [
            ip_link_show_all,
            ip_link_show,
            ip_eth0,
            ip_eth4,
            ip_eth5,
            ip_eth6,
            ip_lo,
            ip_virbr0,
            ip_wlan0,
            ip_eth0,
            ip_eth4,
            ip_eth5,
            ip_eth6,
            ip_lo,
            ip_virbr0,
            ip_wlan0,
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
                call(["dhclient", "-nw", "-4", b"eth6"]),
            ),
        )
        self.assertThat(
            mock_popen,
            MockCallsMatch(
                call(["sh", "-c", DHCP6_TEMPLATE % "eth1"]),
                call(["sh", "-c", DHCP6_TEMPLATE % "eth2"]),
                call(["sh", "-c", DHCP6_TEMPLATE % "eth4"]),
                call(["sh", "-c", DHCP6_TEMPLATE % "virbr0"]),
                call(["sh", "-c", DHCP6_TEMPLATE % "wlan0"]),
            ),
        )


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
            self.addDetail(
                "output", text_content(error.output.decode("utf-8", "replace"))
            )
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
            self.run_script(), Equals(sysdv_name.encode("ascii") + b"\n")
        )

    def test_runs_successfully_when_systemd_detect_virt_not_found(self):
        # Remove symlink to systemd-detect-virt.
        self.sysdv.unlink()
        # Either "none" or "qemu" will be returned here depending on the host
        # running these tests.
        self.assertThat(
            self.run_script(), MatchesAny(Equals(b"none\n"), Equals(b"qemu\n"))
        )
