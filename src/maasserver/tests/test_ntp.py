# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.ntp`."""

__all__ = []

from operator import methodcaller

from maasserver.dbviews import register_view
from maasserver.models.config import Config
from maasserver.ntp import (
    get_peers_for,
    get_servers_for,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from netaddr import IPAddress
from testtools.matchers import (
    AfterPreprocessing,
    AllMatch,
    ContainsAll,
    Equals,
    HasLength,
    IsInstance,
    MatchesAll,
    MatchesStructure,
    Not,
)


def IsSetOfServers(servers):
    return MatchesAll(
        IsInstance(frozenset),
        Equals(frozenset(servers)),
        first_only=True,
    )


IsEmptySet = MatchesAll(
    IsInstance(frozenset),
    Equals(frozenset()),
    first_only=True,
)


IsIPv6Address = AfterPreprocessing(
    IPAddress, MatchesStructure(version=Equals(6)))


def populate_node_with_addresses(node, subnets):
    iface = factory.make_Interface(node=node)
    for subnet in subnets:
        factory.make_StaticIPAddress(interface=iface, subnet=subnet)


class TestGetServersFor_ExternalOnly(MAASServerTestCase):
    """Tests `get_servers_for` when `ntp_external_only` is set."""

    scenarios = (
        ("region", {"make_node": factory.make_RegionController}),
        ("region+rack", {"make_node": factory.make_RegionRackController}),
        ("rack", {"make_node": factory.make_RackController}),
        ("machine", {"make_node": factory.make_Machine}),
        ("device", {"make_node": factory.make_Device}),
    )

    def setUp(self):
        super(TestGetServersFor_ExternalOnly, self).setUp()
        Config.objects.set_config("ntp_external_only", True)

    def test_yields_nothing_when_no_ntp_servers_defined(self):
        Config.objects.set_config("ntp_servers", "")
        servers = get_servers_for(node=self.make_node())
        self.assertThat(servers, IsEmptySet)

    def test_yields_all_ntp_servers_when_defined(self):
        ntp_servers = factory.make_hostname(), factory.make_hostname()
        Config.objects.set_config("ntp_servers", " ".join(ntp_servers))
        servers = get_servers_for(node=self.make_node())
        self.assertThat(servers, IsSetOfServers(ntp_servers))


class TestGetServersFor_Common(MAASServerTestCase):
    """Common basis for tests of `get_servers_for`.

    This ensures that `ntp_external_only` is NOT set.
    """

    def setUp(self):
        super(TestGetServersFor_Common, self).setUp()
        Config.objects.set_config("ntp_external_only", False)


class TestGetServersFor_Region_RegionRack_None(TestGetServersFor_Common):
    """Tests `get_servers_for` for `RegionController` nodes.

    Also test for `None`, i.e. where there is no node.
    """

    scenarios = (
        ("region", {"make_node": factory.make_RegionController}),
        ("region+rack", {"make_node": factory.make_RegionRackController}),
        ("none", {"make_node": lambda: None}),
    )

    def test_yields_nothing_when_no_ntp_servers_defined(self):
        Config.objects.set_config("ntp_servers", "")
        servers = get_servers_for(node=self.make_node())
        self.assertThat(servers, IsEmptySet)

    def test_yields_all_ntp_servers_when_defined(self):
        ntp_servers = factory.make_hostname(), factory.make_hostname()
        Config.objects.set_config("ntp_servers", " ".join(ntp_servers))
        servers = get_servers_for(node=self.make_node())
        self.assertThat(servers, IsSetOfServers(ntp_servers))


class TestGetServersFor_Rack(TestGetServersFor_Common):
    """Tests `get_servers_for` for `RackController` nodes."""

    def test_yields_region_addresses(self):
        register_view("maasserver_routable_pairs")
        Config.objects.set_config("ntp_external_only", False)

        rack = factory.make_RackController()
        address = factory.make_StaticIPAddress(
            interface=factory.make_Interface(node=rack))

        region1 = factory.make_RegionController()
        region1_address = factory.make_StaticIPAddress(
            interface=factory.make_Interface(node=region1),
            subnet=address.subnet)

        region2 = factory.make_RegionController()
        region2_address = factory.make_StaticIPAddress(
            interface=factory.make_Interface(node=region2),
            subnet=address.subnet)

        servers = get_servers_for(rack)
        self.assertThat(servers, IsSetOfServers({
            region1_address.ip,
            region2_address.ip,
        }))


class TestGetServersFor_Machine(TestGetServersFor_Common):
    """Tests `get_servers_for` for `Machine` nodes."""

    def test_yields_rack_addresses_before_first_boot(self):
        register_view("maasserver_routable_pairs")

        machine = factory.make_Machine()
        machine.boot_cluster_ip = None
        machine.save()
        address = factory.make_StaticIPAddress(
            interface=factory.make_Interface(node=machine))

        rack1 = factory.make_RackController()
        rack1_address = factory.make_StaticIPAddress(
            interface=factory.make_Interface(node=rack1),
            subnet=address.subnet)

        rack2 = factory.make_RackController()
        rack2_address = factory.make_StaticIPAddress(
            interface=factory.make_Interface(node=rack2),
            subnet=address.subnet)

        servers = get_servers_for(machine)
        self.assertThat(servers, IsSetOfServers({
            rack1_address.ip,
            rack2_address.ip,
        }))

    def test_yields_boot_rack_addresses_when_machine_has_booted(self):
        register_view("maasserver_routable_pairs")

        machine = factory.make_Machine()
        address = factory.make_StaticIPAddress(
            interface=factory.make_Interface(node=machine))

        rack_primary = factory.make_RackController()
        rack_primary_address = factory.make_StaticIPAddress(
            interface=factory.make_Interface(node=rack_primary),
            subnet=address.subnet)

        rack_secondary = factory.make_RackController()
        rack_secondary_address = factory.make_StaticIPAddress(
            interface=factory.make_Interface(node=rack_secondary),
            subnet=address.subnet)

        rack_other = factory.make_RackController()
        rack_other_address = factory.make_StaticIPAddress(  # noqa
            interface=factory.make_Interface(node=rack_other),
            subnet=address.subnet)

        vlan = address.subnet.vlan
        vlan.primary_rack = rack_primary
        vlan.secondary_rack = rack_secondary
        vlan.dhcp_on = True
        vlan.save()

        servers = get_servers_for(machine)
        self.assertThat(servers, IsSetOfServers({
            rack_primary_address.ip,
            rack_secondary_address.ip,
        }))


class TestGetServersFor_Device(TestGetServersFor_Common):
    """Tests `get_servers_for` for `Device` nodes."""

    def test_yields_rack_addresses(self):
        register_view("maasserver_routable_pairs")

        device = factory.make_Device()
        address = factory.make_StaticIPAddress(
            interface=factory.make_Interface(node=device))

        rack1 = factory.make_RackController()
        rack1_address = factory.make_StaticIPAddress(
            interface=factory.make_Interface(node=rack1),
            subnet=address.subnet)

        rack2 = factory.make_RackController()
        rack2_address = factory.make_StaticIPAddress(
            interface=factory.make_Interface(node=rack2),
            subnet=address.subnet)

        servers = get_servers_for(device)
        self.assertThat(servers, IsSetOfServers({
            rack1_address.ip,
            rack2_address.ip,
        }))


class TestGetServersFor_Selection(MAASServerTestCase):
    """Tests the address selection mechanism for `get_servers_for`.

    For racks, machines, and devices, a selection process takes place to
    determine which of several candidate addresses per server to choose. This
    result is stable, i.e. it will choose the same address each time.
    """

    scenarios = (
        ("rack", {
            "make_node": factory.make_RackController,
            "make_server": factory.make_RegionController,
        }),
        ("machine", {
            "make_node": factory.make_Machine,
            "make_server": factory.make_RackController,
        }),
        ("device", {
            "make_node": factory.make_Device,
            "make_server": factory.make_RackController,
        }),
    )

    def setUp(self):
        super(TestGetServersFor_Selection, self).setUp()
        Config.objects.set_config("ntp_external_only", False)
        register_view("maasserver_routable_pairs")

    def test_prefers_ipv6_to_ipv4_peers_then_highest_numerically(self):
        subnet4 = factory.make_Subnet(version=4)
        subnet6a = factory.make_Subnet(version=6)
        subnet6b = factory.make_Subnet(version=6)
        # Ensure that addresses in subnet6a < those in subnet6b.
        subnet6a, subnet6b = sorted(
            {subnet6a, subnet6b}, key=methodcaller("get_ipnetwork"))
        # Create a node and server with an address in each subnet.
        node, server = self.make_node(), self.make_server()
        subnets = {subnet4, subnet6a, subnet6b}
        populate_node_with_addresses(node, subnets)
        populate_node_with_addresses(server, subnets)

        servers = get_servers_for(node)
        self.assertThat(servers, Not(HasLength(0)))
        self.assertThat(servers, AllMatch(IsIPv6Address))
        self.assertThat(subnet6b.get_ipnetwork(), ContainsAll(servers))


class TestGetPeersFor_Region_RegionRack(MAASServerTestCase):
    """Tests `get_peers_for` for region and region+rack controllers."""

    scenarios = (
        ("region", {"make_node": factory.make_RegionController}),
        ("region+rack", {"make_node": factory.make_RegionRackController}),
    )

    def setUp(self):
        super(TestGetPeersFor_Region_RegionRack, self).setUp()
        register_view("maasserver_routable_pairs")

    def test_yields_peer_addresses(self):
        node1 = self.make_node()
        node1_address = factory.make_StaticIPAddress(
            interface=factory.make_Interface(node=node1))
        node2 = self.make_node()
        node2_address = factory.make_StaticIPAddress(
            interface=factory.make_Interface(node=node2),
            subnet=node1_address.subnet)

        self.assertThat(
            get_peers_for(node1),
            IsSetOfServers({node2_address.ip}))
        self.assertThat(
            get_peers_for(node2),
            IsSetOfServers({node1_address.ip}))

    def test_prefers_ipv6_to_ipv4_peers_then_highest_numerically(self):
        subnet4 = factory.make_Subnet(version=4)
        subnet6a = factory.make_Subnet(version=6)
        subnet6b = factory.make_Subnet(version=6)
        # Ensure that addresses in subnet6a < those in subnet6b.
        subnet6a, subnet6b = sorted(
            {subnet6a, subnet6b}, key=methodcaller("get_ipnetwork"))
        # Create some peers, each with an address in each subnet.
        nodes = self.make_node(), self.make_node()
        subnets = {subnet4, subnet6a, subnet6b}
        for node in nodes:
            populate_node_with_addresses(node, subnets)
        for node in nodes:
            peers = get_peers_for(node)
            self.assertThat(peers, Not(HasLength(0)))
            self.assertThat(peers, AllMatch(IsIPv6Address))
            self.assertThat(subnet6b.get_ipnetwork(), ContainsAll(peers))


class TestGetPeersFor_Other(MAASServerTestCase):
    """Tests `get_peers_for` for other node types."""

    scenarios = (
        ("rack", {"make_node": factory.make_RackController}),
        ("machine", {"make_node": factory.make_Machine}),
        ("device", {"make_node": factory.make_Device}),
    )

    def test_yields_nothing(self):
        node1 = self.make_node()
        node1_address = factory.make_StaticIPAddress(
            interface=factory.make_Interface(node=node1))
        node2 = self.make_node()
        node2_address = factory.make_StaticIPAddress(  # noqa
            interface=factory.make_Interface(node=node2),
            subnet=node1_address.subnet)

        self.assertThat(get_peers_for(node1), IsEmptySet)
        self.assertThat(get_peers_for(node2), IsEmptySet)


class TestGetPeersFor_None(MAASServerTestCase):
    """Tests `get_peers_for` for `None`, i.e. where there is no node."""

    def test_yields_nothing(self):
        self.assertThat(get_peers_for(None), IsEmptySet)
