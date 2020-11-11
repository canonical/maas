# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for NTP service configuration."""


from functools import partial
from itertools import chain
from random import randrange
import re

from netaddr import IPAddress
from testtools.matchers import (
    Contains,
    Equals,
    Is,
    IsInstance,
    MatchesStructure,
    StartsWith,
)

from maastesting.factory import factory
from maastesting.fixtures import MAASRootFixture
from maastesting.testcase import MAASTestCase
from provisioningserver.ntp import config
from provisioningserver.path import get_data_path


def read_configuration(path):
    with open(path, "r", encoding="utf-8") as fd:
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

    def setUp(self):
        super().setUp()
        self.useFixture(MAASRootFixture())

    def test_configure(self):
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
        offset = randrange(0, 5)
        config.configure(servers, peers, offset)
        ntp_conf_path = get_data_path("etc", config._ntp_conf_name)
        ntp_maas_conf_path = get_data_path("etc", config._ntp_maas_conf_name)
        ntp_conf = read_configuration(ntp_conf_path)
        self.assertThat(extract_servers_and_pools(ntp_conf), Equals([]))
        self.assertThat(
            extract_included_files(ntp_conf), Equals([ntp_maas_conf_path])
        )
        ntp_maas_conf = read_configuration(ntp_maas_conf_path)
        self.assertThat(
            extract_servers_and_pools(ntp_maas_conf), Equals(servers)
        )
        self.assertThat(extract_peers(ntp_maas_conf), Equals(peers))
        self.assertThat(
            extract_tos_options(ntp_maas_conf),
            Equals([str(offset + 8), "orphan"]),
        )

    def test_configure_region_is_alias(self):
        self.assertThat(config.configure_region, IsInstance(partial))
        self.assertThat(
            config.configure_region,
            MatchesStructure(
                func=Is(config.configure),
                args=Equals(()),
                keywords=Equals({"offset": 0}),
            ),
        )

    def test_configure_rack_is_alias(self):
        self.assertThat(config.configure_rack, IsInstance(partial))
        self.assertThat(
            config.configure_rack,
            MatchesStructure(
                func=Is(config.configure),
                args=Equals(()),
                keywords=Equals({"offset": 1}),
            ),
        )


class TestNormaliseAddress(MAASTestCase):
    """Tests for `p.ntp.config.normalise_address`."""

    def test_returns_hostnames_unchanged(self):
        hostname = factory.make_hostname()
        self.assertThat(config.normalise_address(hostname), Equals(hostname))

    def test_returns_ipv4_addresses_as_IPAddress(self):
        address = factory.make_ipv4_address()
        normalised = config.normalise_address(address)
        self.assertThat(normalised, IsInstance(IPAddress))
        self.assertThat(normalised.version, Equals(4))
        self.assertThat(str(normalised), Equals(address))

    def test_returns_ipv6_addresses_as_IPAddress(self):
        address = factory.make_ipv6_address()
        normalised = config.normalise_address(address)
        self.assertThat(normalised, IsInstance(IPAddress))
        self.assertThat(normalised.version, Equals(6))
        self.assertThat(str(normalised), Equals(address))

    def test_renders_ipv6_mapped_ipv4_addresses_as_plain_ipv4(self):
        address_as_ipv4 = factory.make_ipv4_address()
        address_as_ipv6 = str(IPAddress(address_as_ipv4).ipv6())
        normalised = config.normalise_address(address_as_ipv6)
        self.assertThat(normalised, IsInstance(IPAddress))
        self.assertThat(str(normalised), Equals(address_as_ipv4))


def extract_tos_options(configuration):
    commands = re.findall(
        r"^ *local stratum +([^\r\n]+)$", configuration, re.MULTILINE
    )
    return list(chain.from_iterable(map(str.split, commands)))


class TestRenderNTPConfFromSource(MAASTestCase):
    """Tests for `p.ntp.config._render_ntp_conf_from_source`."""

    def test_removes_pools_and_servers_from_source_configuration(self):
        ntp_maas_conf_path = factory.make_name(config._ntp_maas_conf_name)
        ntp_conf_lines = config._render_ntp_conf_from_source(
            example_ntp_conf.splitlines(keepends=True), ntp_maas_conf_path
        )
        servers_or_pools = extract_servers_and_pools("".join(ntp_conf_lines))
        self.assertThat(servers_or_pools, Equals([]))

    def test_includes_maas_configuration(self):
        ntp_maas_conf_path = factory.make_name(config._ntp_maas_conf_name)
        ntp_conf_lines = config._render_ntp_conf_from_source(
            example_ntp_conf.splitlines(keepends=True), ntp_maas_conf_path
        )
        included_files = extract_included_files("".join(ntp_conf_lines))
        self.assertThat(included_files, Equals([ntp_maas_conf_path]))

    def test_replaces_maas_configuration(self):
        ntp_maas_conf_path = factory.make_name(config._ntp_maas_conf_name)
        ntp_conf_lines = config._render_ntp_conf_from_source(
            example_ntp_conf.splitlines(keepends=True), ntp_maas_conf_path
        )
        ntp_conf_lines = config._render_ntp_conf_from_source(
            ntp_conf_lines, ntp_maas_conf_path
        )
        included_files = extract_included_files("".join(ntp_conf_lines))
        self.assertThat(included_files, Equals([ntp_maas_conf_path]))

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
        ntp_maas_conf_path = factory.make_name(config._ntp_maas_conf_name)
        ntp_conf_lines = config._render_ntp_conf_from_source(
            ntp_conf_lines, ntp_maas_conf_path
        )
        self.assertThat(
            list(ntp_conf_lines),
            Equals(
                [
                    "# chrony.conf\n",
                    "\n",
                    "foo",
                    "bar",
                    "\n",
                    "include %s\n" % ntp_maas_conf_path,
                ]
            ),
        )


class TestRenderNTPConf(MAASTestCase):
    """Tests for `p.ntp.config._render_ntp_conf`."""

    def test_removes_pools_and_servers_from_source_configuration(self):
        ntp_maas_conf_path = factory.make_name(config._ntp_maas_conf_name)
        ntp_conf = config._render_ntp_conf(ntp_maas_conf_path)
        servers_or_pools = extract_servers_and_pools(ntp_conf)
        self.assertThat(servers_or_pools, Equals([]))

    def test_includes_maas_configuration(self):
        ntp_maas_conf_path = factory.make_name(config._ntp_maas_conf_name)
        ntp_conf = config._render_ntp_conf(ntp_maas_conf_path)
        included_files = extract_included_files(ntp_conf)
        self.assertThat(included_files, Equals([ntp_maas_conf_path]))


class TestRenderNTPMAASConf(MAASTestCase):
    """Tests for `p.ntp.config._render_ntp_maas_conf`."""

    def test_renders_the_given_servers(self):
        servers = [
            factory.make_ipv4_address(),
            factory.make_ipv6_address(),
            factory.make_hostname(),
        ]
        ntp_maas_conf = config._render_ntp_maas_conf(servers, [], 0)
        self.assertThat(
            ntp_maas_conf, StartsWith("# MAAS NTP configuration.\n")
        )
        servers_or_pools = extract_servers_and_pools_full(ntp_maas_conf)
        # Hostnames are rendered as `pool` commands so that all IP addresses
        # resolved via DNS are included in clock selection.
        self.assertThat(
            servers_or_pools,
            Equals(
                [
                    ("server", servers[0], "iburst"),
                    ("server", servers[1], "iburst"),
                    ("pool", servers[2], "iburst"),
                ]
            ),
        )

    def test_renders_the_given_peers(self):
        peers = [
            factory.make_ipv4_address(),
            factory.make_ipv6_address(),
            factory.make_hostname(),
        ]
        ntp_maas_conf = config._render_ntp_maas_conf([], peers, 0)
        self.assertThat(
            ntp_maas_conf, StartsWith("# MAAS NTP configuration.\n")
        )
        observed_peers = extract_peers_full(ntp_maas_conf)
        self.assertThat(
            observed_peers, Equals([("peer", peer, "") for peer in peers])
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
        self.assertThat(observed_servers, Equals([server_as_ipv4]))
        observed_peers = extract_peers(ntp_maas_conf)
        self.assertThat(observed_peers, Equals([peer_as_ipv4]))

    def test_configures_orphan_mode(self):
        offset = randrange(0, 5)
        ntp_maas_conf = config._render_ntp_maas_conf([], [], offset)
        self.assertThat(
            extract_tos_options(ntp_maas_conf),
            Equals([str(offset + 8), "orphan"]),
        )

    def test_configures_hwtimestamp_mode(self):
        ntp_maas_conf = config._render_ntp_maas_conf([], [], 0)
        self.assertThat(ntp_maas_conf, Contains("\nhwtimestamp *\n"))


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
