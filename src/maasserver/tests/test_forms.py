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

from django.conf import settings
from django.core.exceptions import ValidationError
from maasserver.enum import (
    NODE_STATUS,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.forms import (
    AdminNodeForm,
    AdminNodeWithMACAddressesForm,
    ERROR_MESSAGE_STATIC_IPS_OUTSIDE_RANGE,
    ERROR_MESSAGE_STATIC_RANGE_IN_USE,
    get_node_create_form,
    get_node_edit_form,
    initialize_node_group,
    list_all_usable_architectures,
    MACAddressForm,
    MAX_MESSAGES,
    merge_error_messages,
    NodeForm,
    NodeGroupInterfaceForeignDHCPForm,
    NodeGroupInterfaceForm,
    NodeWithMACAddressesForm,
    pick_default_architecture,
    remove_None_values,
    validate_new_static_ip_ranges,
    validate_nonoverlapping_networks,
    )
from maasserver.models import (
    MACAddress,
    Network,
    Node,
    NodeGroup,
    NodeGroupInterface,
    )
from maasserver.models.network import get_name_and_vlan_from_cluster_interface
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import MockCalledOnceWith
from netaddr import IPNetwork
from provisioningserver import tasks
from testtools import TestCase
from testtools.matchers import (
    AllMatch,
    Contains,
    Equals,
    MatchesAll,
    MatchesRegex,
    MatchesStructure,
    StartsWith,
    )


class TestHelpers(MAASServerTestCase):

    def make_usable_boot_images(self, nodegroup=None, osystem=None,
                                arch=None, subarchitecture=None, release=None):
        """Create a set of boot images, so the architecture becomes "usable".

        This will make the images' architecture show up in the list of usable
        architecture.

        Nothing is returned.
        """
        if nodegroup is None:
            nodegroup = factory.make_node_group()
        if osystem is None:
            osystem = factory.make_name('os')
        if arch is None:
            arch = factory.make_name('arch')
        if subarchitecture is None:
            subarchitecture = factory.make_name('subarch')
        if release is None:
            release = factory.make_name('release')
        for purpose in ['install', 'commissioning']:
            factory.make_boot_image(
                nodegroup=nodegroup, osystem=osystem, architecture=arch,
                subarchitecture=subarchitecture, release=release,
                purpose=purpose)

    def test_initialize_node_group_leaves_nodegroup_reference_intact(self):
        preselected_nodegroup = factory.make_node_group()
        node = factory.make_node(nodegroup=preselected_nodegroup)
        initialize_node_group(node)
        self.assertEqual(preselected_nodegroup, node.nodegroup)

    def test_initialize_node_group_initializes_nodegroup_to_form_value(self):
        node = Node(
            NODE_STATUS.NEW, architecture=make_usable_architecture(self))
        nodegroup = factory.make_node_group()
        initialize_node_group(node, nodegroup)
        self.assertEqual(nodegroup, node.nodegroup)

    def test_initialize_node_group_defaults_to_master(self):
        node = Node(
            NODE_STATUS.NEW,
            architecture=make_usable_architecture(self))
        initialize_node_group(node)
        self.assertEqual(NodeGroup.objects.ensure_master(), node.nodegroup)

    def test_list_all_usable_architectures_combines_nodegroups(self):
        arches = [
            (factory.make_name('arch'), factory.make_name('subarch'))
            for _ in range(3)]
        for arch, subarch in arches:
            self.make_usable_boot_images(arch=arch, subarchitecture=subarch)
        expected = [
            "%s/%s" % (arch, subarch) for arch, subarch in arches]
        self.assertItemsEqual(expected, list_all_usable_architectures())

    def test_list_all_usable_architectures_sorts_output(self):
        arches = [
            (factory.make_name('arch'), factory.make_name('subarch'))
            for _ in range(3)]
        for arch, subarch in arches:
            self.make_usable_boot_images(arch=arch, subarchitecture=subarch)
        expected = [
            "%s/%s" % (arch, subarch) for arch, subarch in arches]
        self.assertEqual(sorted(expected), list_all_usable_architectures())

    def test_list_all_usable_architectures_returns_no_duplicates(self):
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        self.make_usable_boot_images(arch=arch, subarchitecture=subarch)
        self.make_usable_boot_images(arch=arch, subarchitecture=subarch)
        self.assertEqual(
            ["%s/%s" % (arch, subarch)], list_all_usable_architectures())

    def test_pick_default_architecture_returns_empty_if_no_options(self):
        self.assertEqual('', pick_default_architecture([]))

    def test_pick_default_architecture_prefers_i386_generic_if_usable(self):
        self.assertEqual(
            'i386/generic',
            pick_default_architecture(
                ['amd64/generic', 'i386/generic', 'mips/generic']))

    def test_pick_default_architecture_falls_back_to_first_option(self):
        arches = [factory.make_name('arch') for _ in range(5)]
        self.assertEqual(arches[0], pick_default_architecture(arches))

    def test_remove_None_values_removes_None_values_in_dict(self):
        random_input = factory.make_string()
        self.assertEqual(
            {random_input: random_input},
            remove_None_values({
                random_input: random_input,
                factory.make_string(): None,
                }))

    def test_remove_None_values_leaves_empty_dict_untouched(self):
        self.assertEqual({}, remove_None_values({}))

    def test_get_node_edit_form_returns_NodeForm_if_non_admin(self):
        user = factory.make_user()
        self.assertEqual(NodeForm, get_node_edit_form(user))

    def test_get_node_edit_form_returns_APIAdminNodeEdit_if_admin(self):
        admin = factory.make_admin()
        self.assertEqual(AdminNodeForm, get_node_edit_form(admin))

    def test_get_node_create_form_if_non_admin(self):
        user = factory.make_user()
        self.assertEqual(
            NodeWithMACAddressesForm, get_node_create_form(user))

    def test_get_node_create_form_if_admin(self):
        admin = factory.make_admin()
        self.assertEqual(
            AdminNodeWithMACAddressesForm, get_node_create_form(admin))


class TestMergeErrorMessages(MAASServerTestCase):

    def test_merge_error_messages_returns_summary_message(self):
        summary = factory.make_name('summary')
        errors = [factory.make_name('error') for _ in range(2)]
        result = merge_error_messages(summary, errors, 5)
        self.assertEqual(
            "%s (%s)" % (summary, ' \u2014 '.join(errors)), result)

    def test_merge_error_messages_includes_limited_number_of_msgs(self):
        summary = factory.make_name('summary')
        errors = [
            factory.make_name('error')
            for _ in range(MAX_MESSAGES + 2)]
        result = merge_error_messages(summary, errors)
        self.assertEqual(
            "%s (%s and 2 more errors)" % (
                summary, ' \u2014 '.join(errors[:MAX_MESSAGES])),
            result)

    def test_merge_error_messages_with_one_more_error(self):
        summary = factory.make_name('summary')
        errors = [
            factory.make_name('error')
            for _ in range(MAX_MESSAGES + 1)]
        result = merge_error_messages(summary, errors)
        self.assertEqual(
            "%s (%s and 1 more error)" % (
                summary, ' \u2014 '.join(errors[:MAX_MESSAGES])),
            result)


class TestMACAddressForm(MAASServerTestCase):

    def test_MACAddressForm_creates_mac_address(self):
        node = factory.make_node()
        mac = factory.getRandomMACAddress()
        form = MACAddressForm(node=node, data={'mac_address': mac})
        form.save()
        self.assertTrue(
            MACAddress.objects.filter(node=node, mac_address=mac).exists())

    def test_saves_to_db_by_default(self):
        node = factory.make_node()
        mac = factory.getRandomMACAddress()
        form = MACAddressForm(node=node, data={'mac_address': mac})
        form.save()
        self.assertEqual(
            mac, MACAddress.objects.get(mac_address=mac).mac_address)

    def test_does_not_save_to_db_if_commit_is_False(self):
        node = factory.make_node()
        mac = factory.getRandomMACAddress()
        form = MACAddressForm(node=node, data={'mac_address': mac})
        form.save(commit=False)
        self.assertItemsEqual([], MACAddress.objects.filter(mac_address=mac))

    def test_MACAddressForm_displays_error_message_if_mac_already_used(self):
        mac = factory.getRandomMACAddress()
        node = factory.make_mac_address(address=mac)
        node = factory.make_node()
        form = MACAddressForm(node=node, data={'mac_address': mac})
        self.assertFalse(form.is_valid())
        self.assertEquals(
            {'mac_address': ['This MAC address is already registered.']},
            form._errors)
        self.assertFalse(
            MACAddress.objects.filter(node=node, mac_address=mac).exists())


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
        nodegroup = factory.make_node_group()
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
        cluster = factory.make_node_group()
        existing_interface = factory.make_node_group_interface(cluster)
        int_settings = factory.get_interface_fields()
        del int_settings['name']
        int_settings['interface'] = existing_interface.name
        form = NodeGroupInterfaceForm(
            data=int_settings, instance=make_ngi_instance(cluster))
        interface = form.save()
        self.assertThat(interface.name, StartsWith(int_settings['interface']))
        self.assertNotEqual(int_settings['interface'], interface.name)

    def test_validates_new_static_ip_ranges(self):
        network = IPNetwork("10.1.0.0/24")
        nodegroup = factory.make_node_group(
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
        nodegroup = factory.make_node_group(
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        base_hostname = factory.make_hostname("host")
        full_hostnames = [
            "%s.%s" % (base_hostname, factory.make_hostname("domain"))
            for _ in range(0, 2)]
        for hostname in full_hostnames:
            factory.make_node(hostname=hostname, nodegroup=nodegroup)
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
        nodegroup_a = factory.make_node_group(
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            name=conflicting_domain)
        conflicting_hostname = factory.make_hostname("conflicting-hostname")
        factory.make_node(
            hostname="%s.%s" % (conflicting_hostname, conflicting_domain),
            nodegroup=nodegroup_a)

        nodegroup_b = factory.make_node_group(
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            name=conflicting_domain)
        factory.make_node(
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


class TestValidateNewStaticIPRanges(MAASServerTestCase):
    """Tests for `validate_new_static_ip_ranges`()."""

    def make_interface(self):
        network = IPNetwork("10.1.0.0/24")
        nodegroup = factory.make_node_group(
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
            network=network)
        [interface] = nodegroup.get_managed_interfaces()
        interface.ip_range_low = '10.1.0.1'
        interface.ip_range_high = '10.1.0.10'
        interface.static_ip_range_low = '10.1.0.50'
        interface.static_ip_range_high = '10.1.0.60'
        interface.save()
        return interface

    def test_raises_error_when_allocated_ips_fall_outside_new_range(self):
        interface = self.make_interface()
        StaticIPAddress.objects.allocate_new('10.1.0.56', '10.1.0.60')
        error = self.assertRaises(
            ValidationError,
            validate_new_static_ip_ranges,
            instance=interface,
            static_ip_range_low='10.1.0.50',
            static_ip_range_high='10.1.0.55')
        self.assertEqual(
            ERROR_MESSAGE_STATIC_IPS_OUTSIDE_RANGE,
            error.message)

    def test_removing_static_range_raises_error_if_ips_allocated(self):
        interface = self.make_interface()
        StaticIPAddress.objects.allocate_new('10.1.0.56', '10.1.0.60')
        error = self.assertRaises(
            ValidationError,
            validate_new_static_ip_ranges,
            instance=interface,
            static_ip_range_low='',
            static_ip_range_high='')
        self.assertEqual(
            ERROR_MESSAGE_STATIC_RANGE_IN_USE,
            error.message)

    def test_allows_range_expansion(self):
        interface = self.make_interface()
        StaticIPAddress.objects.allocate_new('10.1.0.56', '10.1.0.60')
        is_valid = validate_new_static_ip_ranges(
            interface, static_ip_range_low='10.1.0.40',
            static_ip_range_high='10.1.0.100')
        self.assertTrue(is_valid)

    def test_allows_allocated_ip_as_upper_bound(self):
        interface = self.make_interface()
        StaticIPAddress.objects.allocate_new('10.1.0.55', '10.1.0.55')
        is_valid = validate_new_static_ip_ranges(
            interface,
            static_ip_range_low=interface.static_ip_range_low,
            static_ip_range_high='10.1.0.55')
        self.assertTrue(is_valid)

    def test_allows_allocated_ip_as_lower_bound(self):
        interface = self.make_interface()
        StaticIPAddress.objects.allocate_new('10.1.0.55', '10.1.0.55')
        is_valid = validate_new_static_ip_ranges(
            interface, static_ip_range_low='10.1.0.55',
            static_ip_range_high=interface.static_ip_range_high)
        self.assertTrue(is_valid)

    def test_ignores_unmanaged_interfaces(self):
        interface = self.make_interface()
        interface.management = NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED
        interface.save()
        StaticIPAddress.objects.allocate_new(
            interface.static_ip_range_low, interface.static_ip_range_high)
        is_valid = validate_new_static_ip_ranges(
            interface, static_ip_range_low='10.1.0.57',
            static_ip_range_high='10.1.0.58')
        self.assertTrue(is_valid)

    def test_ignores_interfaces_with_no_static_range(self):
        interface = self.make_interface()
        interface.static_ip_range_low = None
        interface.static_ip_range_high = None
        interface.save()
        StaticIPAddress.objects.allocate_new('10.1.0.56', '10.1.0.60')
        is_valid = validate_new_static_ip_ranges(
            interface, static_ip_range_low='10.1.0.57',
            static_ip_range_high='10.1.0.58')
        self.assertTrue(is_valid)

    def test_ignores_unchanged_static_range(self):
        interface = self.make_interface()
        StaticIPAddress.objects.allocate_new(
            interface.static_ip_range_low, interface.static_ip_range_high)
        is_valid = validate_new_static_ip_ranges(
            interface,
            static_ip_range_low=interface.static_ip_range_low,
            static_ip_range_high=interface.static_ip_range_high)
        self.assertTrue(is_valid)


class TestNodeGroupInterfaceForeignDHCPForm(MAASServerTestCase):

    def test_forms_saves_foreign_dhcp_ip(self):
        nodegroup = factory.make_node_group()
        interface = factory.make_node_group_interface(nodegroup)
        foreign_dhcp_ip = factory.getRandomIPAddress()
        form = NodeGroupInterfaceForeignDHCPForm(
            data={'foreign_dhcp_ip': foreign_dhcp_ip},
            instance=interface)
        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(
            foreign_dhcp_ip, reload_object(interface).foreign_dhcp_ip)

    def test_forms_validates_foreign_dhcp_ip(self):
        nodegroup = factory.make_node_group()
        interface = factory.make_node_group_interface(nodegroup)
        form = NodeGroupInterfaceForeignDHCPForm(
            data={'foreign_dhcp_ip': 'invalid-ip'}, instance=interface)
        self.assertFalse(form.is_valid())

    def test_report_foreign_dhcp_does_not_trigger_update_signal(self):
        self.patch(settings, "DHCP_CONNECT", False)
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED)
        interface = factory.make_node_group_interface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)

        self.patch(settings, "DHCP_CONNECT", True)
        self.patch(tasks, 'write_dhcp_config')

        foreign_dhcp_ip = factory.getRandomIPAddress()
        form = NodeGroupInterfaceForeignDHCPForm(
            data={'foreign_dhcp_ip': foreign_dhcp_ip},
            instance=interface)

        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(
            foreign_dhcp_ip, reload_object(interface).foreign_dhcp_ip)
        tasks.write_dhcp_config.apply_async.assert_has_calls([])


class TestValidateNonoverlappingNetworks(TestCase):
    """Tests for `validate_nonoverlapping_networks`."""

    def make_interface_definition(self, ip, netmask, name=None):
        """Return a minimal imitation of an interface definition."""
        if name is None:
            name = factory.make_name('itf')
        return {
            'interface': name,
            'ip': ip,
            'subnet_mask': netmask,
            'management': NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
        }

    def test_accepts_zero_interfaces(self):
        validate_nonoverlapping_networks([])
        # Success is getting here without error.
        pass

    def test_accepts_single_interface(self):
        validate_nonoverlapping_networks(
            [self.make_interface_definition('10.1.1.1', '255.255.0.0')])
        # Success is getting here without error.
        pass

    def test_accepts_disparate_ranges(self):
        validate_nonoverlapping_networks([
            self.make_interface_definition('10.1.0.0', '255.255.0.0'),
            self.make_interface_definition('192.168.0.0', '255.255.255.0'),
            ])
        # Success is getting here without error.
        pass

    def test_accepts_near_neighbours(self):
        validate_nonoverlapping_networks([
            self.make_interface_definition('10.1.0.0', '255.255.0.0'),
            self.make_interface_definition('10.2.0.0', '255.255.0.0'),
            ])
        # Success is getting here without error.
        pass

    def test_rejects_identical_ranges(self):
        definitions = [
            self.make_interface_definition('192.168.0.0', '255.255.255.0'),
            self.make_interface_definition('192.168.0.0', '255.255.255.0'),
            ]
        error = self.assertRaises(
            ValidationError,
            validate_nonoverlapping_networks, definitions)
        error_text = error.messages[0]
        self.assertThat(
            error_text, MatchesRegex(
                "Conflicting networks on [^\\s]+ and [^\\s]+: "
                "address ranges overlap."))
        self.assertThat(
            error_text,
            MatchesAll(
                *(
                    Contains(definition['interface'])
                    for definition in definitions
                )))

    def test_rejects_nested_ranges(self):
        definitions = [
            self.make_interface_definition('192.168.0.0', '255.255.0.0'),
            self.make_interface_definition('192.168.100.0', '255.255.255.0'),
            ]
        error = self.assertRaises(
            ValidationError,
            validate_nonoverlapping_networks, definitions)
        self.assertIn("Conflicting networks", unicode(error))

    def test_detects_conflict_regardless_of_order(self):
        definitions = [
            self.make_interface_definition('192.168.100.0', '255.255.255.0'),
            self.make_interface_definition('192.168.1.0', '255.255.255.0'),
            self.make_interface_definition('192.168.64.0', '255.255.192.0'),
            ]
        error = self.assertRaises(
            ValidationError,
            validate_nonoverlapping_networks, definitions)
        self.assertThat(error.messages[0], StartsWith("Conflicting networks"))
