# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `NodeWithMACAddressesForm`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from django.http import QueryDict
from maasserver.forms import NodeWithMACAddressesForm
from maasserver.models import NodeGroup
from maasserver.testing.architecture import (
    make_usable_architecture,
    patch_usable_architectures,
)
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from netaddr import IPNetwork


class NodeWithMACAddressesFormTest(MAASServerTestCase):

    def get_QueryDict(self, params):
        query_dict = QueryDict('', mutable=True)
        for k, v in params.items():
            if isinstance(v, list):
                query_dict.setlist(k, v)
            else:
                query_dict[k] = v
        return query_dict

    def make_params(self, mac_addresses=None, architecture=None,
                    hostname=None, nodegroup=None):
        if mac_addresses is None:
            mac_addresses = [factory.make_mac_address()]
        if architecture is None:
            architecture = factory.make_name('arch')
        if hostname is None:
            hostname = factory.make_name('hostname')
        params = {
            'mac_addresses': mac_addresses,
            'architecture': architecture,
            'hostname': hostname,
        }
        if nodegroup is not None:
            params['nodegroup'] = nodegroup
        # Make sure that the architecture parameter is acceptable.
        patch_usable_architectures(self, [architecture])
        return self.get_QueryDict(params)

    def test_NodeWithMACAddressesForm_valid(self):
        architecture = make_usable_architecture(self)
        form = NodeWithMACAddressesForm(
            data=self.make_params(
                mac_addresses=['aa:bb:cc:dd:ee:ff', '9a:bb:c3:33:e5:7f'],
                architecture=architecture))

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            ['aa:bb:cc:dd:ee:ff', '9a:bb:c3:33:e5:7f'],
            form.cleaned_data['mac_addresses'])
        self.assertEqual(architecture, form.cleaned_data['architecture'])

    def test_NodeWithMACAddressesForm_simple_invalid(self):
        # If the form only has one (invalid) MAC address field to validate,
        # the error message in form.errors['mac_addresses'] is the
        # message from the field's validation error.
        form = NodeWithMACAddressesForm(
            data=self.make_params(mac_addresses=['invalid']))

        self.assertFalse(form.is_valid())
        self.assertEqual(['mac_addresses'], list(form.errors))
        self.assertEqual(
            ["'invalid' is not a valid MAC address."],
            form.errors['mac_addresses'])

    def test_NodeWithMACAddressesForm_multiple_invalid(self):
        # If the form has multiple MAC address fields to validate,
        # if one or more fields are invalid, a single error message is
        # present in form.errors['mac_addresses'] after validation.
        form = NodeWithMACAddressesForm(
            data=self.make_params(mac_addresses=['invalid_1', 'invalid_2']))

        self.assertFalse(form.is_valid())
        self.assertEqual(['mac_addresses'], list(form.errors))
        self.assertEqual(
            [
                "One or more MAC addresses is invalid. "
                "('invalid_1' is not a valid MAC address. \u2014"
                " 'invalid_2' is not a valid MAC address.)"
            ],
            form.errors['mac_addresses'])

    def test_NodeWithMACAddressesForm_empty(self):
        # Empty values in the list of MAC addresses are simply ignored.
        form = NodeWithMACAddressesForm(
            data=self.make_params(
                mac_addresses=[factory.make_mac_address(), '']))

        self.assertTrue(form.is_valid())

    def test_NodeWithMACAddressesForm_save(self):
        macs = ['aa:bb:cc:dd:ee:ff', '9a:bb:c3:33:e5:7f']
        form = NodeWithMACAddressesForm(
            data=self.make_params(mac_addresses=macs))
        node = form.save()

        self.assertIsNotNone(node.id)  # The node is persisted.
        self.assertItemsEqual(
            macs,
            [nic.mac_address for nic in node.interface_set.all()])

    def test_includes_nodegroup_field_for_new_node(self):
        self.assertIn(
            'nodegroup',
            NodeWithMACAddressesForm(data=self.make_params()).fields)

    def test_does_not_include_nodegroup_field_for_existing_node(self):
        params = self.make_params()
        node = factory.make_Node()
        self.assertNotIn(
            'nodegroup',
            NodeWithMACAddressesForm(data=params, instance=node).fields)

    def test_sets_nodegroup_to_master_by_default(self):
        self.assertEqual(
            NodeGroup.objects.ensure_master(),
            NodeWithMACAddressesForm(data=self.make_params()).save().nodegroup)

    def test_leaves_nodegroup_alone_if_unset_on_existing_node(self):
        # Selecting a node group for a node is only supported on new
        # nodes.  You can't change it later.
        original_nodegroup = factory.make_NodeGroup()
        node = factory.make_Node(nodegroup=original_nodegroup)
        factory.make_NodeGroup(network=IPNetwork("192.168.1.0/24"))
        form = NodeWithMACAddressesForm(
            data=self.make_params(nodegroup='192.168.1.0'), instance=node)
        form.save()
        self.assertEqual(original_nodegroup, reload_object(node).nodegroup)

    def test_form_without_hostname_generates_hostname(self):
        form = NodeWithMACAddressesForm(data=self.make_params(hostname=''))
        node = form.save()
        self.assertTrue(len(node.hostname) > 0)

    def test_form_with_ip_based_hostname_generates_hostname(self):
        ip_based_hostname = '192-168-12-10.domain'
        form = NodeWithMACAddressesForm(
            data=self.make_params(hostname=ip_based_hostname))
        node = form.save()
        self.assertNotEqual(ip_based_hostname, node.hostname)
