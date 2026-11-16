# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for NTP service configuration."""

from functools import partial
from itertools import chain
import os.path
import re
from shutil import rmtree

from netaddr import IPAddress

from maastesting.factory import factory
from maastesting.fixtures import MAASRootFixture
from maastesting.testcase import MAASTestCase
from provisioningserver.ntp import config
from provisioningserver.path import get_tentative_data_path


def read_configuration(path):
    with open(path, encoding="utf-8") as fd:
        return fd.read()


def extract_servers_and_pools(configuration):
    return [
        address
        for _, address, _ in extract_servers_and_pools_full(configuration)
    ]


def extract_servers_and_pools_full(configuration):
    return re.findall(
        r"^ *(server|pool) +(\S+)(?: +([^\r\n]+))?$",
        configuration,
        re.MULTILINE,
    )


def extract_peers(configuration):
    return [address for _, address, _ in extract_peers_full(configuration)]


def extract_peers_full(configuration):
    # We expect each peer to be annotated with `xleave`, so include that
    # in the regular expression as well.
    return re.findall(
        r"^ *(peer) +(\S+) xleave(?: +([^\r\n]+))?$",
        configuration,
        re.MULTILINE,
    )


def extract_included_files(configuration):
    return re.findall(
        r" ^ \s* include \s+ (\S*) $ ",
        configuration,
        re.VERBOSE | re.MULTILINE,
    )


class TestConfigure(MAASTestCase):
    """Tests for `p.ntp.config.configure`."""

    def test_configure(self):
        self.useFixture(MAASRootFixture())
        servers = [
            factory.make_ipv4_address(),
            factory.make_ipv6_address(),
            factory.make_hostname(),
        ]
        peers = [
            factory.make_ipv4_address(),
            factory.make_ipv6_address(),
            factory.make_hostname(),
        ]
        offset = 3
        config.configure(servers, peers, offset)
        ntp_conf_path = get_tentative_data_path("etc", config._NTP_CONF_NAME)
        ntp_maas_conf_path = get_tentative_data_path(
            "etc", config._NTP_MAAS_CONF_NAME
        )
        ntp_conf = read_configuration(ntp_conf_path)
        self.assertEqual([], extract_servers_and_pools(ntp_conf))
        self.assertEqual(
            [ntp_maas_conf_path], extract_included_files(ntp_conf)
        )
        ntp_maas_conf = read_configuration(ntp_maas_conf_path)
        self.assertEqual(servers, extract_servers_and_pools(ntp_maas_conf))
        self.assertEqual(peers, extract_peers(ntp_maas_conf))
        # orphan is offset + 8
        self.assertEqual(
            ["11", "orphan"],
            extract_tos_options(ntp_maas_conf),
        )

    def test_configure_creates_missing_dir(self):
        self.useFixture(MAASRootFixture())
        chrony_dir = get_tentative_data_path("etc", "chrony")
        rmtree(chrony_dir)
        config.configure([], [], 0)
        self.assertTrue(os.path.isdir(chrony_dir))

    def test_configure_region_is_alias(self):
        self.assertIsInstance(config.configure_region, partial)
        self.assertIs(config.configure_region.func, config.configure)
        self.assertEqual(config.configure_region.args, ())
        self.assertEqual(config.configure_region.keywords, {"offset": 0})

    def test_configure_rack_is_alias(self):
        self.assertIsInstance(config.configure_rack, partial)
        self.assertIs(config.configure_rack.func, config.configure)
        self.assertEqual(config.configure_rack.args, ())
        self.assertEqual(config.configure_rack.keywords, {"offset": 1})


class TestNormaliseAddress(MAASTestCase):
    """Tests for `p.ntp.config.normalise_address`."""

    def test_returns_hostnames_unchanged(self):
        hostname = factory.make_hostname()
        self.assertEqual(hostname, config.normalise_address(hostname))

    def test_returns_ipv4_addresses_as_IPAddress(self):
        address = factory.make_ipv4_address()
        normalised = config.normalise_address(address)
        self.assertIsInstance(normalised, IPAddress)
        self.assertEqual(4, normalised.version)
        self.assertEqual(address, str(normalised))

    def test_returns_ipv6_addresses_as_IPAddress(self):
        address = factory.make_ipv6_address()
        normalised = config.normalise_address(address)
        self.assertIsInstance(normalised, IPAddress)
        self.assertEqual(6, normalised.version)
        self.assertEqual(address, str(normalised))

    def test_renders_ipv6_mapped_ipv4_addresses_as_plain_ipv4(self):
        address_as_ipv4 = factory.make_ipv4_address()
        address_as_ipv6 = str(IPAddress(address_as_ipv4).ipv6())
        normalised = config.normalise_address(address_as_ipv6)
        self.assertIsInstance(normalised, IPAddress)
        self.assertEqual(address_as_ipv4, str(normalised))


def extract_tos_options(configuration):
    commands = re.findall(
        r"^ *local stratum +([^\r\n]+)$", configuration, re.MULTILINE
    )
    return list(chain.from_iterable(map(str.split, commands)))


class TestRenderNTPConfFromSource(MAASTestCase):
    """Tests for `p.ntp.config._render_ntp_conf_from_source`."""

    def test_removes_pools_and_servers_from_source_configuration(self):
        ntp_maas_conf_path = factory.make_name(config._NTP_MAAS_CONF_NAME)
        ntp_conf_lines = config._render_ntp_conf_from_source(
            example_ntp_conf.splitlines(keepends=True), ntp_maas_conf_path
        )
        servers_or_pools = extract_servers_and_pools("".join(ntp_conf_lines))
        self.assertEqual([], servers_or_pools)

    def test_includes_maas_configuration(self):
        ntp_maas_conf_path = factory.make_name(config._NTP_MAAS_CONF_NAME)
        ntp_conf_lines = config._render_ntp_conf_from_source(
            example_ntp_conf.splitlines(keepends=True), ntp_maas_conf_path
        )
        included_files = extract_included_files("".join(ntp_conf_lines))
        self.assertEqual([ntp_maas_conf_path], included_files)

    def test_replaces_maas_configuration(self):
        ntp_maas_conf_path = factory.make_name(config._NTP_MAAS_CONF_NAME)
        ntp_conf_lines = config._render_ntp_conf_from_source(
            example_ntp_conf.splitlines(keepends=True), ntp_maas_conf_path
        )
        ntp_conf_lines = config._render_ntp_conf_from_source(
            ntp_conf_lines, ntp_maas_conf_path
        )
        included_files = extract_included_files("".join(ntp_conf_lines))
        self.assertEqual([ntp_maas_conf_path], included_files)

    def test_cleans_up_whitespace(self):
        ntp_conf_lines = [
            "# chrony.conf\n",
            "\n",
            "   \n",
            "\t\r\n",
            "foo",
            "bar",
            "\n",
            "\n",
        ]
        ntp_maas_conf_path = factory.make_name(config._NTP_MAAS_CONF_NAME)
        ntp_conf_lines = config._render_ntp_conf_from_source(
            ntp_conf_lines, ntp_maas_conf_path
        )
        self.assertEqual(
            list(ntp_conf_lines),
            [
                "# chrony.conf\n",
                "\n",
                "foo",
                "bar",
                "\n",
                "include %s\n" % ntp_maas_conf_path,
            ],
        )


class TestRenderNTPConf(MAASTestCase):
    """Tests for `p.ntp.config._render_ntp_conf`."""

    def test_removes_pools_and_servers_from_source_configuration(self):
        ntp_maas_conf_path = factory.make_name(config._NTP_MAAS_CONF_NAME)
        ntp_conf = config._render_ntp_conf(ntp_maas_conf_path)
        servers_or_pools = extract_servers_and_pools(ntp_conf)
        self.assertEqual([], servers_or_pools)

    def test_includes_maas_configuration(self):
        ntp_maas_conf_path = factory.make_name(config._NTP_MAAS_CONF_NAME)
        ntp_conf = config._render_ntp_conf(ntp_maas_conf_path)
        included_files = extract_included_files(ntp_conf)
        self.assertEqual([ntp_maas_conf_path], included_files)


class TestRenderNTPMAASConf(MAASTestCase):
    """Tests for `p.ntp.config._render_ntp_maas_conf`."""

    def test_renders_the_given_servers(self):
        servers = [
            factory.make_ipv4_address(),
            factory.make_ipv6_address(),
            factory.make_hostname(),
        ]
        ntp_maas_conf = config._render_ntp_maas_conf(servers, [], 0)
        self.assertTrue(
            ntp_maas_conf.startswith("# MAAS NTP configuration.\n")
        )
        servers_or_pools = extract_servers_and_pools_full(ntp_maas_conf)
        # Hostnames are rendered as `pool` commands so that all IP addresses
        # resolved via DNS are included in clock selection.
        self.assertEqual(
            servers_or_pools,
            [
                ("server", servers[0], "iburst"),
                ("server", servers[1], "iburst"),
                ("pool", servers[2], "iburst"),
            ],
        )

    def test_renders_the_given_peers(self):
        peers = [
            factory.make_ipv4_address(),
            factory.make_ipv6_address(),
            factory.make_hostname(),
        ]
        ntp_maas_conf = config._render_ntp_maas_conf([], peers, 0)
        self.assertTrue(
            ntp_maas_conf.startswith("# MAAS NTP configuration.\n")
        )
        observed_peers = extract_peers_full(ntp_maas_conf)
        self.assertEqual(
            [("peer", peer, "") for peer in peers], observed_peers
        )

    def test_renders_ipv6_mapped_ipv4_addresses_as_plain_ipv4(self):
        server_as_ipv4 = factory.make_ipv4_address()
        server_as_ipv6 = str(IPAddress(server_as_ipv4).ipv6())
        peer_as_ipv4 = factory.make_ipv4_address()
        peer_as_ipv6 = str(IPAddress(peer_as_ipv4).ipv6())
        ntp_maas_conf = config._render_ntp_maas_conf(
            [server_as_ipv6], [peer_as_ipv6], 0
        )
        observed_servers = extract_servers_and_pools(ntp_maas_conf)
        self.assertEqual([server_as_ipv4], observed_servers)
        observed_peers = extract_peers(ntp_maas_conf)
        self.assertEqual([peer_as_ipv4], observed_peers)

    def test_configures_orphan_mode(self):
        offset = 3
        ntp_maas_conf = config._render_ntp_maas_conf([], [], offset)
        # orphan is offset + 8
        self.assertEqual(
            ["11", "orphan"],
            extract_tos_options(ntp_maas_conf),
        )

    def test_configures_hwtimestamp_mode(self):
        ntp_maas_conf = config._render_ntp_maas_conf([], [], 0)
        self.assertIn("\nhwtimestamp *\n", ntp_maas_conf)


example_ntp_conf = """\
# Welcome to the chrony configuration file. See chrony.conf(5) for more
# information about usuable directives.

# Use servers from the NTP Pool Project. Approved by Ubuntu Technical Board
# on 2011-02-08 (LP: #104525). See http://www.pool.ntp.org/join.html for
# more information.
pool 0.ubuntu.pool.ntp.org iburst
pool 1.ubuntu.pool.ntp.org iburst
pool 2.ubuntu.pool.ntp.org iburst
pool 3.ubuntu.pool.ntp.org iburst

# Use Ubuntu's ntp server as a fallback.
pool ntp.ubuntu.com

# This directive specify the location of the file containing ID/key pairs for
# NTP authentication.
keyfile /etc/chrony/chrony.keys

# This directive specify the file into which chronyd will store the rate
# information.
driftfile /var/lib/chrony/chrony.drift

# Uncomment the following line to turn logging on.
#log tracking measurements statistics

# Log files location.
logdir /var/log/chrony

# Stop bad estimates upsetting machine clock.
maxupdateskew 100.0

# This directive enables kernel synchronisation (every 11 minutes) of the
# real-time clock. Note that it can’t be used along with the 'rtcfile'
# directive.
rtcsync

# Step the system clock instead of slewing it if the adjustment is larger than
# one second, but only in the first three clock updates.
makestep 1 3
"""
