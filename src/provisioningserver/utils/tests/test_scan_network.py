# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for ``provisioningserver.utils.scan_network``."""


from argparse import ArgumentParser, Namespace
import io
import os
import random
import subprocess
from unittest.mock import ANY, Mock

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.utils import scan_network as scan_network_module
from provisioningserver.utils.scan_network import (
    add_arguments,
    get_nmap_arguments,
    get_ping_arguments,
    NmapParameters,
    PingParameters,
    run,
    run_nmap,
    run_ping,
    yield_nmap_parameters,
    yield_ping_parameters,
)
from provisioningserver.utils.script import ActionScriptError
from provisioningserver.utils.shell import get_env_with_locale

TEST_INTERFACES = {
    "eth0": {"links": []},
    "eth1": {"links": [{"address": "192.168.0.1/24"}]},
    "eth2": {
        "links": [
            {"address": "192.168.2.1/24"},
            {"address": "192.168.3.1/24"},
            {"address": "2001:db8::1/64"},
        ]
    },
}


class TestScanNetworkCommand(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.output = io.StringIO()
        self.error_output = io.StringIO()
        self.all_interfaces_mock = self.patch(
            scan_network_module, "get_all_interfaces_definition"
        )
        self.scan_networks_mock = self.patch(scan_network_module.scan_networks)
        self.all_interfaces_mock.return_value = TEST_INTERFACES
        self.parser = ArgumentParser()
        add_arguments(self.parser)

    def run_command(self, *args):
        parsed_args = self.parser.parse_args([*args])
        return run(parsed_args, stdout=self.output, stderr=self.error_output)

    def test_interprets_long_arguments(self):
        self.run_command("--ping", "--threads", "37", "--slow")
        self.scan_networks_mock.assert_called_once_with(
            Namespace(
                threads=37, slow=True, ping=True, interface=None, cidr=[]
            ),
            ANY,
            ANY,
            ANY,
        ),

    def test_default_arguments(self):
        self.run_command()
        self.scan_networks_mock.assert_called_once_with(
            Namespace(
                threads=None, slow=False, ping=False, interface=None, cidr=[]
            ),
            ANY,
            ANY,
            ANY,
        ),

    def test_scans_all_interface_cidrs_when_zero_parameters_passed(self):
        self.run_command()
        self.scan_networks_mock.assert_called_once_with(
            ANY,
            {
                "eth0": [],
                "eth1": ["192.168.0.1/24"],
                "eth2": ["192.168.2.1/24", "192.168.3.1/24"],
            },
            ANY,
            ANY,
        )

    def test_scans_all_cidrs_on_single_interface_when_ifname_passed(self):
        self.run_command("eth2")
        self.scan_networks_mock.assert_called_once_with(
            ANY,
            {"eth2": ["192.168.2.1/24", "192.168.3.1/24"]},
            ANY,
            ANY,
        )

    def test_finds_correct_interface_if_passed_in_cidr_matches(self):
        self.run_command("192.168.2.0/24")
        self.scan_networks_mock.assert_called_once_with(
            ANY,
            {"eth0": [], "eth1": [], "eth2": ["192.168.2.0/24"]},
            ANY,
            ANY,
        )

    def test_scans_specific_interface_cidr(self):
        self.run_command("eth2", "192.168.3.0/24")
        self.scan_networks_mock.assert_called_once_with(
            ANY, {"eth2": ["192.168.3.0/24"]}, ANY, ANY
        )

    def test_scans_cidr_subset(self):
        self.run_command("192.168.3.0/28")
        self.scan_networks_mock.assert_called_once_with(
            ANY,
            {"eth0": [], "eth1": [], "eth2": ["192.168.3.0/28"]},
            ANY,
            ANY,
        )

    def test_rejects_ipv6_cidr(self):
        expected_error = ".*Not a valid IPv4 CIDR:.*"
        with self.assertRaisesRegex(ActionScriptError, expected_error):
            self.run_command("eth2", "2001:db8::/64")

    def test_rejects_non_interface_or_cidr(self):
        expected_error = ".*First argument must be an interface or CIDR: wtf0"
        with self.assertRaisesRegex(ActionScriptError, expected_error):
            self.run_command("wtf0")


class TestScanNetworkCommandEndToEnd(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.output = io.StringIO()
        self.error_output = io.StringIO()
        self.all_interfaces_mock = self.patch(
            scan_network_module, "get_all_interfaces_definition"
        )
        self.has_command_available_mock = self.patch(
            scan_network_module, "has_command_available"
        )
        self.all_interfaces_mock.return_value = TEST_INTERFACES
        self.popen = self.patch(scan_network_module.subprocess, "Popen")
        self.popen.return_value.poll = Mock()
        self.popen.return_value.poll.return_value = None
        self.popen.return_value.returncode = 0
        self.parser = ArgumentParser()
        add_arguments(self.parser)

    def run_command(self, *args):
        parsed_args = self.parser.parse_args([*args])
        return run(parsed_args, stdout=self.output, stderr=self.error_output)

    def test_runs_ping_single_threaded(self):
        ip = factory.make_ip_address(ipv6=False)
        # Force the use of `ping` even if `nmap` is installed.
        self.run_command("--threads", "1", "--ping", "eth0", "%s/32" % ip)
        expected_params = PingParameters(interface="eth0", ip=ip)
        self.popen.assert_called_once_with(
            get_ping_arguments(expected_params),
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            env=get_env_with_locale(),
        )

    def test_runs_ping_e2e(self):
        ip = factory.make_ip_address(ipv6=False)
        # Force the use of `ping` even if `nmap` is installed.
        self.run_command("--ping", "eth0", "%s/32" % ip)
        expected_params = PingParameters(interface="eth0", ip=ip)
        self.popen.assert_called_once_with(
            get_ping_arguments(expected_params),
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            env=get_env_with_locale(),
        )

    def test_runs_ping_e2e_prints_summary(self):
        self.popen.return_value.returncode = 0
        # Force the use of `ping` even if `nmap` is installed.
        self.run_command("--ping", "eth1", "192.168.0.0/24")
        self.assertEqual(
            self.error_output.getvalue(),
            "Pinged 254 hosts (254 up) in 0 second(s).\n",
        )

    def test_runs_ping_e2e_prints_warning_for_unknown_cidr(self):
        self.popen.return_value.returncode = 1
        # Force the use of `ping` even if `nmap` is installed.
        self.run_command("--ping", "eth1", "172.16.0.0/24")
        self.assertRegex(
            self.error_output.getvalue(),
            r"^Warning: 172.16.0.0/24 is not present on eth1",
        )

    def test_runs_nmap_single_threaded(self):
        ip = factory.make_ip_address(ipv6=False)
        # Force the use of `nmap` by ensuring it is reported as available.
        self.has_command_available_mock.return_value = True
        cidr = "%s/32" % ip
        slow = random.choice([True, False])
        args = ["--threads", "1", "eth0", cidr]
        if slow is True:
            args.append("--slow")
        self.run_command(*args)
        expected_params = NmapParameters(
            interface="eth0", cidr=cidr, slow=slow
        )
        self.popen.assert_called_once_with(
            get_nmap_arguments(expected_params),
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            env=get_env_with_locale(),
            preexec_fn=os.setsid,
        )

    def test_runs_nmap_e2e(self):
        ip = factory.make_ip_address(ipv6=False)
        # Force the use of `nmap` by ensuring it is reported as available.
        self.has_command_available_mock.return_value = True
        cidr = "%s/32" % ip
        slow = random.choice([True, False])
        args = ["eth0", cidr]
        if slow is True:
            args.append("--slow")
        self.run_command(*args)
        expected_params = NmapParameters(
            interface="eth0", cidr=cidr, slow=slow
        )
        self.popen.assert_called_once_with(
            get_nmap_arguments(expected_params),
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            env=get_env_with_locale(),
            preexec_fn=os.setsid,
        )

    def test_runs_nmap_e2e_prints_summary(self):
        ip = factory.make_ip_address(ipv6=False)
        # Force the use of `nmap` by ensuring it is reported as available.
        self.has_command_available_mock.return_value = True
        cidr = "%s/32" % ip
        slow = random.choice([True, False])
        args = ["eth0", cidr]
        if slow is True:
            args.append("--slow")
        self.run_command(*args)
        self.assertRegex(
            self.error_output.getvalue(),
            r"1 nmap scan\(s\) completed in 0 second\(s\).",
        )

    def test_prints_error_for_missing_cidr(self):
        self.run_command("8.8.8.0/24")
        self.assertRegex(
            self.error_output.getvalue(),
            r"^Requested network\(s\) not available to scan:",
        )


class TestRunPing(MAASTestCase):
    def test_runs_popen_with_expected_parameters(self):
        popen = self.patch(scan_network_module.subprocess, "Popen")
        popen.return_value.poll = Mock()
        popen.return_value.poll.return_value = None
        popen.return_value.returncode = 0
        interface = factory.make_name("eth")
        ip = factory.make_ip_address(ipv6=False)
        params = PingParameters(interface, ip)
        run_ping(params)
        popen.assert_called_once_with(
            get_ping_arguments(params),
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            env=get_env_with_locale(),
        )


class TestRunNmap(MAASTestCase):
    def test_runs_popen_with_expected_parameters(self):
        popen = self.patch(scan_network_module.subprocess, "Popen")
        popen.return_value.poll = Mock()
        popen.return_value.poll.return_value = None
        interface = factory.make_name("eth")
        cidr = "192.168.0.0/24"
        params = NmapParameters(interface, cidr, slow=False)
        run_nmap(params)
        popen.assert_called_once_with(
            get_nmap_arguments(params),
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            env=get_env_with_locale(),
            preexec_fn=os.setsid,
        )

    def test_runs_popen_with_expected_parameters__slow(self):
        popen = self.patch(scan_network_module.subprocess, "Popen")
        popen.return_value.poll = Mock()
        popen.return_value.poll.return_value = None
        interface = factory.make_name("eth")
        cidr = "192.168.0.0/24"
        params = NmapParameters(interface, cidr, slow=True)
        run_nmap(params)
        nmap_args = get_nmap_arguments(params)
        popen.assert_called_once_with(
            nmap_args,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            env=get_env_with_locale(),
            preexec_fn=os.setsid,
        )
        self.assertIn("--max-rate", nmap_args)


class TestYieldNmapParameters(MAASTestCase):
    def test_nmap__yields_ipv4_cidrs(self):
        slow = random.choice([True, False])
        params = yield_nmap_parameters(
            {"eth0": ["2001:db8::/64", "192.168.0.1/24", "192.168.1.1/24"]},
            slow=slow,
        )
        self.assertEqual(
            set(params),
            {
                NmapParameters(
                    interface="eth0", cidr="192.168.0.0/24", slow=slow
                ),
                NmapParameters(
                    interface="eth0", cidr="192.168.1.0/24", slow=slow
                ),
            },
        )


class TestYieldPingParameters(MAASTestCase):
    def test_ping__yields_ipv4_ips(self):
        params = yield_ping_parameters(
            {"eth0": ["2001:db8::/64", "192.168.0.1/30"]}
        )
        self.assertEqual(
            set(params),
            {
                PingParameters(interface="eth0", ip="192.168.0.1"),
                PingParameters(interface="eth0", ip="192.168.0.2"),
            },
        )
