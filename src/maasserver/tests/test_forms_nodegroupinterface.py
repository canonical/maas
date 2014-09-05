# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test forms."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import random

from maasserver.enum import (
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.forms import (
    ERROR_MESSAGE_STATIC_RANGE_IN_USE,
    NodeGroupInterfaceForm,
    )
from maasserver.models import (
    Network,
    NodeGroupInterface,
    )
from maasserver.models.network import get_name_and_vlan_from_cluster_interface
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import MockCalledOnceWith
from netaddr import (
    IPAddress,
    IPNetwork,
    )
from testtools.matchers import (
    AllMatch,
    Equals,
    MatchesStructure,
    StartsWith,
    )


nullable_fields = [
    'subnet_mask', 'broadcast_ip', 'router_ip', 'ip_range_low',
    'ip_range_high', 'static_ip_range_low', 'static_ip_range_high',
    ]


def make_ngi_instance(nodegroup=None):
    """Create a `NodeGroupInterface` with nothing set but `nodegroup`.

    This is used by tests to instantiate the cluster interface form for
    a given cluster.  We create an initial cluster interface object just
    to tell it which cluster that is.
    """
    if nodegroup is None:
        nodegroup = factory.make_NodeGroup()
    return NodeGroupInterface(nodegroup=nodegroup)


class TestNodeGroupInterfaceForm(MAASServerTestCase):

    def test__validates_parameters(self):
        form = NodeGroupInterfaceForm(
            data={'ip': factory.make_string()},
            instance=make_ngi_instance())
        self.assertFalse(form.is_valid())
        self.assertEquals(
            {'ip': ['Enter a valid IPv4 or IPv6 address.']}, form._errors)

    def test__can_save_fields_being_None(self):
        int_settings = factory.get_interface_fields()
        int_settings['management'] = NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED
        for field_name in nullable_fields:
            del int_settings[field_name]
        form = NodeGroupInterfaceForm(
            data=int_settings, instance=make_ngi_instance())
        interface = form.save()
        field_values = [
            getattr(interface, field_name) for field_name in nullable_fields]
        self.assertThat(field_values, AllMatch(Equals('')))

    def test__uses_name_if_given(self):
        name = factory.make_name('explicit-name')
        int_settings = factory.get_interface_fields()
        int_settings['name'] = name
        form = NodeGroupInterfaceForm(
            data=int_settings, instance=make_ngi_instance())
        interface = form.save()
        self.assertEqual(name, interface.name)

    def test__lets_name_default_to_network_interface_name(self):
        int_settings = factory.get_interface_fields()
        int_settings['interface'] = factory.make_name('ether')
        del int_settings['name']
        form = NodeGroupInterfaceForm(
            data=int_settings, instance=make_ngi_instance())
        interface = form.save()
        self.assertEqual(int_settings['interface'], interface.name)

    def test__escapes_interface_name(self):
        int_settings = factory.get_interface_fields()
        int_settings['interface'] = 'eth1+1'
        del int_settings['name']
        form = NodeGroupInterfaceForm(
            data=int_settings, instance=make_ngi_instance())
        interface = form.save()
        self.assertEqual('eth1--1', interface.name)

    def test__defaults_to_unique_name_if_no_name_or_interface_given(self):
        int_settings = factory.get_interface_fields(
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        del int_settings['name']
        del int_settings['interface']
        form1 = NodeGroupInterfaceForm(
            data=int_settings, instance=make_ngi_instance())
        interface1 = form1.save()
        form2 = NodeGroupInterfaceForm(
            data=int_settings, instance=make_ngi_instance())
        interface2 = form2.save()
        self.assertNotIn(interface1.name, [None, ''])
        self.assertNotIn(interface2.name, [None, ''])
        self.assertNotEqual(interface1.name, interface2.name)

    def test__disambiguates_default_name(self):
        cluster = factory.make_NodeGroup()
        existing_interface = factory.make_NodeGroupInterface(cluster)
        int_settings = factory.get_interface_fields()
        del int_settings['name']
        int_settings['interface'] = existing_interface.name
        form = NodeGroupInterfaceForm(
            data=int_settings, instance=make_ngi_instance(cluster))
        interface = form.save()
        self.assertThat(interface.name, StartsWith(int_settings['interface']))
        self.assertNotEqual(int_settings['interface'], interface.name)

    def test__disambiguates_IPv4_interface_with_ipv4_suffix(self):
        cluster = factory.make_NodeGroup()
        existing_interface = factory.make_NodeGroupInterface(
            cluster, network=factory.getRandomNetwork())
        int_settings = factory.get_interface_fields()
        del int_settings['name']
        int_settings['interface'] = existing_interface.name
        form = NodeGroupInterfaceForm(
            data=int_settings, instance=make_ngi_instance(cluster))
        interface = form.save()
        self.assertEqual('%s-ipv4' % int_settings['interface'], interface.name)

    def test__disambiguates_IPv6_interface_with_ipv6_suffix(self):
        cluster = factory.make_NodeGroup()
        existing_interface = factory.make_NodeGroupInterface(cluster)
        int_settings = factory.get_interface_fields(
            network=factory.make_ipv6_network(slash=64))
        del int_settings['name']
        int_settings['interface'] = existing_interface.name
        form = NodeGroupInterfaceForm(
            data=int_settings, instance=make_ngi_instance(cluster))
        interface = form.save()
        self.assertThat(
            interface.name,
            StartsWith('%s-ipv6-' % int_settings['interface']))

    def test__requires_netmask_on_managed_IPv4_interface(self):
        network = factory.getRandomNetwork()
        int_settings = factory.get_interface_fields(
            network=network, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        del int_settings['subnet_mask']
        form = NodeGroupInterfaceForm(
            data=int_settings, instance=make_ngi_instance())
        self.assertFalse(form.is_valid())

    def test__lets_netmask_default_to_64_bits_on_IPv6(self):
        network = factory.make_ipv6_network()
        int_settings = factory.get_interface_fields(
            network=network, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        del int_settings['subnet_mask']
        form = NodeGroupInterfaceForm(
            data=int_settings, instance=make_ngi_instance())
        self.assertTrue(form.is_valid())
        interface = form.save()
        self.assertEqual(
            IPAddress('ffff:ffff:ffff:ffff::'),
            IPAddress(interface.subnet_mask))

    def test__rejects_netmasks_other_than_64_bits_on_IPv6(self):
        network = factory.make_ipv6_network()
        int_settings = factory.get_interface_fields(
            network=network, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            netmask='ffff:ffff::')
        form = NodeGroupInterfaceForm(
            data=int_settings, instance=make_ngi_instance())
        self.assertFalse(form.is_valid())

    def test_validates_new_static_ip_ranges(self):
        network = IPNetwork("10.1.0.0/24")
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
            network=network)
        [interface] = nodegroup.get_managed_interfaces()
        StaticIPAddress.objects.allocate_new(
            interface.static_ip_range_low, interface.static_ip_range_high)
        form = NodeGroupInterfaceForm(
            data={'static_ip_range_low': '', 'static_ip_range_high': ''},
            instance=interface)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            [ERROR_MESSAGE_STATIC_RANGE_IN_USE],
            form._errors['static_ip_range_low'])
        self.assertEqual(
            [ERROR_MESSAGE_STATIC_RANGE_IN_USE],
            form._errors['static_ip_range_high'])

    def test_calls_get_duplicate_fqdns_when_appropriate(self):
        # Check for duplicate FQDNs if the NodeGroupInterface has a
        # NodeGroup and is managing DNS.
        int_settings = factory.get_interface_fields(
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        form = NodeGroupInterfaceForm(
            data=int_settings, instance=make_ngi_instance())
        mock = self.patch(form, "get_duplicate_fqdns")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertThat(mock, MockCalledOnceWith())

    def test_reports_error_if_fqdns_duplicated(self):
        int_settings = factory.get_interface_fields(
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        form = NodeGroupInterfaceForm(
            data=int_settings, instance=make_ngi_instance())
        mock = self.patch(form, "get_duplicate_fqdns")
        hostnames = [
            factory.make_hostname("duplicate") for _ in range(0, 3)]
        mock.return_value = hostnames
        self.assertFalse(form.is_valid())
        message = "Enabling DNS management creates duplicate FQDN(s): %s." % (
            ", ".join(set(hostnames)))
        self.assertEqual(
            {'management': [message]},
            form.errors)

    def test_identifies_duplicate_fqdns_in_nodegroup(self):
        # Don't allow DNS management to be enabled when it would
        # cause more than one node on the nodegroup to have the
        # same FQDN.
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        base_hostname = factory.make_hostname("host")
        full_hostnames = [
            "%s.%s" % (base_hostname, factory.make_hostname("domain"))
            for _ in range(0, 2)]
        for hostname in full_hostnames:
            factory.make_Node(hostname=hostname, nodegroup=nodegroup)
        [interface] = nodegroup.get_managed_interfaces()
        data = {"management": NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS}
        form = NodeGroupInterfaceForm(data=data, instance=interface)
        duplicates = form.get_duplicate_fqdns()
        expected_duplicates = set(["%s.%s" % (base_hostname, nodegroup.name)])
        self.assertEqual(expected_duplicates, duplicates)

    def test_identifies_duplicate_fqdns_across_nodegroups(self):
        # Don't allow DNS management to be enabled when it would
        # cause a node in this nodegroup to have the same FQDN
        # as a node in another nodegroup.

        conflicting_domain = factory.make_hostname("conflicting-domain")
        nodegroup_a = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            name=conflicting_domain)
        conflicting_hostname = factory.make_hostname("conflicting-hostname")
        factory.make_Node(
            hostname="%s.%s" % (conflicting_hostname, conflicting_domain),
            nodegroup=nodegroup_a)

        nodegroup_b = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            name=conflicting_domain)
        factory.make_Node(
            hostname="%s.%s" % (
                conflicting_hostname, factory.make_hostname("other-domain")),
            nodegroup=nodegroup_b)

        [interface] = nodegroup_b.get_managed_interfaces()
        data = {"management": NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS}
        form = NodeGroupInterfaceForm(data=data, instance=interface)
        duplicates = form.get_duplicate_fqdns()
        expected_duplicates = set(
            ["%s.%s" % (conflicting_hostname, conflicting_domain)])
        self.assertEqual(expected_duplicates, duplicates)


class TestNodeGroupInterfaceFormNetworkCreation(MAASServerTestCase):
    """Tests for when NodeGroupInterfaceForm creates a Network."""

    def test_creates_network_name(self):
        int_settings = factory.get_interface_fields()
        int_settings['interface'] = 'eth0:1'
        interface = make_ngi_instance()
        form = NodeGroupInterfaceForm(data=int_settings, instance=interface)
        form.save()
        [network] = Network.objects.all()
        expected, _ = get_name_and_vlan_from_cluster_interface(interface)
        self.assertEqual(expected, network.name)

    def test_sets_vlan_tag(self):
        int_settings = factory.get_interface_fields()
        vlan_tag = random.randint(1, 10)
        int_settings['interface'] = 'eth0.%s' % vlan_tag
        interface = make_ngi_instance()
        form = NodeGroupInterfaceForm(data=int_settings, instance=interface)
        form.save()
        [network] = Network.objects.all()
        self.assertEqual(vlan_tag, network.vlan_tag)

    def test_vlan_tag_is_None_if_no_vlan(self):
        int_settings = factory.get_interface_fields()
        int_settings['interface'] = 'eth0:1'
        interface = make_ngi_instance()
        form = NodeGroupInterfaceForm(data=int_settings, instance=interface)
        form.save()
        [network] = Network.objects.all()
        self.assertIs(None, network.vlan_tag)

    def test_sets_network_values(self):
        int_settings = factory.get_interface_fields()
        interface = make_ngi_instance()
        form = NodeGroupInterfaceForm(data=int_settings, instance=interface)
        form.save()
        [network] = Network.objects.all()
        expected_net_address = unicode(interface.network.network)
        expected_netmask = unicode(interface.network.netmask)
        self.assertThat(
            network, MatchesStructure.byEquality(
                ip=expected_net_address,
                netmask=expected_netmask))

    def test_does_not_create_new_network_if_already_exists(self):
        int_settings = factory.get_interface_fields()
        interface = make_ngi_instance()
        form = NodeGroupInterfaceForm(data=int_settings, instance=interface)
        # The easiest way to pre-create the same network is just to save
        # the form twice.
        form.save()
        [existing_network] = Network.objects.all()
        form.save()
        self.assertItemsEqual([existing_network], Network.objects.all())

    def test_creates_many_unique_networks(self):
        names = ('eth0', 'eth0:1', 'eth0.1', 'eth0:1.2')
        for name in names:
            int_settings = factory.get_interface_fields()
            int_settings['interface'] = name
            interface = make_ngi_instance()
            form = NodeGroupInterfaceForm(
                data=int_settings, instance=interface)
            form.save()

        self.assertEqual(len(names), len(Network.objects.all()))
