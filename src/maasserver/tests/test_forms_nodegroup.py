# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for nodegroup forms."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import json
from random import randint

from django.forms import (
    CheckboxInput,
    HiddenInput,
)
from maasserver.enum import (
    NODE_STATUS,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
)
from maasserver.forms import (
    INTERFACES_VALIDATION_ERROR_MESSAGE,
    NodeGroupDefineForm,
    NodeGroupEdit,
)
from maasserver.models import (
    NodeGroup,
    NodeGroupInterface,
)
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from netaddr import IPNetwork
from provisioningserver.utils.enum import map_enum
from testtools.matchers import (
    HasLength,
    MatchesStructure,
    StartsWith,
)


class TestNodeGroupDefineForm(MAASServerTestCase):

    def test_creates_pending_nodegroup(self):
        name = factory.make_name('name')
        uuid = factory.make_UUID()
        form = NodeGroupDefineForm(data={'name': name, 'uuid': uuid})
        self.assertTrue(form.is_valid(), form._errors)
        nodegroup = form.save()
        self.assertEqual(
            (uuid, name, NODEGROUP_STATUS.PENDING, 0),
            (
                nodegroup.uuid,
                nodegroup.name,
                nodegroup.status,
                nodegroup.nodegroupinterface_set.count(),
            ))

    def test_creates_nodegroup_with_status(self):
        name = factory.make_name('name')
        uuid = factory.make_UUID()
        form = NodeGroupDefineForm(
            status=NODEGROUP_STATUS.ACCEPTED,
            data={'name': name, 'uuid': uuid})
        self.assertTrue(form.is_valid(), form._errors)
        nodegroup = form.save()
        self.assertEqual(NODEGROUP_STATUS.ACCEPTED, nodegroup.status)

    def test_validates_parameters(self):
        name = factory.make_name('name')
        too_long_uuid = 'test' * 30
        form = NodeGroupDefineForm(
            data={'name': name, 'uuid': too_long_uuid})
        self.assertFalse(form.is_valid())
        self.assertEquals(
            {'uuid':
                ['Ensure this value has at most 36 characters (it has 120).']},
            form._errors)

    def test_rejects_invalid_json_interfaces(self):
        name = factory.make_name('name')
        uuid = factory.make_UUID()
        invalid_interfaces = factory.make_name('invalid_json_interfaces')
        form = NodeGroupDefineForm(
            data={
                'name': name, 'uuid': uuid, 'interfaces': invalid_interfaces})
        self.assertFalse(form.is_valid())
        self.assertEquals(
            {'interfaces': ['Invalid json value.']},
            form._errors)

    def test_rejects_invalid_list_interfaces(self):
        name = factory.make_name('name')
        uuid = factory.make_UUID()
        invalid_interfaces = json.dumps('invalid interface list')
        form = NodeGroupDefineForm(
            data={
                'name': name, 'uuid': uuid, 'interfaces': invalid_interfaces})
        self.assertFalse(form.is_valid())
        self.assertEquals(
            {'interfaces': [INTERFACES_VALIDATION_ERROR_MESSAGE]},
            form._errors)

    def test_rejects_invalid_interface(self):
        name = factory.make_name('name')
        uuid = factory.make_UUID()
        interface = factory.get_interface_fields()
        # Make the interface invalid.
        interface['ip_range_high'] = 'invalid IP address'
        interfaces = json.dumps([interface])
        form = NodeGroupDefineForm(
            data={'name': name, 'uuid': uuid, 'interfaces': interfaces})
        self.assertFalse(form.is_valid())
        self.assertIn(
            "Enter a valid IPv4 or IPv6 address",
            form._errors['interfaces'][0])

    def test_creates_interface_from_params(self):
        name = factory.make_name('name')
        uuid = factory.make_UUID()
        interface = factory.get_interface_fields()
        interfaces = json.dumps([interface])
        form = NodeGroupDefineForm(
            data={'name': name, 'uuid': uuid, 'interfaces': interfaces})
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        nodegroup = NodeGroup.objects.get(uuid=uuid)
        # Replace empty strings with None as empty strings are converted into
        # None for fields with null=True.
        expected_result = {
            key: (value if value != '' else None)
            for key, value in interface.items()
        }
        self.assertThat(
            nodegroup.nodegroupinterface_set.all()[0],
            MatchesStructure.byEquality(**expected_result))

    def test_accepts_unnamed_cluster_interface(self):
        uuid = factory.make_UUID()
        interface = factory.get_interface_fields()
        del interface['name']
        interfaces = json.dumps([interface])
        form = NodeGroupDefineForm(
            data={
                'name': factory.make_name('cluster'),
                'uuid': uuid,
                'interfaces': interfaces,
            })
        self.assertTrue(form.is_valid(), form._errors)
        cluster = form.save()
        [cluster_interface] = cluster.nodegroupinterface_set.all()
        self.assertEqual(interface['interface'], cluster_interface.name)
        self.assertEqual(interface['interface'], cluster_interface.interface)

    def test_checks_against_conflicting_managed_networks(self):
        big_network = IPNetwork('10.0.0.0/255.255.0.0')
        nested_network = IPNetwork('10.0.100.0/255.255.255.0')
        managed = NODEGROUPINTERFACE_MANAGEMENT.DHCP
        form = NodeGroupDefineForm(
            data={
                'name': factory.make_name('cluster'),
                'uuid': factory.make_UUID(),
                'interfaces': json.dumps([
                    factory.get_interface_fields(
                        network=big_network, management=managed),
                    factory.get_interface_fields(
                        network=nested_network, management=managed),
                    ]),
            })
        self.assertFalse(form.is_valid())
        self.assertNotEqual([], form._errors['interfaces'])
        self.assertThat(
            form._errors['interfaces'][0],
            StartsWith("Conflicting networks"))

    def test_ignores_conflicts_on_unmanaged_interfaces(self):
        big_network = IPNetwork('10.0.0.0/255.255.0.0')
        nested_network = IPNetwork('10.100.100.0/255.255.255.0')
        managed = NODEGROUPINTERFACE_MANAGEMENT.DHCP
        unmanaged = NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED
        form = NodeGroupDefineForm(
            data={
                'name': factory.make_name('cluster'),
                'uuid': factory.make_UUID(),
                'interfaces': json.dumps([
                    factory.get_interface_fields(
                        network=big_network, management=managed),
                    factory.get_interface_fields(
                        network=nested_network, management=unmanaged),
                    ]),
            })
        is_valid = form.is_valid()
        self.assertEqual(
            (True, None),
            (is_valid, form._errors.get('interfaces')))

    def test_creates_multiple_interfaces(self):
        name = factory.make_name('name')
        uuid = factory.make_UUID()
        interfaces = [
            factory.get_interface_fields(management=management)
            for management in map_enum(NODEGROUPINTERFACE_MANAGEMENT).values()
            ]
        form = NodeGroupDefineForm(
            data={
                'name': name,
                'uuid': uuid,
                'interfaces': json.dumps(interfaces),
                })
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        nodegroup = NodeGroup.objects.get(uuid=uuid)
        self.assertEqual(
            len(interfaces), nodegroup.nodegroupinterface_set.count())

    def test_populates_cluster_name_default(self):
        name = factory.make_name('name')
        uuid = factory.make_UUID()
        form = NodeGroupDefineForm(
            status=NODEGROUP_STATUS.ACCEPTED,
            data={'name': name, 'uuid': uuid})
        self.assertTrue(form.is_valid(), form._errors)
        nodegroup = form.save()
        self.assertIn(uuid, nodegroup.cluster_name)

    def test_populates_cluster_name(self):
        cluster_name = factory.make_name('cluster_name')
        uuid = factory.make_UUID()
        form = NodeGroupDefineForm(
            status=NODEGROUP_STATUS.ACCEPTED,
            data={'cluster_name': cluster_name, 'uuid': uuid})
        self.assertTrue(form.is_valid(), form._errors)
        nodegroup = form.save()
        self.assertEqual(cluster_name, nodegroup.cluster_name)

    def test_creates_unmanaged_interfaces(self):
        name = factory.make_name('name')
        uuid = factory.make_UUID()
        interface = factory.get_interface_fields()
        del interface['management']
        interfaces = json.dumps([interface])
        form = NodeGroupDefineForm(
            data={'name': name, 'uuid': uuid, 'interfaces': interfaces})
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        uuid_nodegroup = NodeGroup.objects.get(uuid=uuid)
        self.assertEqual(
            [NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED],
            [
                nodegroup.management for nodegroup in
                uuid_nodegroup.nodegroupinterface_set.all()
            ])

    def test_gives_disambiguation_preference_to_IPv4(self):
        network_interface = factory.make_name('eth', sep='')
        ipv4_network = factory.make_ipv4_network()
        # We'll be creating a cluster with two interfaces, both using the same
        # network interface: an IPv4 one and an IPv6 one.
        # We randomise the ordering of this list to rule out special treatment
        # based on definition order.
        interfaces = sorted(
            [
                factory.get_interface_fields(
                    network=factory.make_ipv6_network(slash=64),
                    interface=network_interface),
                factory.get_interface_fields(
                    network=ipv4_network, interface=network_interface),
            ],
            cmp=lambda left, right: randint(-1, 1))
        # We're not going to pass names for these cluster interfaces, so the
        # form will have to make some up based on the network interface name.
        for definition in interfaces:
            del definition['name']
        form = NodeGroupDefineForm(
            data={
                'name': factory.make_name('cluster'),
                'uuid': factory.make_UUID(),
                'interfaces': json.dumps(interfaces),
                })
        self.assertTrue(form.is_valid(), form._errors)
        cluster = form.save()
        # All of the cluster interfaces' names are unique and based on the
        # network interface name, but the IPv4 one gets the unadorned name.
        interfaces_by_name = {
            interface.name: interface
            for interface in cluster.nodegroupinterface_set.all()
            }
        self.expectThat(interfaces_by_name, HasLength(len(interfaces)))
        self.assertIn(network_interface, interfaces_by_name)
        self.assertEqual(
            ipv4_network,
            interfaces_by_name[network_interface].network)


class TestNodeGroupEdit(MAASServerTestCase):

    def make_form_data(self, nodegroup):
        """Create `NodeGroupEdit` form data based on `nodegroup`."""
        return {
            'name': nodegroup.name,
            'cluster_name': nodegroup.cluster_name,
            'status': nodegroup.status,
        }

    def test_changes_name(self):
        nodegroup = factory.make_NodeGroup(name=factory.make_name('old-name'))
        new_name = factory.make_name('new-name')
        data = self.make_form_data(nodegroup)
        data['name'] = new_name
        form = NodeGroupEdit(instance=nodegroup, data=data)
        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(new_name, reload_object(nodegroup).name)

    def test_refuses_name_change_if_dns_managed_and_nodes_in_use(self):
        nodegroup, node = factory.make_unrenamable_NodeGroup_with_Node()
        data = self.make_form_data(nodegroup)
        data['name'] = factory.make_name('new-name')
        form = NodeGroupEdit(instance=nodegroup, data=data)
        self.assertFalse(form.is_valid())

    def test_accepts_unchanged_name(self):
        nodegroup, node = factory.make_unrenamable_NodeGroup_with_Node()
        original_name = nodegroup.name
        form = NodeGroupEdit(
            instance=nodegroup, data=self.make_form_data(nodegroup))
        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(original_name, reload_object(nodegroup).name)

    def test_accepts_omitted_name(self):
        nodegroup, node = factory.make_unrenamable_NodeGroup_with_Node()
        original_name = nodegroup.name
        data = self.make_form_data(nodegroup)
        del data['name']
        form = NodeGroupEdit(instance=nodegroup, data=data)
        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(original_name, reload_object(nodegroup).name)

    def test_accepts_name_change_if_nodegroup_not_accepted(self):
        nodegroup, node = factory.make_unrenamable_NodeGroup_with_Node()
        nodegroup.status = NODEGROUP_STATUS.PENDING
        data = self.make_form_data(nodegroup)
        data['name'] = factory.make_name('new-name')
        form = NodeGroupEdit(instance=nodegroup, data=data)
        self.assertTrue(form.is_valid())

    def test_accepts_name_change_if_dns_managed_but_no_nodes_in_use(self):
        nodegroup, node = factory.make_unrenamable_NodeGroup_with_Node()
        node.status = NODE_STATUS.READY
        node.save()
        data = self.make_form_data(nodegroup)
        data['name'] = factory.make_name('new-name')
        form = NodeGroupEdit(instance=nodegroup, data=data)
        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(data['name'], reload_object(nodegroup).name)

    def test_accepts_name_change_if_nodes_in_use_but_dns_not_managed(self):
        nodegroup, node = factory.make_unrenamable_NodeGroup_with_Node()
        [interface] = nodegroup.get_managed_interfaces()
        interface.management = NODEGROUPINTERFACE_MANAGEMENT.DHCP
        interface.save()
        data = self.make_form_data(nodegroup)
        data['name'] = factory.make_name('new-name')
        form = NodeGroupEdit(instance=nodegroup, data=data)
        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(data['name'], reload_object(nodegroup).name)

    def test_accepts_name_change_if_nodegroup_has_no_interface(self):
        nodegroup, node = factory.make_unrenamable_NodeGroup_with_Node()
        NodeGroupInterface.objects.filter(nodegroup=nodegroup).delete()
        data = self.make_form_data(nodegroup)
        data['name'] = factory.make_name('new-name')
        form = NodeGroupEdit(instance=nodegroup, data=data)
        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(data['name'], reload_object(nodegroup).name)

    def test_shows_default_disable_ipv4_if_managed_ipv6_configured(self):
        nodegroup = factory.make_NodeGroup()
        factory.make_NodeGroupInterface(
            nodegroup, network=factory.make_ipv6_network(),
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        form = NodeGroupEdit(instance=nodegroup)
        self.assertIsInstance(
            form.fields['default_disable_ipv4'].widget, CheckboxInput)

    def test_hides_default_disable_ipv4_if_no_managed_ipv6_configured(self):
        nodegroup = factory.make_NodeGroup()
        eth = factory.make_name('eth')
        factory.make_NodeGroupInterface(
            nodegroup, network=factory.make_ipv4_network(), interface=eth,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        factory.make_NodeGroupInterface(
            nodegroup, network=factory.make_ipv6_network(), interface=eth,
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        form = NodeGroupEdit(instance=nodegroup)
        self.assertIsInstance(
            form.fields['default_disable_ipv4'].widget, HiddenInput)

    def test_default_disable_ipv4_field_ignores_other_nodegroups(self):
        factory.make_NodeGroupInterface(
            factory.make_NodeGroup(), network=factory.make_ipv6_network(),
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        nodegroup = factory.make_NodeGroup()
        form = NodeGroupEdit(instance=nodegroup)
        self.assertIsInstance(
            form.fields['default_disable_ipv4'].widget, HiddenInput)
