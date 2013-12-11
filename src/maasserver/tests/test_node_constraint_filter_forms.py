# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test node constraint forms."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from django import forms
from django.core.exceptions import ValidationError
from maasserver.enum import ARCHITECTURE
from maasserver.fields import MAC
from maasserver.models import Node
from maasserver.node_constraint_filter_forms import (
    AcquireNodeForm,
    generate_architecture_wildcards,
    JUJU_ACQUIRE_FORM_FIELDS_MAPPING,
    parse_legacy_tags,
    RenamableFieldsForm,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils import ignore_unused
from maastesting.matchers import ContainsAll


class TestUtils(MAASServerTestCase):

    def test_generate_architecture_wildcards(self):
        # Create a test architecture choice list of one architecture that only
        # has one available subarch (single_subarch) and two architectures that
        # have a matching primary architecture (double_subarch_{1,2})
        single_subarch = factory.make_name('arch'), factory.make_name('arch')
        double_subarch_1 = factory.make_name('arch'), factory.make_name('arch')
        double_subarch_2 = double_subarch_1[0], factory.make_name('arch')
        choices = (
            ('/'.join(single_subarch), None),
            ('/'.join(double_subarch_1), None),
            ('/'.join(double_subarch_2), None),
        )

        # single_subarch should end up in the dict essentially unchanged, and
        # the double_subarchs should have been flattened into a single dict
        # element with a list of them.
        self.assertEquals(
            {
                single_subarch[0]: frozenset([choices[0][0]]),
                double_subarch_1[0]: frozenset(
                    [choices[1][0], choices[2][0]]),
            },
            generate_architecture_wildcards(choices=choices)
        )

    def test_parse_legacy_tags(self):
        self.assertEquals([], parse_legacy_tags([]))
        self.assertEquals(['a', 'b'], parse_legacy_tags(['a', 'b']))
        self.assertEquals(['a', 'b'], parse_legacy_tags(['a b']))
        self.assertEquals(['a', 'b'], parse_legacy_tags(['a, b']))
        self.assertEquals(['a', 'b', 'c'], parse_legacy_tags(['a, b c']))
        self.assertEquals(['a', 'b'], parse_legacy_tags(['a,b']))
        self.assertEquals(
            ['a', 'b', 'c', 'd'], parse_legacy_tags(['a,b', 'c d']))

    def test_JUJU_ACQUIRE_FORM_FIELDS_MAPPING_fields(self):
        self.assertThat(
            list(AcquireNodeForm().fields),
            ContainsAll(JUJU_ACQUIRE_FORM_FIELDS_MAPPING))


class TestRenamableForm(RenamableFieldsForm):
    field1 = forms.CharField(label="A field which is forced to contain 'foo'.")
    field2 = forms.CharField(label="Field 2", required=False)

    def clean_field1(self):
        name = self.get_field_name('field1')
        value = self.cleaned_data[name]
        if value != "foo":
            raise ValidationError("The value should be 'foo'")
        return value


class TestRenamableFieldsForm(MAASServerTestCase):

    def test_rename_field_renames_field(self):
        form = TestRenamableForm()
        form.rename_field('field1', 'new_field')
        self.assertItemsEqual(form.fields, ['new_field', 'field2'])

    def test_rename_field_updates_mapping(self):
        form = TestRenamableForm()
        form.rename_field('field1', 'new_field')
        self.assertEquals('new_field', form.get_field_name('field1'))

    def test_rename_field_renames_validation_method(self):
        form = TestRenamableForm(data={'new_field': 'not foo', 'field2': 'a'})
        form.rename_field('field1', 'new_field')
        self.assertEquals(
            (False, {'new_field': ["The value should be 'foo'"]}),
            (form.is_valid(), form.errors))


class TestAcquireNodeForm(MAASServerTestCase):

    def test_strict_form_checks_unknown_constraints(self):
        data = {'unknown_constraint': 'boo'}
        form = AcquireNodeForm.Strict(data=data)
        self.assertEquals(
            (False, {'unknown_constraint': ["No such constraint."]}),
            (form.is_valid(), form.errors))

    def test_not_strict_does_not_check_unknown_constraints(self):
        data = {'unknown_constraint': 'boo'}
        form = AcquireNodeForm(data=data)
        self.assertTrue(form.is_valid())

    def assertConstrainedNodes(self, nodes, data):
        form = AcquireNodeForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertItemsEqual(nodes, form.filter_nodes(Node.objects.all()))

    def test_no_constraints(self):
        nodes = [factory.make_node() for i in range(3)]
        form = AcquireNodeForm(data={})
        self.assertTrue(form.is_valid())
        self.assertItemsEqual(nodes, form.filter_nodes(nodes))

    def test_hostname(self):
        nodes = [factory.make_node() for i in range(3)]
        self.assertConstrainedNodes([nodes[0]], {'name': nodes[0].hostname})
        self.assertConstrainedNodes([], {'name': 'unknown-name'})

    def test_hostname_with_domain_part(self):
        nodes = [factory.make_node() for i in range(3)]
        self.assertConstrainedNodes(
            [nodes[0]],
            {'name': '%s.%s' % (nodes[0].hostname, nodes[0].nodegroup.name)})
        self.assertConstrainedNodes(
            [],
            {'name': '%s.%s' % (nodes[0].hostname, 'unknown-domain')})
        self.assertConstrainedNodes(
            [],
            {'name': '%s.%s' % (nodes[0].hostname, nodes[1].nodegroup.name)})
        node = factory.make_node(hostname="host21.mydomain")
        self.assertConstrainedNodes(
            [node],
            {'name': 'host21.mydomain'})

        self.assertConstrainedNodes(
            [node],
            {'name': 'host21.%s' % node.nodegroup.name})

    def test_cpu_count(self):
        node1 = factory.make_node(cpu_count=1)
        node2 = factory.make_node(cpu_count=2)
        nodes = [node1, node2]
        self.assertConstrainedNodes(nodes, {'cpu_count': '0'})
        self.assertConstrainedNodes(nodes, {'cpu_count': '1.0'})
        self.assertConstrainedNodes([node2], {'cpu_count': '2'})
        self.assertConstrainedNodes([], {'cpu_count': '4'})

    def test_invalid_cpu_count(self):
        form = AcquireNodeForm(data={'cpu_count': 'invalid'})
        self.assertEquals(
            (False, {'cpu_count': ["Invalid CPU count: number required."]}),
            (form.is_valid(), form.errors))

    def test_memory(self):
        node1 = factory.make_node(memory=1024)
        node2 = factory.make_node(memory=4096)
        self.assertConstrainedNodes([node1, node2], {'mem': '512'})
        self.assertConstrainedNodes([node1, node2], {'mem': '1024'})
        self.assertConstrainedNodes([node2], {'mem': '2048'})
        self.assertConstrainedNodes([node2], {'mem': '4096'})
        self.assertConstrainedNodes([], {'mem': '8192'})
        self.assertConstrainedNodes([node2], {'mem': '4096.0'})

    def test_invalid_memory(self):
        form = AcquireNodeForm(data={'mem': 'invalid'})
        self.assertEquals(
            (False, {'mem': ["Invalid memory: number of MB required."]}),
            (form.is_valid(), form.errors))

    def test_connected_to(self):
        mac1 = MAC('aa:bb:cc:dd:ee:ff')
        mac2 = MAC('00:11:22:33:44:55')
        node1 = factory.make_node(routers=[mac1, mac2])
        node2 = factory.make_node(routers=[mac1])
        factory.make_node()
        self.assertConstrainedNodes(
            [node1], {'connected_to': [
                mac1.get_raw(), mac2.get_raw()]})
        self.assertConstrainedNodes(
            [node1, node2], {'connected_to': [mac1.get_raw()]})

    def test_invalid_connected_to(self):
        form = AcquireNodeForm(data={'connected_to': 'invalid'})
        self.assertEquals(
            (False, {
                'connected_to':
                ["Invalid parameter: list of MAC addresses required."]}),
            (form.is_valid(), form.errors))

    def test_not_connected_to(self):
        mac1 = MAC('aa:bb:cc:dd:ee:ff')
        mac2 = MAC('00:11:22:33:44:55')
        node1 = factory.make_node(routers=[mac1, mac2])
        node2 = factory.make_node(routers=[mac1])
        node3 = factory.make_node()
        self.assertConstrainedNodes(
            [node3], {'not_connected_to': [
                mac1.get_raw(), mac2.get_raw()]})
        self.assertConstrainedNodes(
            [node2, node3], {'not_connected_to': [mac2.get_raw()]})
        self.assertConstrainedNodes(
            [node1, node2, node3], {'not_connected_to': ["b1:b1:b1:b1:b1:b1"]})

    def test_invalid_not_connected_to(self):
        form = AcquireNodeForm(data={'not_connected_to': 'invalid'})
        self.assertEquals(
            (False, {
                'not_connected_to':
                ["Invalid parameter: list of MAC addresses required."]}),
            (form.is_valid(), form.errors))

    def test_zone(self):
        node1 = factory.make_node()
        node2 = factory.make_node()
        node3 = factory.make_node()
        zone1 = factory.make_zone(nodes=[node1, node2])
        zone2 = factory.make_zone()

        self.assertConstrainedNodes(
            [node1, node2], {'zone': zone1.name})
        self.assertConstrainedNodes(
            [node1, node2, node3], {'zone': ''})
        self.assertConstrainedNodes(
            [node1, node2, node3], {})
        self.assertConstrainedNodes(
            [], {'zone': zone2.name})

    def test_invalid_zone(self):
        form = AcquireNodeForm(data={'zone': 'unknown'})
        self.assertEquals(
            (False, {'zone': ["No such zone: 'unknown'."]}),
            (form.is_valid(), form.errors))

    def test_tags(self):
        tag_big = factory.make_tag(name='big')
        tag_burly = factory.make_tag(name='burly')
        node_big = factory.make_node()
        node_big.tags.add(tag_big)
        node_burly = factory.make_node()
        node_burly.tags.add(tag_burly)
        node_bignburly = factory.make_node()
        node_bignburly.tags.add(tag_big)
        node_bignburly.tags.add(tag_burly)
        self.assertConstrainedNodes(
            [node_big, node_bignburly], {'tags': ['big']})
        self.assertConstrainedNodes(
            [node_burly, node_bignburly], {'tags': ['burly']})
        self.assertConstrainedNodes(
            [node_bignburly], {'tags': ['big', 'burly']})

    def test_invalid_tags(self):
        form = AcquireNodeForm(data={'tags': ['big', 'unknown']})
        self.assertEquals(
            (False, {
                'tags':
                ["No such tag(s): 'big', 'unknown'."]}),
            (form.is_valid(), form.errors))

    def test_combined_constraints(self):
        tag_big = factory.make_tag(name='big')
        node_big = factory.make_node(architecture=ARCHITECTURE.i386)
        node_big.tags.add(tag_big)
        node_small = factory.make_node(architecture=ARCHITECTURE.i386)
        ignore_unused(node_small)
        node_big_arm = factory.make_node(
            architecture=ARCHITECTURE.armhf_highbank)
        node_big_arm.tags.add(tag_big)
        self.assertConstrainedNodes(
            [node_big, node_big_arm], {'tags': ['big']})
        self.assertConstrainedNodes(
            [node_big], {'arch': 'i386/generic', 'tags': ['big']})

    def test_invalid_combined_constraints(self):
        form = AcquireNodeForm(
            data={'tags': ['unknown'], 'mem': 'invalid'})
        self.assertEquals(
            (False, {
                'tags': ["No such tag(s): 'unknown'."],
                'mem': ["Invalid memory: number of MB required."],
            }),
            (form.is_valid(), form.errors))
