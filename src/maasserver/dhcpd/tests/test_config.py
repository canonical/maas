# Copyright 2012-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test cases for dhcp.config"""

from base64 import b64encode
from itertools import count
import random
import re
import shlex
import socket
import subprocess
import tempfile
import traceback

from fixtures import FakeLogger
import netaddr
from testtools.content import Content, text_content, UTF8_TEXT

from maasserver.dhcpd import config
from maasserver.dhcpd.config import _get_addresses
from maasserver.dhcpd.testing.config import (
    fix_shared_networks_failover,
    make_failover_peer_config,
    make_global_dhcp_snippets,
    make_host,
    make_shared_network,
)
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from maastesting.utils import running_in_docker
from provisioningserver.boot import BootMethodRegistry
from provisioningserver.utils import flatten
from provisioningserver.utils.shell import get_env_with_locale
from provisioningserver.utils.text import quote


def is_ip_address(string):
    """Does `string` look like an IP address?"""
    try:
        netaddr.IPAddress(string)
    except netaddr.AddrFormatError:
        return False
    else:
        return True


def make_sample_params_only(
    ipv6=False, with_interface=False, disabled_boot_architectures=None
):
    """Return a dict of arbitrary DHCP configuration parameters.

    :param ipv6: When true, prepare configuration for a DHCPv6 server,
        otherwise prepare configuration for a DHCPv4 server.
    :return: A dictionary of sample configuration.
    """
    failover_peers = [make_failover_peer_config() for _ in range(3)]
    shared_networks = [
        make_shared_network(
            ipv6=ipv6,
            with_interface=with_interface,
            disabled_boot_architectures=disabled_boot_architectures,
        )
        for _ in range(3)
    ]

    shared_networks = fix_shared_networks_failover(
        shared_networks, failover_peers
    )

    return {
        "omapi_key": b64encode(factory.make_bytes()).decode("ascii"),
        "failover_peers": failover_peers,
        "shared_networks": shared_networks,
        "hosts": [make_host(ipv6=ipv6) for _ in range(3)],
        "global_dhcp_snippets": make_global_dhcp_snippets(),
        "ipv6": ipv6,
        "running_in_snap": factory.pick_bool(),
    }


def _resolve(name):
    # Find the first address that `getaddrinfo` returns for any address
    # family, socket type, and protocol. This is like `gethostbyname` that
    # also finds names in `/etc/hosts` and works with IPv6.
    for *_, addr in socket.getaddrinfo(name, 0):
        return addr[0]


def read_aliases_from_etc_hosts():
    """Read all the aliases (hostnames) from /etc/hosts."""
    with open("/etc/hosts", encoding="ascii") as hosts:
        for line in map(str.strip, hosts):
            if len(line) > 0 and not line.startswith("#"):
                address, *aliases = line.split()
                for alias in aliases:
                    # Ensure each alias resolves as expected before returning.
                    if _resolve(alias) == address:
                        yield alias


# Names that will resolve without network activity.
aliases_from_etc_hosts = tuple(read_aliases_from_etc_hosts())


def make_sample_params(test, ipv6=False, with_interface=False):
    """Return a dict of arbitrary DHCP configuration parameters.

    This differs from `make_sample_params_only` in that it arranges it such
    that hostnames within the sample configuration can be resolved using
    `gethostbyname` or `getaddrinfo`.

    :param test: An instance of `maastesting.testcase.TestCase`.
    :param ipv6: When true, prepare configuration for a DHCPv6 server,
        otherwise prepare configuration for a DHCPv4 server.
    :return: A dictionary of sample configuration.
    """
    sample_params = make_sample_params_only(
        ipv6=ipv6, with_interface=with_interface
    )

    # So that get_config can resolve the configuration, collect hostnames from
    # the sample params that need to resolve then replace them with names that
    # will resolve locally, i.e. with an alias found in `/etc/hosts`.
    for shared_network in sample_params["shared_networks"]:
        for subnet in shared_network["subnets"]:
            subnet["ntp_servers"] = [
                (
                    server
                    if is_ip_address(server)
                    else random.choice(aliases_from_etc_hosts)
                )
                for server in subnet["ntp_servers"]
            ]

    return sample_params


def validate_dhcpd_configuration(test, configuration, ipv6):
    """Validate `configuration` using `dhcpd` itself.

    :param test: An instance of `maastesting.testcase.TestCase`.
    :param configuration: The contents of the configuration file as a string.
    :param ipv6: When true validate as DHCPv6, otherwise validate as DHCPv4.
    """
    with (
        tempfile.NamedTemporaryFile(
            "w", encoding="ascii", prefix="dhcpd.", suffix=".conf"
        ) as conffile,
        tempfile.NamedTemporaryFile(
            "w", encoding="ascii", prefix="dhcpd.", suffix=".leases"
        ) as leasesfile,
    ):
        # Write the configuration to the temporary file.
        conffile.write(configuration)
        conffile.flush()
        # Add line numbers to configuration and add as a detail. This will
        # make it much easier to debug; `dhcpd -t` prints line numbers for any
        # errors it finds.
        test.addDetail(
            conffile.name,
            Content(
                UTF8_TEXT,
                lambda: map(
                    str.encode,
                    (
                        "> %3d  %s" % entry
                        for entry in zip(
                            count(1), configuration.splitlines(keepends=True)
                        )
                    ),
                ),
            ),
        )
        cmd = [
            "dhcpd",
            ("-6" if ipv6 else "-4"),
            "-t",
            "-cf",
            conffile.name,
            "-lf",
            leasesfile.name,
        ]
        if not running_in_docker():
            # Call `dhcpd` without AppArmor confinement, so that it can read
            # configurations file from /tmp.  This is not needed when running
            # in Docker when AppArmor is not present.
            cmd = ["aa-exec", "--profile", "unconfined"] + cmd
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=get_env_with_locale(),
        )
        command = " ".join(map(shlex.quote, process.args))
        output, _ = process.communicate()
        # Record the output from `dhcpd -t` as a detail.
        test.addDetail(
            f"stdout/err from `{command}`",
            text_content(output.decode("utf-8")),
        )
        # Check that it completed successfully.
        test.assertEqual(process.returncode, 0, f"`{command}` failed.")


class TestGetConfig(MAASTestCase):
    """Tests for `get_config`."""

    scenarios = [
        ("v4", dict(template="dhcpd.conf.template", ipv6=False)),
        ("v6", dict(template="dhcpd6.conf.template", ipv6=True)),
    ]

    def test_uses_branch_template_by_default(self):
        # Since the branch comes with dhcp templates in etc/maas, we can
        # instantiate those templates without any hackery.
        self.assertIsNotNone(
            config.get_config(
                self.template, **make_sample_params(self, ipv6=self.ipv6)
            )
        )

    def test_complains_if_too_few_parameters(self):
        params = make_sample_params(self, ipv6=self.ipv6)
        del params["hosts"][0]["mac"]

        with self.assertRaisesRegex(config.DHCPConfigError, "Failed") as cm:
            config.get_config(self.template, **params)

        tblines = list(
            traceback.TracebackException.from_exception(cm.exception).format()
        )
        self.assertEqual(tblines[0], "Traceback (most recent call last):\n")
        self.assertEqual(
            tblines[-1],
            "maasserver.dhcpd.config.DHCPConfigError: Failed to render DHCP configuration.\n",
        )
        above_exception = "\nThe above exception was the direct cause of the following exception:\n\n"
        self.assertIn(above_exception, tblines)
        idx = tblines.index(above_exception)
        self.assertRegex(
            tblines[idx - 1],
            rf"KeyError\('mac at line \d+ column \d+ in file .*{self.template}'\)",
        )

    def test_renders_dns_servers_as_comma_separated_list(self):
        params = make_sample_params(self, ipv6=self.ipv6)
        rendered = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, rendered, self.ipv6)
        dns_servers_expected = [
            ", ".join(map(str, subnet["dns_servers"]))
            for network in params["shared_networks"]
            for subnet in network["subnets"]
        ]
        dns_servers_pattern = r"\b%s\s+(.+);" % re.escape(
            "dhcp6.name-servers" if self.ipv6 else "domain-name-servers"
        )
        dns_servers_observed = re.findall(dns_servers_pattern, rendered)
        self.assertEqual(dns_servers_expected, dns_servers_observed)

    def test_renders_without_dns_servers_set(self):
        params = make_sample_params(self, ipv6=self.ipv6)
        for network in params["shared_networks"]:
            for subnet in network["subnets"]:
                subnet["dns_servers"] = ""
        rendered = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, rendered, self.ipv6)
        self.assertNotIn("dhcp6.name-servers", rendered)  # IPv6
        self.assertNotIn("domain-name-servers", rendered)  # IPv4

    def test_renders_search_list_as_quoted_comma_separated_list(self):
        params = make_sample_params(self, ipv6=self.ipv6)
        for network in params["shared_networks"]:
            for subnet in network["subnets"]:
                subnet["search_list"].append("canonical.com")
        rendered = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, rendered, self.ipv6)
        dns_servers_expected = [
            ", ".join(map(quote, subnet["search_list"]))
            for network in params["shared_networks"]
            for subnet in network["subnets"]
        ]
        dns_servers_pattern = r"\b%s\s+(.+);" % re.escape(
            "dhcp6.domain-search" if self.ipv6 else "domain-search"
        )
        dns_servers_observed = re.findall(dns_servers_pattern, rendered)
        self.assertEqual(dns_servers_expected, dns_servers_observed)

    def test_renders_without_search_list_set(self):
        params = make_sample_params(self, ipv6=self.ipv6)
        for network in params["shared_networks"]:
            for subnet in network["subnets"]:
                subnet["search_list"] = ""
        rendered = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, rendered, self.ipv6)
        self.assertNotIn("dhcp6.domain-search", rendered)  # IPv6
        self.assertNotIn("domain-search", rendered)  # IPv4

    def test_renders_ntp_servers_as_comma_separated_list(self):
        params = make_sample_params(self, ipv6=self.ipv6)
        rendered = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, rendered, self.ipv6)
        ntp_servers_expected = flatten(
            [
                server if is_ip_address(server) else _get_addresses(server)
                for network in params["shared_networks"]
                for subnet in network["subnets"]
                for server in subnet["ntp_servers"]
            ]
        )
        ntp_servers_observed = [
            server
            for server_line in re.findall(
                r"\b(?:ntp-servers|dhcp6[.]sntp-servers)\s+(.+);", rendered
            )
            for server in server_line.split(", ")
        ]
        self.assertCountEqual(ntp_servers_expected, ntp_servers_observed)

    def test_renders_without_ntp_servers_set(self):
        params = make_sample_params(self, ipv6=self.ipv6)
        for network in params["shared_networks"]:
            for subnet in network["subnets"]:
                subnet["ntp_servers"] = ""
        rendered = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, rendered, self.ipv6)
        self.assertNotIn("ntp-servers", rendered)

    def test_silently_discards_unresolvable_ntp_servers(self):
        params = make_sample_params_only(ipv6=self.ipv6)
        rendered = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, rendered, self.ipv6)
        ntp_servers_expected = [
            server
            for network in params["shared_networks"]
            for subnet in network["subnets"]
            for server in subnet["ntp_servers"]
            if is_ip_address(server)
        ]
        ntp_servers_observed = [
            server
            for server_line in re.findall(
                r"\b(?:ntp-servers|dhcp6[.]sntp-servers)\s+(.+);", rendered
            )
            for server in server_line.split(", ")
        ]
        self.assertCountEqual(ntp_servers_expected, ntp_servers_observed)

    def test_renders_router_ip_if_present(self):
        params = make_sample_params(self, ipv6=self.ipv6)
        router_ip = factory.make_ipv4_address()
        params["shared_networks"][0]["subnets"][0]["router_ip"] = router_ip
        rendered = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, rendered, self.ipv6)
        self.assertIn(router_ip, rendered)

    def test_renders_with_empty_string_router_ip(self):
        params = make_sample_params(self, ipv6=self.ipv6)
        for network in params["shared_networks"]:
            for subnet in network["subnets"]:
                subnet["router_ip"] = ""
        rendered = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, rendered, self.ipv6)
        # Remove all lines that have been commented out.
        rendered = "".join(
            line
            for line in rendered.splitlines(keepends=True)
            if not line.lstrip().startswith("#")
        )
        self.assertNotIn("option routers", rendered)

    def test_renders_with_hosts(self):
        params = make_sample_params(self, ipv6=self.ipv6)
        self.assertGreaterEqual(len(params["hosts"]), 1)
        config_output = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, config_output, self.ipv6)
        for host in params["hosts"]:
            self.assertIn(host["host"], config_output)
            self.assertIn(host["mac"], config_output)
            self.assertIn(host["ip"], config_output)

    def test_renders_global_dhcp_snippets(self):
        params = make_sample_params(self, ipv6=self.ipv6)
        config_output = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, config_output, self.ipv6)
        for dhcp_snippet in params["global_dhcp_snippets"]:
            self.assertIn(dhcp_snippet["value"], config_output)

    def test_renders_subnet_dhcp_snippets(self):
        params = make_sample_params(self, ipv6=self.ipv6)
        config_output = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, config_output, self.ipv6)
        for shared_network in params["shared_networks"]:
            for subnet in shared_network["subnets"]:
                for dhcp_snippet in subnet["dhcp_snippets"]:
                    self.assertIn(dhcp_snippet["value"], config_output)

    def test_renders_node_dhcp_snippets(self):
        params = make_sample_params(self, ipv6=self.ipv6)
        config_output = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, config_output, self.ipv6)
        for host in params["hosts"]:
            for dhcp_snippet in host["dhcp_snippets"]:
                self.assertIn(dhcp_snippet["value"], config_output)

    def test_renders_subnet_cidr(self):
        params = make_sample_params(self, ipv6=self.ipv6)
        config_output = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, config_output, self.ipv6)
        for shared_network in params["shared_networks"]:
            for subnet in shared_network["subnets"]:
                if self.ipv6 is True:
                    expected = "subnet6 %s" % subnet["subnet_cidr"]
                else:
                    expected = "subnet {} netmask {}".format(
                        subnet["subnet"],
                        subnet["subnet_mask"],
                    )
                self.assertIn(expected, config_output)

    def test_renders_multiple_host_entries_for_vlan_interfaces(self):
        """Test host entries for VLAN interfaces with shared MAC.

        When a machine has multiple interfaces (physical + VLANs) sharing
        the same MAC address, each interface should get its own host
        declaration with a unique hostname and fixed IP address.
        """
        params = make_sample_params(self, ipv6=self.ipv6)

        # Add machine with 4 interfaces sharing same MAC (physical + VLANs)
        shared_mac = "00:16:3e:db:77:26"
        vlan_hosts = [
            {
                "host": "valid-gnat-enp5s0",
                "mac": shared_mac,
                "ip": "2001:db8:1::10" if self.ipv6 else "10.178.148.10",
                "dhcp_snippets": [],
            },
            {
                "host": "valid-gnat-enp5s0-100",
                "mac": shared_mac,
                "ip": "2001:db8:2::10" if self.ipv6 else "10.20.0.10",
                "dhcp_snippets": [],
            },
            {
                "host": "valid-gnat-enp5s0-200",
                "mac": shared_mac,
                "ip": "2001:db8:3::10" if self.ipv6 else "10.30.0.10",
                "dhcp_snippets": [],
            },
            {
                "host": "valid-gnat-enp5s0-300",
                "mac": shared_mac,
                "ip": "2001:db8:4::10" if self.ipv6 else "10.40.0.10",
                "dhcp_snippets": [],
            },
        ]
        params["hosts"].extend(vlan_hosts)

        config_output = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, config_output, self.ipv6)

        # Verify each VLAN interface entry is present
        for host in vlan_hosts:
            expected_hostname = (
                f"{host['host']}-{shared_mac.replace(':', '-')}"
            )
            self.assertIn(f"host {expected_hostname}", config_output)
            if self.ipv6:
                self.assertIn(f"fixed-address6 {host['ip']};", config_output)
            else:
                self.assertIn(f"fixed-address {host['ip']};", config_output)

        # Verify all 4 host declarations are present
        mac_count = config_output.count(f"hardware ethernet {shared_mac};")
        self.assertEqual(
            mac_count,
            4,
            f"Expected 4 host declarations for MAC {shared_mac}, "
            f"found {mac_count}",
        )

    def test_renders_multiple_reserved_ips_same_mac(self):
        """Test reserved IPs with same MAC on different subnets.

        When multiple reserved IPs exist for the same MAC address across
        different subnets, each reservation should get its own host
        declaration with unique hostname.
        """
        params = make_sample_params(self, ipv6=self.ipv6)

        # Add reserved IPs for same MAC on different subnets
        reserved_mac = "00:16:3e:a0:54:e2"
        reserved_hosts = [
            {
                "host": "rsvd-4",
                "mac": reserved_mac,
                "ip": "2001:db8:2::30" if self.ipv6 else "10.20.0.30",
                "dhcp_snippets": [],
            },
            {
                "host": "rsvd-5",
                "mac": reserved_mac,
                "ip": "2001:db8:3::30" if self.ipv6 else "10.30.0.30",
                "dhcp_snippets": [],
            },
            {
                "host": "rsvd-6",
                "mac": reserved_mac,
                "ip": "2001:db8:4::30" if self.ipv6 else "10.40.0.30",
                "dhcp_snippets": [],
            },
        ]
        params["hosts"].extend(reserved_hosts)

        config_output = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, config_output, self.ipv6)

        # Verify each reserved IP entry is present
        for host in reserved_hosts:
            expected_hostname = (
                f"{host['host']}-{reserved_mac.replace(':', '-')}"
            )
            self.assertIn(f"host {expected_hostname}", config_output)
            if self.ipv6:
                self.assertIn(f"fixed-address6 {host['ip']};", config_output)
            else:
                self.assertIn(f"fixed-address {host['ip']};", config_output)

        # Verify all 3 reserved IP declarations are present
        mac_count = config_output.count(f"hardware ethernet {reserved_mac};")
        self.assertEqual(
            mac_count,
            3,
            f"Expected 3 host declarations for MAC {reserved_mac}, "
            f"found {mac_count}",
        )

    def test_host_declarations_have_unique_names_with_mac_suffix(self):
        """Test that all host declarations have unique names.

        Host declaration names must be unique and include MAC address
        suffix to ensure uniqueness when multiple entries share the
        same MAC.
        """
        params = make_sample_params(self, ipv6=self.ipv6)

        # Add hosts with same MAC but different interface names
        shared_mac = "00:16:3e:ab:cd:ef"
        hosts_with_shared_mac = [
            {
                "host": "machine-eth0",
                "mac": shared_mac,
                "ip": "2001:db8:1::20" if self.ipv6 else "10.178.148.20",
                "dhcp_snippets": [],
            },
            {
                "host": "machine-eth0-100",
                "mac": shared_mac,
                "ip": "2001:db8:2::20" if self.ipv6 else "10.20.0.20",
                "dhcp_snippets": [],
            },
        ]
        params["hosts"].extend(hosts_with_shared_mac)

        config_output = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, config_output, self.ipv6)

        # Extract all host declaration names
        host_pattern = r"^host\s+([\w\-]+)\s*\{$"
        host_names = re.findall(host_pattern, config_output, re.MULTILINE)

        # Verify all host names are unique
        self.assertEqual(
            len(host_names),
            len(set(host_names)),
            f"Duplicate host names found: {host_names}",
        )

        # Verify MAC suffix is present in host names
        mac_suffix = shared_mac.replace(":", "-")
        for host in hosts_with_shared_mac:
            expected_name = f"{host['host']}-{mac_suffix}"
            self.assertIn(
                expected_name,
                host_names,
                f"Expected host name '{expected_name}' not found",
            )

    def test_vlan_interface_hosts_maintain_dhcp_snippets(self):
        """Test DHCP snippets preserved for VLAN interface hosts.

        When generating multiple host declarations for VLAN interfaces,
        each should maintain its own DHCP snippets if present.
        """
        params = make_sample_params(self, ipv6=self.ipv6)

        shared_mac = "00:16:3e:11:22:33"
        vlan_hosts = [
            {
                "host": "node-eth0",
                "mac": shared_mac,
                "ip": "2001:db8:1::60" if self.ipv6 else "10.178.148.60",
                "dhcp_snippets": [
                    {
                        "name": "snippet-vlan0",
                        "description": "Snippet for untagged VLAN",
                        "value": "# VLAN 0 configuration",
                    }
                ],
            },
            {
                "host": "node-eth0-100",
                "mac": shared_mac,
                "ip": "2001:db8:2::60" if self.ipv6 else "10.20.0.60",
                "dhcp_snippets": [
                    {
                        "name": "snippet-vlan100",
                        "description": "Snippet for VLAN 100",
                        "value": "# VLAN 100 configuration",
                    }
                ],
            },
        ]
        params["hosts"].extend(vlan_hosts)

        config_output = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, config_output, self.ipv6)

        # Verify each snippet is present in configuration
        for host in vlan_hosts:
            expected_hostname = (
                f"{host['host']}-{shared_mac.replace(':', '-')}"
            )
            host_start = config_output.find(f"host {expected_hostname}")
            self.assertNotEqual(
                host_start,
                -1,
                f"Host {expected_hostname} not found in configuration",
            )

            # Verify snippets appear after their host declaration
            for dhcp_snippet in host["dhcp_snippets"]:
                snippet_pos = config_output.find(
                    dhcp_snippet["value"], host_start
                )
                self.assertNotEqual(
                    snippet_pos,
                    -1,
                    f"DHCP snippet '{dhcp_snippet['value']}' not found "
                    f"for host {expected_hostname}",
                )


class Test_process_shared_network_v6(MAASTestCase):
    """Tests for `_process_network_parameters_v6`."""

    scenarios = (
        (
            "singleton",
            dict(
                expected={
                    "ip_range_high": "2001:db8:3:1::ffff",
                    "ip_range_low": "2001:db8:3:1::",
                    "failover_peer": None,
                },
                failover_peers=[],
            ),
        ),
        (
            "primary",
            dict(
                expected={
                    "ip_range_high": "2001:db8:3:1::7fff",
                    "ip_range_low": "2001:db8:3:1::",
                    "failover_peer": "failover-vlan-5020",
                },
                failover_peers=[
                    {
                        "mode": "primary",
                        "peer_address": "2001:db8:3:0:1::",
                        "name": "failover-vlan-5020",
                        "address": "2001:db8:3:280::2",
                    }
                ],
            ),
        ),
        (
            "secondary",
            dict(
                expected={
                    "ip_range_high": "2001:db8:3:1::ffff",
                    "ip_range_low": "2001:db8:3:1::8000",
                    "failover_peer": "failover-vlan-5020",
                },
                failover_peers=[
                    {
                        "mode": "secondary",
                        "address": "2001:db8:3:0:1::",
                        "name": "failover-vlan-5020",
                        "peer_address": "2001:db8:3:280::2",
                    }
                ],
            ),
        ),
    )

    def test_adjusts_parameters_for_primary(self):
        shared_networks = [
            {
                "name": "vlan-5020",
                "interface": "eth0",
                "subnets": [
                    {
                        "domain_name": "maas.example.com",
                        "pools": [
                            {
                                "ip_range_high": "2001:db8:3:1::ffff",
                                "ip_range_low": "2001:db8:3:1::",
                                "failover_peer": self.expected[
                                    "failover_peer"
                                ],
                            }
                        ],
                        "dns_servers": [],
                        "subnet_mask": "ffff:ffff:ffff:ffff::",
                        "ntp_servers": [],
                        "broadcast_ip": "2001:db8:3::ffff:ffff:ffff:ffff",
                        "router_ip": "fe80::1",
                        "subnet": "2001:db8:3::",
                        "subnet_cidr": "2001:db8:3::/64",
                        "dhcp_snippets": [],
                    }
                ],
            }
        ]
        self.patch(config, "get_rack_ip_for_subnet").return_value = None
        self.patch(config, "compose_conditional_bootloader").return_value = ""
        self.patch(config, "_get_addresses").return_value = (
            [""],
            ["2001:db8:280::2"],
        )
        actual = config._process_network_parameters_v6(
            self.failover_peers, shared_networks
        )
        self.assertDictEqual(
            actual[0]["subnets"][0]["pools"][0], self.expected
        )


class TestComposeConditionalBootloader(MAASTestCase):
    """Tests for `compose_conditional_bootloader`."""

    def test_composes_bootloader_section_v4(self):
        ip = factory.make_ipv4_address()
        output = config.compose_conditional_bootloader(False, ip)
        for name, method in BootMethodRegistry:
            if name == "pxe":
                self.assertIn("else", output)
                self.assertIn(method.bootloader_path, output)
            elif method.arch_octet is not None:
                if isinstance(method.arch_octet, list):
                    for arch in method.arch_octet:
                        self.assertIn(arch, output)
                else:
                    self.assertIn(method.arch_octet, output)
                self.assertIn(method.bootloader_path, output)
            else:
                # No DHCP configuration is rendered for boot methods that have
                # no `arch_octet`, with the solitary exception of PXE.
                pass

            if method.user_class == "iPXE":
                self.assertIn(
                    f'option user-class = "{method.user_class}" or',
                    output,
                )
            elif method.user_class is not None:
                self.assertIn(
                    f'option user-class = "{method.user_class}" {{',
                    output,
                )

            if method.path_prefix_http or method.http_url:
                self.assertIn("http://%s:5248/" % ip, output)
            if method.path_prefix_force:
                self.assertIn(
                    "option dhcp-parameter-request-list = concat(",
                    output,
                )
                self.assertIn(
                    "option dhcp-parameter-request-list,d2);", output
                )
            if method.http_url:
                self.assertIn(
                    'option vendor-class-identifier "HTTPClient";',
                    output,
                )

    def test_composes_bootloader_section_v6(self):
        ip = factory.make_ipv6_address()
        output = config.compose_conditional_bootloader(True, ip)
        for name, method in BootMethodRegistry:
            if name == "uefi":
                self.assertIn("else", output)
                self.assertIn(method.bootloader_path, output)
            elif method.arch_octet is not None:
                if isinstance(method.arch_octet, list):
                    for arch in method.arch_octet:
                        self.assertIn(arch, output)
                else:
                    self.assertIn(method.arch_octet, output)
                self.assertIn(method.bootloader_path, output)
            else:
                # No DHCP configuration is rendered for boot methods that have
                # no `arch_octet`, with the solitary exception of PXE.
                pass
            if method.user_class == "iPXE":
                self.assertIn(
                    f'option dhcp6.user-class = "{method.user_class}" or',
                    output,
                )
            elif method.user_class is not None:
                self.assertIn(
                    f'option dhcp6.user-class = "{method.user_class}" {{',
                    output,
                )

            if method.path_prefix_http or method.http_url:
                self.assertIn("http://[%s]:5248/" % ip, output)
            if method.path_prefix_force:
                self.assertIn(
                    "option dhcp6.oro = concat(option dhcp6.oro,00d2);", output
                )
            if method.http_url:
                self.assertIn(
                    'option dhcp6.vendor-class 0 10 "HTTPClient";', output
                )

    def test_disabled_boot_architecture(self):
        if factory.pick_bool():
            ipv6 = True
            ip = factory.make_ipv6_address()
        else:
            ipv6 = False
            ip = factory.make_ipv4_address()
        disabled_arches = random.sample(
            [
                boot_method
                for _, boot_method in BootMethodRegistry
                if boot_method.arch_octet or boot_method.user_class
            ],
            3,
        )
        output = config.compose_conditional_bootloader(
            ipv6, ip, [bm.name for bm in disabled_arches]
        )
        for disabled_arch in disabled_arches:
            if disabled_arch.arch_octet:
                self.assertNotIn(disabled_arch.arch_octet, output)
            else:
                self.assertNotIn(disabled_arch.user_class, output)


class TestGetAddresses(MAASTestCase):
    """Tests for `_get_addresses`."""

    def test_ip_addresses_are_passed_through(self):
        address4 = factory.make_ipv4_address()
        address6 = factory.make_ipv6_address()
        self.assertEqual(
            ([address4], [address6]),
            config._get_addresses(address4, address6),
        )

    def test_ignores_resolution_failures(self):
        # Some ISPs configure their DNS to resolve to an ads page when a domain
        # doesn't exist. This ensures resolving fails so the test passes.
        self.patch(config, "_gen_addresses_where_possible").return_value = []
        self.assertEqual(
            ([], []),
            config._get_addresses("no-way-this-exists.maas.io"),
        )

    def test_logs_resolution_failures(self):
        # Some ISPs configure their DNS to resolve to an ads page when a domain
        # doesn't exist. This ensures resolving fails so the test passes.
        exception = socket.gaierror()
        exception.errno = random.choice(
            list(config._gen_addresses_where_possible_suppress)
        )
        exception.strerror = "[Errno ...] ..."
        self.patch(config, "_gen_addresses").side_effect = exception
        with FakeLogger(config.__name__) as logger:
            config._get_addresses("no-way-this-exists.maas.io")
        self.assertIn(
            f"Could not resolve no-way-this-exists.maas.io: [Errno {exception.errno}] [Errno ...] ...",
            logger.output.strip(),
        )
