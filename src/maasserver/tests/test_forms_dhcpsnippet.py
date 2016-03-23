# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for DHCP snippets forms."""

__all__ = []

from django.core.exceptions import ValidationError
from maasserver.forms_dhcpsnippet import DHCPSnippetForm
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestDHCPSnippetForm(MAASServerTestCase):

    def test__create_dhcp_snippet_requies_name(self):
        self.assertRaises(
            ValidationError,
            DHCPSnippetForm, data={'value': factory.make_string()})

    def test__create_dhcp_snippet_requires_value(self):
        self.assertRaises(
            ValidationError,
            DHCPSnippetForm, data={'name': factory.make_name('name')})

    def test__creates_dhcp_snippet(self):
        name = factory.make_name('name')
        value = factory.make_string()
        description = factory.make_string()
        enabled = factory.pick_bool()
        form = DHCPSnippetForm(data={
            'name': name,
            'value': value,
            'description': description,
            'enabled': enabled,
        })
        self.assertTrue(form.is_valid(), form.errors)
        dhcp_snippet = form.save()
        self.assertEqual(name, dhcp_snippet.name)
        self.assertEqual(value, dhcp_snippet.value.data)
        self.assertEqual(description, dhcp_snippet.description)
        self.assertEqual(enabled, dhcp_snippet.enabled)

    def test__creates_dhcp_snippet_with_node(self):
        node = factory.make_Node()
        name = factory.make_name('name')
        value = factory.make_string()
        description = factory.make_string()
        enabled = factory.pick_bool()
        form = DHCPSnippetForm(data={
            'name': name,
            'value': value,
            'description': description,
            'enabled': enabled,
            'node': node.system_id,
        })
        self.assertTrue(form.is_valid(), form.errors)
        dhcp_snippet = form.save()
        self.assertEqual(value, dhcp_snippet.value.data)
        self.assertEqual(description, dhcp_snippet.description)
        self.assertEqual(enabled, dhcp_snippet.enabled)
        self.assertEqual(node, dhcp_snippet.node)

    def test__creates_dhcp_snippet_with_subnet(self):
        subnet = factory.make_Subnet()
        name = factory.make_name('name')
        value = factory.make_string()
        description = factory.make_string()
        enabled = factory.pick_bool()
        form = DHCPSnippetForm(data={
            'name': name,
            'value': value,
            'description': description,
            'enabled': enabled,
            'subnet': subnet.id,
        })
        self.assertTrue(form.is_valid(), form.errors)
        dhcp_snippet = form.save()
        self.assertEqual(name, dhcp_snippet.name)
        self.assertEqual(value, dhcp_snippet.value.data)
        self.assertEqual(description, dhcp_snippet.description)
        self.assertEqual(enabled, dhcp_snippet.enabled)
        self.assertEqual(subnet, dhcp_snippet.subnet)

    def test__cannt_create_dhcp_snippet_with_node_and_subnet(self):
        node = factory.make_Node()
        subnet = factory.make_Subnet()
        name = factory.make_name('name')
        value = factory.make_string()
        description = factory.make_string()
        enabled = factory.pick_bool()
        form = DHCPSnippetForm(data={
            'name': name,
            'value': value,
            'description': description,
            'enabled': enabled,
            'node': node.system_id,
            'subnet': subnet.id,
        })
        self.assertFalse(form.is_valid())

    def test__updates_name(self):
        dhcp_snippet = factory.make_DHCPSnippet()
        name = factory.make_name('name')
        form = DHCPSnippetForm(
            instance=dhcp_snippet, data={'name': name})
        self.assertTrue(form.is_valid(), form.errors)
        dhcp_snippet = form.save()
        self.assertEqual(name, dhcp_snippet.name)

    def test__updates_value(self):
        dhcp_snippet = factory.make_DHCPSnippet()
        old_value = dhcp_snippet.value.data
        new_value = factory.make_string()
        form = DHCPSnippetForm(
            instance=dhcp_snippet, data={'value': new_value})
        self.assertTrue(form.is_valid(), form.errors)
        dhcp_snippet = form.save()
        self.assertEqual(new_value, dhcp_snippet.value.data)
        self.assertEqual(old_value, dhcp_snippet.value.previous_version.data)

    def test__updates_description(self):
        dhcp_snippet = factory.make_DHCPSnippet()
        description = factory.make_string()
        form = DHCPSnippetForm(
            instance=dhcp_snippet, data={'description': description})
        self.assertTrue(form.is_valid(), form.errors)
        dhcp_snippet = form.save()
        self.assertEqual(description, dhcp_snippet.description)

    def test__updates_enabled(self):
        dhcp_snippet = factory.make_DHCPSnippet()
        enabled = not dhcp_snippet.enabled
        form = DHCPSnippetForm(
            instance=dhcp_snippet, data={'enabled': enabled})
        self.assertTrue(form.is_valid(), form.errors)
        dhcp_snippet = form.save()
        self.assertEqual(enabled, dhcp_snippet.enabled)

    def test__updates_node(self):
        dhcp_snippet = factory.make_DHCPSnippet()
        node = factory.make_Node()
        form = DHCPSnippetForm(
            instance=dhcp_snippet, data={'node': node.system_id})
        self.assertTrue(form.is_valid(), form.errors)
        dhcp_snippet = form.save()
        self.assertEqual(node, dhcp_snippet.node)

    def test__cannt_update_node_when_subnet_set(self):
        dhcp_snippet = factory.make_DHCPSnippet(subnet=factory.make_Subnet())
        node = factory.make_Node()
        form = DHCPSnippetForm(
            instance=dhcp_snippet, data={'node': node.system_id})
        self.assertFalse(form.is_valid())

    def test__updates_subnet(self):
        dhcp_snippet = factory.make_DHCPSnippet()
        subnet = factory.make_Subnet()
        form = DHCPSnippetForm(
            instance=dhcp_snippet, data={'subnet': subnet.id})
        self.assertTrue(form.is_valid(), form.errors)
        dhcp_snippet = form.save()
        self.assertEqual(subnet, dhcp_snippet.subnet)

    def test__cannt_update_subnet_when_node_set(self):
        dhcp_snippet = factory.make_DHCPSnippet(node=factory.make_Node())
        subnet = factory.make_Subnet()
        form = DHCPSnippetForm(
            instance=dhcp_snippet, data={'subnet': subnet.id})
        self.assertFalse(form.is_valid())

    def test__cannt_update_both_node_and_subnet(self):
        dhcp_snippet = factory.make_DHCPSnippet()
        form = DHCPSnippetForm(
            instance=dhcp_snippet,
            data={
                'node': factory.make_Node().system_id,
                'subnet': factory.make_Subnet().id,
            })
        self.assertFalse(form.is_valid())

    def test__update_global_snippet_resets_node(self):
        node = factory.make_Node()
        dhcp_snippet = factory.make_DHCPSnippet(node=node)
        form = DHCPSnippetForm(
            instance=dhcp_snippet, data={"global_snippet": True})
        self.assertTrue(form.is_valid(), form.errors)
        dhcp_snippet = form.save()
        self.assertIsNone(dhcp_snippet.node)

    def test__update_global_snippet_resets_subnet(self):
        subnet = factory.make_Subnet()
        dhcp_snippet = factory.make_DHCPSnippet(subnet=subnet)
        form = DHCPSnippetForm(
            instance=dhcp_snippet, data={"global_snippet": True})
        self.assertTrue(form.is_valid(), form.errors)
        dhcp_snippet = form.save()
        self.assertIsNone(dhcp_snippet.subnet)
