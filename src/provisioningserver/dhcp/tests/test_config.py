# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test cases for dhcp.config"""


from base64 import b64encode
from itertools import count
import pipes
import random
import re
import socket
import subprocess
import tempfile
from textwrap import dedent
import traceback

from fixtures import FakeLogger
import netaddr
from testtools.content import Content, text_content, UTF8_TEXT
from testtools.matchers import (
    AfterPreprocessing,
    Contains,
    ContainsAll,
    Equals,
)

from maastesting.factory import factory
from maastesting.matchers import DocTestMatches, GreaterThanOrEqual
from maastesting.testcase import MAASTestCase
from maastesting.utils import running_in_docker
from provisioningserver.boot import BootMethodRegistry
from provisioningserver.dhcp import config
from provisioningserver.dhcp.config import _get_addresses
from provisioningserver.dhcp.testing.config import (
    fix_shared_networks_failover,
    make_failover_peer_config,
    make_global_dhcp_snippets,
    make_host,
    make_shared_network,
)
from provisioningserver.utils import flatten
import provisioningserver.utils.network as net_utils
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


def make_sample_params_only(ipv6=False, with_interface=False):
    """Return a dict of arbitrary DHCP configuration parameters.

    :param ipv6: When true, prepare configuration for a DHCPv6 server,
        otherwise prepare configuration for a DHCPv4 server.
    :return: A dictionary of sample configuration.
    """
    failover_peers = [make_failover_peer_config() for _ in range(3)]
    shared_networks = [
        make_shared_network(ipv6=ipv6, with_interface=with_interface)
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
    }


def _resolve(name):
    # Find the first address that `getaddrinfo` returns for any address
    # family, socket type, and protocol. This is like `gethostbyname` that
    # also finds names in `/etc/hosts` and works with IPv6.
    for *_, addr in socket.getaddrinfo(name, 0):
        return addr[0]


def read_aliases_from_etc_hosts():
    """Read all the aliases (hostnames) from /etc/hosts."""
    with open("/etc/hosts", "r", encoding="ascii") as hosts:
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
                server
                if is_ip_address(server)
                else random.choice(aliases_from_etc_hosts)
                for server in subnet["ntp_servers"]
            ]

    return sample_params


def validate_dhcpd_configuration(test, configuration, ipv6):
    """Validate `configuration` using `dhcpd` itself.

    :param test: An instance of `maastesting.testcase.TestCase`.
    :param configuration: The contents of the configuration file as a string.
    :param ipv6: When true validate as DHCPv6, otherwise validate as DHCPv4.
    """
    with tempfile.NamedTemporaryFile(
        "w", encoding="ascii", prefix="dhcpd.", suffix=".conf"
    ) as conffile, tempfile.NamedTemporaryFile(
        "w", encoding="ascii", prefix="dhcpd.", suffix=".leases"
    ) as leasesfile:
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
        cmd = (
            "dhcpd",
            ("-6" if ipv6 else "-4"),
            "-t",
            "-cf",
            conffile.name,
            "-lf",
            leasesfile.name,
        )
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
        command = " ".join(map(pipes.quote, process.args))
        output, _ = process.communicate()
        # Record the output from `dhcpd -t` as a detail.
        test.addDetail(
            "stdout/err from `%s`" % command,
            text_content(output.decode("utf-8")),
        )
        # Check that it completed successfully.
        test.assertThat(
            process.returncode, Equals(0), "`%s` failed." % command
        )


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

        e = self.assertRaises(
            config.DHCPConfigError, config.get_config, self.template, **params
        )

        tbe = traceback.TracebackException.from_exception(e)
        self.assertDocTestMatches(
            dedent(
                """\
            Traceback (most recent call last):
            ...
            KeyError: 'mac at line ... column ... in file ...'
            <BLANKLINE>
            ...
            <BLANKLINE>
            The above exception was the direct cause of the following
            exception:
            <BLANKLINE>
            Traceback (most recent call last):
            ...
            provisioningserver.dhcp.config.DHCPConfigError: Failed to render
            DHCP configuration.
            """
            ),
            "".join(tbe.format()),
        )

    def test_includes_compose_conditional_bootloader(self):
        params = make_sample_params(self, ipv6=self.ipv6)
        rack_ip = params["shared_networks"][0]["subnets"][0]["router_ip"]
        self.patch(net_utils, "get_all_interface_addresses").return_value = [
            netaddr.IPAddress(rack_ip)
        ]
        bootloader = config.compose_conditional_bootloader(
            ipv6=self.ipv6, rack_ip=rack_ip
        )
        rendered = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, rendered, self.ipv6)
        self.assertThat(rendered, Contains(bootloader))

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
        self.assertItemsEqual(ntp_servers_expected, ntp_servers_observed)

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
        self.assertItemsEqual(ntp_servers_expected, ntp_servers_observed)

    def test_renders_router_ip_if_present(self):
        params = make_sample_params(self, ipv6=self.ipv6)
        router_ip = factory.make_ipv4_address()
        params["shared_networks"][0]["subnets"][0]["router_ip"] = router_ip
        rendered = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, rendered, self.ipv6)
        self.assertThat(rendered, Contains(router_ip))

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
        self.assertThat(
            params["hosts"], AfterPreprocessing(len, GreaterThanOrEqual(1))
        )
        config_output = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, config_output, self.ipv6)
        self.assertThat(
            config_output,
            ContainsAll([host["host"] for host in params["hosts"]]),
        )
        self.assertThat(
            config_output,
            ContainsAll([host["mac"] for host in params["hosts"]]),
        )
        self.assertThat(
            config_output,
            ContainsAll([host["ip"] for host in params["hosts"]]),
        )

    def test_renders_global_dhcp_snippets(self):
        params = make_sample_params(self, ipv6=self.ipv6)
        config_output = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, config_output, self.ipv6)
        self.assertThat(
            config_output,
            ContainsAll(
                [
                    dhcp_snippet["value"]
                    for dhcp_snippet in params["global_dhcp_snippets"]
                ]
            ),
        )

    def test_renders_subnet_dhcp_snippets(self):
        params = make_sample_params(self, ipv6=self.ipv6)
        config_output = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, config_output, self.ipv6)
        for shared_network in params["shared_networks"]:
            for subnet in shared_network["subnets"]:
                self.assertThat(
                    config_output,
                    ContainsAll(
                        [
                            dhcp_snippet["value"]
                            for dhcp_snippet in subnet["dhcp_snippets"]
                        ]
                    ),
                )

    def test_renders_node_dhcp_snippets(self):
        params = make_sample_params(self, ipv6=self.ipv6)
        config_output = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, config_output, self.ipv6)
        for host in params["hosts"]:
            self.assertThat(
                config_output,
                ContainsAll(
                    [
                        dhcp_snippet["value"]
                        for dhcp_snippet in host["dhcp_snippets"]
                    ]
                ),
            )

    def test_renders_subnet_cidr(self):
        params = make_sample_params(self, ipv6=self.ipv6)
        config_output = config.get_config(self.template, **params)
        validate_dhcpd_configuration(self, config_output, self.ipv6)
        for shared_network in params["shared_networks"]:
            for subnet in shared_network["subnets"]:
                if self.ipv6 is True:
                    expected = "subnet6 %s" % subnet["subnet_cidr"]
                else:
                    expected = "subnet %s netmask %s" % (
                        subnet["subnet"],
                        subnet["subnet_mask"],
                    )
                self.assertThat(config_output, Contains(expected))


class TestGetConfigIPv4(MAASTestCase):
    """Tests for `get_config`."""

    def test_includes_next_server_in_config_from_all_addresses(self):
        params = make_sample_params(self, ipv6=False)
        subnet = params["shared_networks"][0]["subnets"][0]
        next_server_ip = factory.pick_ip_in_network(
            netaddr.IPNetwork(subnet["subnet_cidr"])
        )
        self.patch(net_utils, "get_all_interface_addresses").return_value = [
            next_server_ip
        ]
        config_output = config.get_config("dhcpd.conf.template", **params)
        validate_dhcpd_configuration(self, config_output, False)
        self.assertThat(
            config_output, Contains("next-server %s;" % next_server_ip)
        )

    def test_includes_next_server_in_config_from_interface_addresses(self):
        params = make_sample_params(self, ipv6=False, with_interface=True)
        subnet = params["shared_networks"][0]["subnets"][0]
        next_server_ip = factory.pick_ip_in_network(
            netaddr.IPNetwork(subnet["subnet_cidr"])
        )
        self.patch(
            net_utils, "get_all_addresses_for_interface"
        ).return_value = [next_server_ip]
        config_output = config.get_config("dhcpd.conf.template", **params)
        validate_dhcpd_configuration(self, config_output, False)
        self.assertThat(
            config_output, Contains("next-server %s;" % next_server_ip)
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
                self.assertThat(output, Contains("else"))
                self.assertThat(output, Contains(method.bootloader_path))
            elif method.arch_octet is not None:
                if isinstance(method.arch_octet, list):
                    self.assertThat(output, ContainsAll(method.arch_octet))
                else:
                    self.assertThat(output, Contains(method.arch_octet))
                self.assertThat(output, Contains(method.bootloader_path))
            else:
                # No DHCP configuration is rendered for boot methods that have
                # no `arch_octet`, with the solitary exception of PXE.
                pass
            if method.path_prefix_http or method.http_url:
                self.assertThat(output, Contains("http://%s:5248/" % ip))
            if method.path_prefix_force:
                self.assertThat(
                    output,
                    Contains("option dhcp-parameter-request-list = concat("),
                )
                self.assertThat(
                    output, Contains("option dhcp-parameter-request-list,d2);")
                )
            if method.http_url:
                self.assertThat(
                    output,
                    Contains('option vendor-class-identifier "HTTPClient";'),
                )

    def test_composes_bootloader_section_v6(self):
        ip = factory.make_ipv6_address()
        output = config.compose_conditional_bootloader(True, ip)
        for name, method in BootMethodRegistry:
            if name == "uefi":
                self.assertThat(output, Contains("else"))
                self.assertThat(output, Contains(method.bootloader_path))
            elif method.arch_octet is not None:
                if isinstance(method.arch_octet, list):
                    self.assertThat(output, ContainsAll(method.arch_octet))
                else:
                    self.assertThat(output, Contains(method.arch_octet))
                self.assertThat(output, Contains(method.bootloader_path))
            else:
                # No DHCP configuration is rendered for boot methods that have
                # no `arch_octet`, with the solitary exception of PXE.
                pass
            if method.path_prefix_http or method.http_url:
                self.assertThat(output, Contains("http://[%s]:5248/" % ip))
            if method.path_prefix_force:
                self.assertThat(
                    output,
                    Contains(
                        "option dhcp6.oro = concat(option dhcp6.oro,00d2);"
                    ),
                )
            if method.http_url:
                self.assertThat(
                    output,
                    Contains('option dhcp6.vendor-class 0 10 "HTTPClient";'),
                )


class TestGetAddresses(MAASTestCase):
    """Tests for `_get_addresses`."""

    def test_ip_addresses_are_passed_through(self):
        address4 = factory.make_ipv4_address()
        address6 = factory.make_ipv6_address()
        self.assertThat(
            config._get_addresses(address4, address6),
            Equals(([address4], [address6])),
        )

    def test_ignores_resolution_failures(self):
        # Some ISPs configure their DNS to resolve to an ads page when a domain
        # doesn't exist. This ensures resolving fails so the test passes.
        self.patch(config, "_gen_addresses_where_possible").return_value = []
        self.assertThat(
            config._get_addresses("no-way-this-exists.maas.io"),
            Equals(([], [])),
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
        self.assertThat(
            logger.output.strip(),
            DocTestMatches(
                "Could not resolve no-way-this-exists.maas.io: [Errno ...] ..."
            ),
        )
