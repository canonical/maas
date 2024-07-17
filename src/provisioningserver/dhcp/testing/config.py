# Copyright 2014-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test helpers related to DHCP configuration."""

from itertools import cycle
import random

from fixtures import Fixture
from netaddr import IPAddress
from testtools.monkey import patch

from maastesting.factory import factory
from provisioningserver.dhcp import config


def fix_shared_networks_failover(shared_networks, failover_peers):
    # Fix-up failover peers referenced in pools so that they refer to a
    # predefined peer; `dhcpd -t` will otherwise reject the configuration.
    failover_peers_iter = cycle(failover_peers)
    for shared_network in shared_networks:
        for subnet in shared_network["subnets"]:
            for pool in subnet["pools"]:
                peer = next(failover_peers_iter)
                pool["failover_peer"] = peer["name"]
    return shared_networks


def make_subnet_pool(
    network, start_ip=None, end_ip=None, failover_peer=None, dhcp_snippets=None
):
    """Return a pool entry for a subnet from network."""
    if start_ip is None and end_ip is None:
        start_ip, end_ip = factory.make_ip_range(network)
    if failover_peer is None:
        failover_peer = factory.make_name("failover")
    if dhcp_snippets is None:
        dhcp_snippets = make_pool_dhcp_snippets()
    pool = {
        "ip_range_low": str(start_ip),
        "ip_range_high": str(end_ip),
        "failover_peer": failover_peer,
        "dhcp_snippets": dhcp_snippets,
    }
    return pool


def _make_snippets(count, template):
    names = (factory.make_name("name") for _ in range(count))
    return [
        {
            "name": name,
            "description": factory.make_name("description"),
            "value": template % name,
        }
        for name in names
    ]


def make_global_dhcp_snippets(allow_empty=True):
    count = random.randrange((0 if allow_empty else 1), 3)
    return _make_snippets(count, "group { next-server %s; }")


def make_subnet_dhcp_snippets(allow_empty=True):
    count = random.randrange((0 if allow_empty else 1), 3)
    return _make_snippets(count, "option pop-server %s;")


def make_host_dhcp_snippets(allow_empty=True):
    count = random.randrange((0 if allow_empty else 1), 3)
    return _make_snippets(count, "option smtp-server %s;")


def make_pool_dhcp_snippets(allow_empty=True):
    count = random.randrange((0 if allow_empty else 1), 3)
    return _make_snippets(count, "option nntp-server %s;")


def make_host(
    hostname=None,
    interface_name=None,
    mac_address=None,
    ip=None,
    ipv6=False,
    dhcp_snippets=None,
):
    """Return a host entry for a subnet from network."""
    if hostname is None:
        hostname = factory.make_name("host")
    if interface_name is None:
        interface_name = factory.make_name("eth")
    if mac_address is None:
        mac_address = factory.make_mac_address()
    if ip is None:
        ip = factory.make_ip_address(ipv6=ipv6)
    if dhcp_snippets is None:
        dhcp_snippets = make_host_dhcp_snippets()
    return {
        "host": f"{hostname}-{interface_name}",
        "mac": mac_address,
        "ip": ip,
        "dhcp_snippets": dhcp_snippets,
    }


def make_subnet_config(
    network=None,
    pools=None,
    ipv6=False,
    dhcp_snippets=None,
    disabled_boot_architectures=None,
):
    """Return complete DHCP configuration dict for a subnet."""
    if network is None:
        if ipv6 is True:
            network = factory.make_ipv6_network(
                # The dynamic range must be at least 256 hosts in size.
                slash=random.randint(112, 120)
            )
        else:
            network = factory.make_ipv4_network()
    if pools is None:
        pools = [make_subnet_pool(network)]
    if dhcp_snippets is None:
        dhcp_snippets = make_subnet_dhcp_snippets()
    domain_name = "%s.example.com" % factory.make_name("domain")
    return {
        "subnet": str(IPAddress(network.first)),
        "subnet_mask": str(network.netmask),
        "subnet_cidr": str(network.cidr),
        "broadcast_ip": str(network.broadcast),
        "dns_servers": [
            IPAddress(factory.pick_ip_in_network(network)),
            IPAddress(factory.pick_ip_in_network(network)),
        ],
        "ntp_servers": [
            factory.make_ipv4_address(),
            factory.make_ipv6_address(),
            factory.make_name("ntp-server"),
        ],
        "domain_name": domain_name,
        "search_list": [domain_name],
        "router_ip": factory.pick_ip_in_network(network),
        "pools": pools,
        "dhcp_snippets": dhcp_snippets,
        "disabled_boot_architectures": (
            disabled_boot_architectures if disabled_boot_architectures else []
        ),
    }


def make_shared_network(
    name=None,
    subnets=None,
    ipv6=False,
    with_interface=False,
    disabled_boot_architectures=None,
):
    """Return complete DHCP configuration dict for a shared network."""
    if name is None:
        name = factory.make_name("vlan")
    if subnets is None:
        subnets = [
            make_subnet_config(
                ipv6=ipv6,
                disabled_boot_architectures=disabled_boot_architectures,
            )
            for _ in range(3)
        ]
    data = {"name": name, "mtu": 1500, "subnets": subnets}
    if with_interface:
        data["interface"] = factory.make_name("eth")
    return data


def make_failover_peer_config(
    name=None, mode=None, address=None, peer_address=None
):
    """Return complete DHCP configuration dict for a failover peer."""
    if name is None:
        name = factory.make_name("failover")
    if mode is None:
        mode = random.choice(["primary", "secondary"])
    if address is None:
        # XXX: GavinPanella 2016-07-26 bug=1606508: Only IPv4 peers are
        # supported. Failover may not actually be necessary for IPv6.
        address = factory.make_ipv4_address()
    if peer_address is None:
        # XXX: GavinPanella 2016-07-26 bug=1606508: Only IPv4 peers are
        # supported. Failover may not actually be necessary for IPv6.
        peer_address = factory.make_ipv4_address()
    return {
        "name": name,
        "mode": mode,
        "address": address,
        "peer_address": peer_address,
    }


def make_interface(name=None):
    if name is None:
        name = factory.make_name("eth")
    return {"name": name}


class DHCPConfigNameResolutionDisabled(Fixture):
    """Prevent hostname resolution when generating DHCP configuration."""

    def _setUp(self):
        assert hasattr(config, "_gen_addresses")
        restore = patch(config, "_gen_addresses", self._genRandomAddresses)
        self.addCleanup(restore)

    def _genRandomAddresses(self, hostname):
        # Mimic config._gen_addresses by yielding a random IPv4 address and a
        # random IPv6 address.
        yield 4, factory.make_ipv4_address()
        yield 6, factory.make_ipv6_address()
