# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.ntp`."""

__all__ = []

from maasserver.dbviews import register_view
from maasserver.models.config import Config
from maasserver.ntp import get_servers_for
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from testtools.matchers import (
    Equals,
    IsInstance,
    MatchesAll,
)


def IsSetOfServers(servers):
    return MatchesAll(
        IsInstance(frozenset),
        Equals(frozenset(servers)),
        first_only=True,
    )


IsEmptySetOfServers = IsSetOfServers(())


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
        self.assertThat(servers, IsEmptySetOfServers)

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


class TestGetServersFor_Region_RegionRack(TestGetServersFor_Common):
    """Tests `get_servers_for` for `RegionController` nodes."""

    scenarios = (
        ("region", {"make_node": factory.make_RegionController}),
        ("region+rack", {"make_node": factory.make_RegionRackController}),
    )

    def test_yields_nothing_when_no_ntp_servers_defined(self):
        Config.objects.set_config("ntp_servers", "")
        servers = get_servers_for(node=self.make_node())
        self.assertThat(servers, IsEmptySetOfServers)

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
