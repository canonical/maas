# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
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
    ERROR_MESSAGE_DYNAMIC_RANGE_SPANS_SLASH_16S,
    ERROR_MESSAGE_STATIC_RANGE_IN_USE,
    NodeGroupInterfaceForm,
)
from maasserver.models import (
    Fabric,
    NodeGroupInterface,
    VLAN,
)
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
    Contains,
    Equals,
    StartsWith,
)


nullable_fields = [
    'subnet_mask',
    'router_ip',
    'ip_range_low',
    'ip_range_high',
    'static_ip_range_low',
    'static_ip_range_high',
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
        self.assertTrue(form.is_valid())
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
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertEqual(name, interface.name)

    def test__lets_name_default_to_network_interface_name(self):
        int_settings = factory.get_interface_fields()
        int_settings['interface'] = factory.make_name('ether')
        del int_settings['name']
        form = NodeGroupInterfaceForm(
            data=int_settings, instance=make_ngi_instance())
        self.assertTrue(form.is_valid())
        interface = form.save()
        self.assertEqual(int_settings['interface'], interface.name)

    def test__escapes_interface_name(self):
        int_settings = factory.get_interface_fields()
        int_settings['interface'] = 'eth1+1'
        del int_settings['name']
        form = NodeGroupInterfaceForm(
            data=int_settings, instance=make_ngi_instance())
        self.assertTrue(form.is_valid())
        interface = form.save()
        self.assertEqual('eth1--1', interface.name)

    def test__populates_subnet_mask_from_instance(self):
        network = factory._make_random_network()
        nodegroup = factory.make_NodeGroup()
        ngi = factory.make_NodeGroupInterface(
            nodegroup, network=network, ip=unicode(IPAddress(network.first)),
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        form = NodeGroupInterfaceForm(data={}, instance=ngi)
        self.assertEqual(
            unicode(IPAddress(network.netmask)),
            form.initial.get('subnet_mask'))
        self.assertTrue(form.is_valid(), dict(form.errors))
        self.assertEqual(
            unicode(IPAddress(network.netmask)),
            form.cleaned_data.get('subnet_mask'))

    def test__rejects_missing_subnet_mask_if_managed(self):
        int_settings = factory.get_interface_fields(
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        del int_settings['subnet_mask']
        form = NodeGroupInterfaceForm(data=int_settings)
        self.assertFalse(form.is_valid())
        message = (
            "That field cannot be empty (unless that interface is "
            "'unmanaged')")
        self.assertEqual({'subnet_mask': [message]}, form.errors)

    def test__defaults_to_unique_name_if_no_name_or_interface_given(self):
        int_settings = factory.get_interface_fields(
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        del int_settings['name']
        del int_settings['interface']
        form1 = NodeGroupInterfaceForm(
            data=int_settings, instance=make_ngi_instance())
        self.assertTrue(form1.is_valid())
        interface1 = form1.save()
        form2 = NodeGroupInterfaceForm(
            data=int_settings, instance=make_ngi_instance())
        self.assertTrue(form2.is_valid())
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
        self.assertTrue(form.is_valid())
        interface = form.save()
        self.assertThat(interface.name, StartsWith(int_settings['interface']))
        self.assertNotEqual(int_settings['interface'], interface.name)

    def test__disambiguates_IPv4_interface_with_ipv4_suffix(self):
        cluster = factory.make_NodeGroup()
        existing_interface = factory.make_NodeGroupInterface(
            cluster, network=factory.make_ipv4_network())
        int_settings = factory.get_interface_fields()
        del int_settings['name']
        int_settings['interface'] = existing_interface.name
        form = NodeGroupInterfaceForm(
            data=int_settings, instance=make_ngi_instance(cluster))
        self.assertTrue(form.is_valid())
        interface = form.save()
        self.assertThat(
            interface.name,
            StartsWith('%s-ipv4-' % int_settings['interface']))

    def test__disambiguates_IPv6_interface_with_ipv6_suffix(self):
        cluster = factory.make_NodeGroup()
        existing_interface = factory.make_NodeGroupInterface(cluster)
        int_settings = factory.get_interface_fields(
            network=factory.make_ipv6_network(slash=64))
        del int_settings['name']
        int_settings['interface'] = existing_interface.name
        form = NodeGroupInterfaceForm(
            data=int_settings, instance=make_ngi_instance(cluster))
        if 'name' in form.data:
            del form.data['name']
        self.assertTrue(form.is_valid(), form._errors)
        interface = form.save()
        self.assertThat(
            interface.name,
            StartsWith('%s-ipv6-' % int_settings['interface']))

    def test__requires_netmask_on_managed_IPv4_interface(self):
        network = factory.make_ipv4_network()
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
        form = NodeGroupInterfaceForm(
            data=int_settings, instance=make_ngi_instance())
        form.data.update({'subnet_mask': ""})
        self.assertTrue(form.is_valid())
        interface = form.save()
        self.assertEqual(
            IPAddress('ffff:ffff:ffff:ffff::'),
            IPAddress(interface.subnet_mask))

    def test__accepts_netmasks_other_than_64_bits_on_IPv6(self):
        netmask = 'ffff:ffff:ffff:ffff:ffff:ffff:ffff:fff8'
        network = factory.make_ipv6_network(slash=125)
        int_settings = factory.get_interface_fields(
            network=network, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            netmask=netmask)
        form = NodeGroupInterfaceForm(
            data=int_settings, instance=make_ngi_instance())
        self.assertTrue(form.is_valid())
        interface = form.save()
        self.assertEqual(
            IPAddress(netmask),
            IPAddress(interface.subnet_mask))

    def test__rejects_126_bit_netmask_on_IPv6(self):
        netmask = 'ffff:ffff:ffff:ffff:ffff:ffff:ffff:fffc'
        network = factory.make_ipv6_network(slash=126)
        int_settings = factory.get_interface_fields(
            network=network, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            netmask=netmask)
        form = NodeGroupInterfaceForm(
            data=int_settings, instance=make_ngi_instance())
        self.assertFalse(form.is_valid())

    def test__rejects_short_netmask_on_IPv4(self):
        slash = random.randint(30, 32)
        if slash == 30:
            netmask = '255.255.255.252'
        elif slash == 31:
            netmask = '255.255.255.254'
        else:
            netmask = '255.255.255.255'
        network = factory.make_ipv4_network(slash=slash)
        int_settings = factory.get_interface_fields(
            network=network, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            netmask=netmask)
        form = NodeGroupInterfaceForm(
            data=int_settings, instance=make_ngi_instance())
        self.assertFalse(form.is_valid())

    def test_validates_new_static_ip_ranges(self):
        network = IPNetwork("10.1.0.0/24")
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ENABLED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
            network=network)
        [interface] = nodegroup.get_managed_interfaces()
        StaticIPAddress.objects.allocate_new(
            interface.network, interface.static_ip_range_low,
            interface.static_ip_range_high, interface.ip_range_low,
            interface.ip_range_high)
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

    def test_rejects_ipv4_dynamic_ranges_across_multiple_slash_16s(self):
        # Even if a dynamic range is < 65536 addresses, it can't cross
        # two /16 networks.
        network = IPNetwork("10.1.0.0/8")
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ENABLED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
            network=network, static_ip_range_low=None,
            static_ip_range_high=None)
        [interface] = nodegroup.get_managed_interfaces()
        form = NodeGroupInterfaceForm(
            data={
                'ip_range_low': '10.1.255.255',
                'ip_range_high': '10.2.0.1',
                },
            instance=interface)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            [ERROR_MESSAGE_DYNAMIC_RANGE_SPANS_SLASH_16S],
            form._errors['ip_range_low'])
        self.assertEqual(
            [ERROR_MESSAGE_DYNAMIC_RANGE_SPANS_SLASH_16S],
            form._errors['ip_range_low'])

    def test_allows_sane_ipv4_dynamic_range_size(self):
        network = IPNetwork("10.1.0.0/8")
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ENABLED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
            network=network, static_ip_range_low=None,
            static_ip_range_high=None)
        [interface] = nodegroup.get_managed_interfaces()
        form = NodeGroupInterfaceForm(
            data={
                'ip_range_low': '10.0.0.1',
                'ip_range_high': '10.0.1.255',
                },
            instance=interface)
        self.assertTrue(form.is_valid(), form.errors)

    def test_rejects_missing_ip_range_high(self):
        network = IPNetwork("10.0.0.0/8")
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ENABLED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
            network=network, static_ip_range_low=None,
            static_ip_range_high=None)
        [interface] = nodegroup.get_managed_interfaces()
        data = {'ip_range_low': '10.0.0.1'}
        form = NodeGroupInterfaceForm(
            data=data,
            instance=interface)
        self.assertFalse(form.is_valid())

    def test_rejects_missing_ip_range_low(self):
        network = IPNetwork("10.2.0.0/8")
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ENABLED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
            network=network, static_ip_range_low=None,
            static_ip_range_high=None)
        [interface] = nodegroup.get_managed_interfaces()
        data = {
            'ip_range_low': '',
            'ip_range_high': '10.0.1.255'
        }
        form = NodeGroupInterfaceForm(
            data=data,
            instance=interface)
        self.assertFalse(form.is_valid())

    def test_allows_any_size_ipv6_dynamic_range(self):
        network = factory.make_ipv6_network(slash=64)
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ENABLED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
            network=network)
        [interface] = nodegroup.get_managed_interfaces()
        form = NodeGroupInterfaceForm(
            data={
                'ip_range_low': IPAddress(network.first).format(),
                'ip_range_high': IPAddress(network.last).format(),
                'static_ip_range_low': '',
                'static_ip_range_high': '',
                },
            instance=interface)
        self.assertTrue(form.is_valid(), form._errors)

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

    def test_reports_ip_outside_network(self):
        network = IPNetwork('192.168.0.3/24')
        ip_outside_network = '192.168.2.1'
        checked_fields = [
            'router_ip',
            'ip_range_low',
            'ip_range_high',
            'static_ip_range_low',
            'static_ip_range_high',
            ]
        for field in checked_fields:
            nodegroup = factory.make_NodeGroup(
                network=network, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
            [interface] = nodegroup.get_managed_interfaces()
            form = NodeGroupInterfaceForm(
                data={field: ip_outside_network}, instance=interface)
            message = "%s not in the %s network" % (
                ip_outside_network,
                '192.168.0.0/24',
                )
            self.assertFalse(form.is_valid())
            self.assertThat(form.errors[field], Contains(message))

    def test_reports_invalid_ip(self):
        network = IPNetwork('192.168.0.3/24')
        invalid_ip = '192.168.0.9/24'
        checked_fields = [
            'router_ip',
            'ip_range_low',
            'ip_range_high',
            'static_ip_range_low',
            'static_ip_range_high',
            ]
        for field in checked_fields:
            nodegroup = factory.make_NodeGroup(
                network=network, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
            [interface] = nodegroup.get_managed_interfaces()
            form = NodeGroupInterfaceForm(
                data={field: invalid_ip}, instance=interface)
            if field == 'router_ip':
                message = "%s (%s) is not a valid address" % (
                    field,
                    invalid_ip,
                    )
            else:
                message = "Enter a valid IPv4 or IPv6 address."
            self.assertFalse(form.is_valid())
            self.assertThat(form.errors[field], Contains(message))

    def test_identifies_duplicate_fqdns_in_nodegroup(self):
        # Don't allow DNS management to be enabled when it would
        # cause more than one node on the nodegroup to have the
        # same FQDN.
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ENABLED,
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
            status=NODEGROUP_STATUS.ENABLED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            name=conflicting_domain)
        conflicting_hostname = factory.make_hostname("conflicting-hostname")
        factory.make_Node(
            hostname="%s.%s" % (conflicting_hostname, conflicting_domain),
            nodegroup=nodegroup_a)

        nodegroup_b = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ENABLED,
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

    def test_creates_subnet_for_interface(self):
        int_settings = factory.get_interface_fields()
        int_settings['interface'] = 'eth0:1'
        interface = make_ngi_instance()
        form = NodeGroupInterfaceForm(data=int_settings, instance=interface)
        self.assertTrue(form.is_valid())
        ngi = form.save()
        self.assertIsNotNone(ngi.subnet)

    def test_updates_subnet_cidr_and_name_if_subnet_mask_changed(self):
        network = factory._make_random_network(slash=24)
        nodegroup = factory.make_NodeGroup()
        subnet = factory.make_Subnet(name=unicode(network.cidr), cidr=network)
        ngi = factory.make_NodeGroupInterface(nodegroup, subnet=subnet)
        # Update the network from a /24 to a /16
        form = NodeGroupInterfaceForm(
            data=dict(subnet_mask='255.255.0.0'), instance=ngi)
        # form.subnet_mask = '255.255.0.0'
        self.assertTrue(form.is_valid())
        ngi = form.save()
        new_network = IPNetwork(unicode(network.ip) + "/16")
        self.assertThat(ngi.network, Equals(new_network.cidr))
        self.assertThat(ngi.subnet.name, Equals(unicode(new_network.cidr)))

    def test_updating_cidr_does_not_create_new_subnet(self):
        network = factory._make_random_network(slash=24)
        nodegroup = factory.make_NodeGroup()
        subnet = factory.make_Subnet(cidr=network)
        ngi = factory.make_NodeGroupInterface(nodegroup, subnet=subnet)
        # Update the network from a /24 to a /16
        form = NodeGroupInterfaceForm(
            data=dict(subnet_mask='255.255.0.0'), instance=ngi)
        # form.subnet_mask = '255.255.0.0'
        self.assertTrue(form.is_valid())
        form.save()
        # new_network = IPNetwork(unicode(network.ip) + "/16")
        from maasserver.models import Subnet
        # print(list(Subnet.objects.all()))
        # self.assertThat(ngi.network, Equals(new_network.cidr))
        self.assertThat(Subnet.objects.count(), Equals(1))

    def test_multiple_subnets_on_single_interface_uses_existing_vlan(self):
        ng = factory.make_NodeGroup()
        ngi1 = NodeGroupInterface(nodegroup=ng)
        form = NodeGroupInterfaceForm(data=dict(
            interface='eth0', ip='192.168.0.1', subnet_mask='255.255.255.0'),
            instance=ngi1)
        self.assertThat(form.is_valid(), Equals(True))
        ngi1 = form.save()
        self.assertIsNotNone(ngi1)
        ngi2 = NodeGroupInterface(nodegroup=ng)
        form = NodeGroupInterfaceForm(data=dict(
            interface='eth0', ip='192.168.1.1', subnet_mask='255.255.255.0'),
            instance=ngi2)
        self.assertThat(form.is_valid(), Equals(True))
        ngi2 = form.save()
        self.assertIsNotNone(ngi2)
        self.assertThat(VLAN.objects.all().count(), Equals(1))
        self.assertThat(ngi1.vlan, Equals(ngi2.vlan))

    def test_subnet_vlan_creation_uses_default_fabric_if_empty(self):
        ng = factory.make_NodeGroup()
        ngi1 = NodeGroupInterface(nodegroup=ng)
        form = NodeGroupInterfaceForm(data=dict(
            interface='eth0', ip='192.168.0.1', subnet_mask='255.255.255.0'),
            instance=ngi1)
        self.assertThat(form.is_valid(), Equals(True))
        ngi1 = form.save()
        self.assertIsNotNone(ngi1)
        self.assertThat(Fabric.objects.all().count(), Equals(1))
        self.assertThat(ngi1.vlan.fabric.id, Equals(0))

    def test_creates_new_fabric_if_alt_subnet_exists_in_default_fabric(self):
        ng = factory.make_NodeGroup()
        ngi1 = NodeGroupInterface(nodegroup=ng)
        form = NodeGroupInterfaceForm(data=dict(
            interface='eth0', ip='192.168.0.1', subnet_mask='255.255.255.0'),
            instance=ngi1)
        self.assertThat(form.is_valid(), Equals(True))
        ngi1 = form.save()
        self.assertIsNotNone(ngi1)
        self.assertThat(Fabric.objects.all().count(), Equals(1))
        self.assertThat(ngi1.vlan.fabric.id, Equals(0))
        ngi2 = NodeGroupInterface(nodegroup=ng)
        form = NodeGroupInterfaceForm(data=dict(
            interface='eth1', ip='192.168.1.1', subnet_mask='255.255.255.0'),
            instance=ngi2)
        self.assertThat(form.is_valid(), Equals(True))
        ngi2 = form.save()
        self.assertIsNotNone(ngi2)
        self.assertThat(Fabric.objects.all().count(), Equals(2))
        # The first NodeGroupInterface we saved should be using the default
        # Fabric
        self.assertThat(ngi1.vlan.fabric.id, Equals(0))
        self.assertIsNotNone(ngi2.vlan.fabric)

    def test_creates_vlan_interface_if_interface_type_and_parent_known(self):
        ng = factory.make_NodeGroup()
        ngi1 = NodeGroupInterface(nodegroup=ng)
        form = NodeGroupInterfaceForm(data=dict(
            interface='eth0', ip='192.168.0.1', subnet_mask='255.255.255.0'),
            instance=ngi1)
        self.assertThat(form.is_valid(), Equals(True))
        ngi1 = form.save()
        self.assertIsNotNone(ngi1)
        self.assertThat(Fabric.objects.all().count(), Equals(1))
        self.assertThat(ngi1.vlan.fabric.id, Equals(0))
        ngi2 = NodeGroupInterface(nodegroup=ng)
        form = NodeGroupInterfaceForm(data=dict(
            interface='vlan12', ip='192.168.1.1', subnet_mask='255.255.255.0',
            parent='eth0', type='ethernet.vlan'), instance=ngi2)
        self.assertThat(form.is_valid(), Equals(True))
        ngi2 = form.save()
        self.assertIsNotNone(ngi2)
        self.assertThat(Fabric.objects.all().count(), Equals(1))
        self.assertThat(VLAN.objects.filter(vid=12).count(), Equals(1))

    def test_creates_vlan_plus_new_fabric_if_no_parent_untagged_exists(self):
        ng = factory.make_NodeGroup()
        ngi1 = NodeGroupInterface(nodegroup=ng)
        form = NodeGroupInterfaceForm(data=dict(
            interface='eth0', ip='192.168.0.1', subnet_mask='255.255.255.0'),
            instance=ngi1)
        self.assertThat(form.is_valid(), Equals(True))
        ngi1 = form.save()
        self.assertIsNotNone(ngi1)
        self.assertThat(Fabric.objects.all().count(), Equals(1))
        self.assertThat(ngi1.vlan.fabric.id, Equals(0))
        ngi2 = NodeGroupInterface(nodegroup=ng)
        form = NodeGroupInterfaceForm(data=dict(
            interface='eth0.12', ip='192.168.1.1', subnet_mask='255.255.255.0',
            type='ethernet.vlan'), instance=ngi2)
        self.assertThat(form.is_valid(), Equals(True))
        ngi2 = form.save()
        self.assertIsNotNone(ngi2)
        self.assertThat(Fabric.objects.all().count(), Equals(2))
        # Check that VLAN 12 was created on the non-default VLAN.
        self.assertThat(VLAN.objects.filter(
            vid=12, fabric__id__gt=0).count(), Equals(1))
