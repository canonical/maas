# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `metadataserver.vendor_data`."""

__all__ = []

from maasserver.models.config import Config
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from metadataserver.vendor_data import (
    generate_ntp_configuration,
    generate_system_info,
    get_vendor_data,
)
from netaddr import IPAddress
from testtools.matchers import (
    Contains,
    ContainsDict,
    Equals,
    Is,
    IsInstance,
    KeysEqual,
    MatchesDict,
    Not,
)


class TestGetVendorData(MAASServerTestCase):
    """Tests for `get_vendor_data`."""

    def test_returns_dict(self):
        node = factory.make_Node()
        self.assertThat(get_vendor_data(node), IsInstance(dict))

    def test_includes_no_system_information_if_no_default_user(self):
        node = factory.make_Node(owner=factory.make_User())
        vendor_data = get_vendor_data(node)
        self.assertThat(vendor_data, Not(Contains('system_info')))

    def test_includes_system_information_if_default_user(self):
        owner = factory.make_User()
        node = factory.make_Node(owner=owner, default_user=owner)
        vendor_data = get_vendor_data(node)
        self.assertThat(vendor_data, ContainsDict({
            "system_info": MatchesDict({
                "default_user": KeysEqual("name", "gecos"),
            }),
        }))

    def test_includes_ntp_server_information(self):
        Config.objects.set_config("ntp_external_only", True)
        Config.objects.set_config("ntp_servers", "foo bar")
        node = factory.make_Node()
        vendor_data = get_vendor_data(node)
        self.assertThat(vendor_data, ContainsDict({
            "ntp": Equals({
                "servers": [],
                "pools": ["bar", "foo"],
            }),
        }))


class TestGenerateSystemInfo(MAASServerTestCase):
    """Tests for `generate_system_info`."""

    def test_yields_nothing_when_node_has_no_owner(self):
        node = factory.make_Node()
        self.assertThat(node.owner, Is(None))
        configuration = generate_system_info(node)
        self.assertThat(dict(configuration), Equals({}))

    def test_yields_nothing_when_owner_and_no_default_user(self):
        node = factory.make_Node()
        self.assertThat(node.owner, Is(None))
        self.assertThat(node.default_user, Is(''))
        configuration = generate_system_info(node)
        self.assertThat(dict(configuration), Equals({}))

    def test_yields_basic_system_info_when_node_owned_with_default_user(self):
        owner = factory.make_User()
        owner.first_name = "First"
        owner.last_name = "Last"
        owner.save()
        node = factory.make_Node(owner=owner, default_user=owner)
        configuration = generate_system_info(node)
        self.assertThat(dict(configuration), Equals({
            "system_info": {
                "default_user": {
                    "name": owner.username,
                    "gecos": "First Last,,,,",
                },
            },
        }))


class TestGenerateNTPConfiguration(MAASServerTestCase):
    """Tests for `generate_ntp_configuration`."""

    def test_external_only_yields_nothing_when_no_ntp_servers_defined(self):
        Config.objects.set_config("ntp_external_only", True)
        Config.objects.set_config("ntp_servers", "")
        configuration = generate_ntp_configuration(node=factory.make_Node())
        self.assertThat(dict(configuration), Equals({}))

    def test_external_only_yields_all_ntp_servers_when_defined(self):
        Config.objects.set_config("ntp_external_only", True)
        ntp_hosts = factory.make_hostname(), factory.make_hostname()
        ntp_addrs = factory.make_ipv4_address(), factory.make_ipv6_address()
        ntp_servers = ntp_hosts + ntp_addrs
        Config.objects.set_config("ntp_servers", " ".join(ntp_servers))
        configuration = generate_ntp_configuration(node=factory.make_Node())
        self.assertThat(dict(configuration), Equals({
            "ntp": {
                "servers": sorted(ntp_addrs, key=IPAddress),
                "pools": sorted(ntp_hosts),
            },
        }))

    def test_yields_nothing_when_machine_has_no_boot_cluster_address(self):
        Config.objects.set_config("ntp_external_only", False)
        machine = factory.make_Machine()
        machine.boot_cluster_ip = None
        machine.save()
        configuration = generate_ntp_configuration(machine)
        self.assertThat(dict(configuration), Equals({}))

    def test_yields_boot_cluster_address_when_machine_has_booted(self):
        Config.objects.set_config("ntp_external_only", False)

        machine = factory.make_Machine()
        address = factory.make_StaticIPAddress(
            interface=factory.make_Interface(node=machine))

        rack_primary = factory.make_RackController(subnet=address.subnet)
        rack_primary_address = factory.make_StaticIPAddress(
            interface=factory.make_Interface(node=rack_primary),
            subnet=address.subnet)

        rack_secondary = factory.make_RackController(subnet=address.subnet)
        rack_secondary_address = factory.make_StaticIPAddress(
            interface=factory.make_Interface(node=rack_secondary),
            subnet=address.subnet)

        vlan = address.subnet.vlan
        vlan.primary_rack = rack_primary
        vlan.secondary_rack = rack_secondary
        vlan.dhcp_on = True
        vlan.save()

        configuration = generate_ntp_configuration(machine)
        self.assertThat(dict(configuration), Equals({
            "ntp": {
                "servers": sorted(
                    (rack_primary_address.ip, rack_secondary_address.ip),
                    key=IPAddress),
                "pools": [],
            },
        }))
