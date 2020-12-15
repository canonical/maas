# Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for DHCP snippets forms."""


import random

from django.http import HttpRequest

from maasserver.enum import ENDPOINT_CHOICES
from maasserver.forms import dhcpsnippet
from maasserver.forms.dhcpsnippet import DHCPSnippetForm
from maasserver.models import DHCPSnippet, Event, VersionedTextFile
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from provisioningserver.events import AUDIT


class TestDHCPSnippetForm(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        self.patch(dhcpsnippet, "validate_dhcp_config").return_value = {}

    def test_create_dhcp_snippet_requies_name(self):
        form = DHCPSnippetForm(data={"value": factory.make_string()})
        self.assertFalse(form.is_valid())
        self.assertItemsEqual([], VersionedTextFile.objects.all())

    def test_create_dhcp_snippet_requires_value(self):
        form = DHCPSnippetForm(data={"name": factory.make_name("name")})
        self.assertFalse(form.is_valid())
        self.assertItemsEqual([], VersionedTextFile.objects.all())

    def test_creates_dhcp_snippet(self):
        name = factory.make_name("name")
        value = factory.make_string()
        description = factory.make_string()
        enabled = factory.pick_bool()
        form = DHCPSnippetForm(
            data={
                "name": name,
                "value": value,
                "description": description,
                "enabled": enabled,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        request = HttpRequest()
        request.user = factory.make_User()
        dhcp_snippet = form.save(endpoint, request)
        self.assertEqual(name, dhcp_snippet.name)
        self.assertEqual(value, dhcp_snippet.value.data)
        self.assertEqual(description, dhcp_snippet.description)
        self.assertEqual(enabled, dhcp_snippet.enabled)
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(
            event.description, "Created DHCP snippet '%s'." % dhcp_snippet.name
        )

    def test_create_dhcp_snippet_defaults_to_enabled(self):
        name = factory.make_name("name")
        value = factory.make_string()
        description = factory.make_string()
        form = DHCPSnippetForm(
            data={"name": name, "value": value, "description": description}
        )
        self.assertTrue(form.is_valid(), form.errors)
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        request = HttpRequest()
        request.user = factory.make_User()
        dhcp_snippet = form.save(endpoint, request)
        self.assertEqual(name, dhcp_snippet.name)
        self.assertEqual(value, dhcp_snippet.value.data)
        self.assertEqual(description, dhcp_snippet.description)
        self.assertTrue(dhcp_snippet.enabled)

    def test_creates_dhcp_snippet_with_node(self):
        node = factory.make_Node()
        name = factory.make_name("name")
        value = factory.make_string()
        description = factory.make_string()
        enabled = factory.pick_bool()
        form = DHCPSnippetForm(
            data={
                "name": name,
                "value": value,
                "description": description,
                "enabled": enabled,
                "node": node.system_id,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        request = HttpRequest()
        request.user = factory.make_User()
        dhcp_snippet = form.save(endpoint, request)
        self.assertEqual(value, dhcp_snippet.value.data)
        self.assertEqual(description, dhcp_snippet.description)
        self.assertEqual(enabled, dhcp_snippet.enabled)
        self.assertEqual(node, dhcp_snippet.node)

    def test_creates_dhcp_snippet_with_subnet(self):
        subnet = factory.make_Subnet()
        name = factory.make_name("name")
        value = factory.make_string()
        description = factory.make_string()
        enabled = factory.pick_bool()
        form = DHCPSnippetForm(
            data={
                "name": name,
                "value": value,
                "description": description,
                "enabled": enabled,
                "subnet": subnet.id,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        request = HttpRequest()
        request.user = factory.make_User()
        dhcp_snippet = form.save(endpoint, request)
        self.assertEqual(name, dhcp_snippet.name)
        self.assertEqual(value, dhcp_snippet.value.data)
        self.assertEqual(description, dhcp_snippet.description)
        self.assertEqual(enabled, dhcp_snippet.enabled)
        self.assertEqual(subnet, dhcp_snippet.subnet)

    def test_cannt_create_dhcp_snippet_with_node_and_subnet(self):
        node = factory.make_Node()
        subnet = factory.make_Subnet()
        name = factory.make_name("name")
        value = factory.make_string()
        description = factory.make_string()
        enabled = factory.pick_bool()
        form = DHCPSnippetForm(
            data={
                "name": name,
                "value": value,
                "description": description,
                "enabled": enabled,
                "node": node.system_id,
                "subnet": subnet.id,
            }
        )
        self.assertFalse(form.is_valid())

    def test_fail_validation_on_create_cleans_value(self):
        node = factory.make_Node()
        subnet = factory.make_Subnet()
        name = factory.make_name("name")
        value = factory.make_string()
        description = factory.make_string()
        enabled = factory.pick_bool()
        form = DHCPSnippetForm(
            data={
                "name": name,
                "value": value,
                "description": description,
                "enabled": enabled,
                "node": node.system_id,
                "subnet": subnet.id,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertItemsEqual([], DHCPSnippet.objects.all())
        self.assertItemsEqual([], VersionedTextFile.objects.all())

    def test_updates_name(self):
        dhcp_snippet = factory.make_DHCPSnippet()
        name = factory.make_name("name")
        form = DHCPSnippetForm(instance=dhcp_snippet, data={"name": name})
        self.assertTrue(form.is_valid(), form.errors)
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        request = HttpRequest()
        request.user = factory.make_User()
        dhcp_snippet = form.save(endpoint, request)
        self.assertEqual(name, dhcp_snippet.name)
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(
            event.description, "Updated DHCP snippet '%s'." % dhcp_snippet.name
        )

    def test_updates_value(self):
        dhcp_snippet = factory.make_DHCPSnippet()
        old_value = dhcp_snippet.value.data
        new_value = factory.make_string()
        form = DHCPSnippetForm(
            instance=dhcp_snippet, data={"value": new_value}
        )
        self.assertTrue(form.is_valid(), form.errors)
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        request = HttpRequest()
        request.user = factory.make_User()
        dhcp_snippet = form.save(endpoint, request)
        self.assertEqual(new_value, dhcp_snippet.value.data)
        self.assertEqual(old_value, dhcp_snippet.value.previous_version.data)

    def test_updates_description(self):
        dhcp_snippet = factory.make_DHCPSnippet()
        description = factory.make_string()
        form = DHCPSnippetForm(
            instance=dhcp_snippet, data={"description": description}
        )
        self.assertTrue(form.is_valid(), form.errors)
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        request = HttpRequest()
        request.user = factory.make_User()
        dhcp_snippet = form.save(endpoint, request)
        self.assertEqual(description, dhcp_snippet.description)

    def test_updates_enabled(self):
        dhcp_snippet = factory.make_DHCPSnippet()
        enabled = not dhcp_snippet.enabled
        form = DHCPSnippetForm(
            instance=dhcp_snippet, data={"enabled": enabled}
        )
        self.assertTrue(form.is_valid(), form.errors)
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        request = HttpRequest()
        request.user = factory.make_User()
        dhcp_snippet = form.save(endpoint, request)
        self.assertEqual(enabled, dhcp_snippet.enabled)

    def test_updates_node(self):
        dhcp_snippet = factory.make_DHCPSnippet()
        node = factory.make_Node()
        form = DHCPSnippetForm(
            instance=dhcp_snippet, data={"node": node.system_id}
        )
        self.assertTrue(form.is_valid(), form.errors)
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        request = HttpRequest()
        request.user = factory.make_User()
        dhcp_snippet = form.save(endpoint, request)
        self.assertEqual(node, dhcp_snippet.node)

    def test_updates_node_when_subnet_set(self):
        dhcp_snippet = factory.make_DHCPSnippet(subnet=factory.make_Subnet())
        node = factory.make_Node()
        form = DHCPSnippetForm(
            instance=dhcp_snippet, data={"node": node.system_id}
        )
        self.assertTrue(form.is_valid(), form.errors)
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        request = HttpRequest()
        request.user = factory.make_User()
        dhcp_snippet = form.save(endpoint, request)
        self.assertIsNone(dhcp_snippet.subnet)
        self.assertEqual(node, dhcp_snippet.node)

    def test_updates_subnet(self):
        dhcp_snippet = factory.make_DHCPSnippet()
        subnet = factory.make_Subnet()
        form = DHCPSnippetForm(
            instance=dhcp_snippet, data={"subnet": subnet.id}
        )
        self.assertTrue(form.is_valid(), form.errors)
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        request = HttpRequest()
        request.user = factory.make_User()
        dhcp_snippet = form.save(endpoint, request)
        self.assertEqual(subnet, dhcp_snippet.subnet)

    def test_updates_subnet_when_node_set(self):
        dhcp_snippet = factory.make_DHCPSnippet(node=factory.make_Node())
        subnet = factory.make_Subnet()
        form = DHCPSnippetForm(
            instance=dhcp_snippet, data={"subnet": subnet.id}
        )
        self.assertTrue(form.is_valid(), form.errors)
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        request = HttpRequest()
        request.user = factory.make_User()
        dhcp_snippet = form.save(endpoint, request)
        self.assertIsNone(dhcp_snippet.node)
        self.assertEqual(subnet, dhcp_snippet.subnet)

    def test_cannot_update_both_node_and_subnet(self):
        dhcp_snippet = factory.make_DHCPSnippet()
        form = DHCPSnippetForm(
            instance=dhcp_snippet,
            data={
                "node": factory.make_Node().system_id,
                "subnet": factory.make_Subnet().id,
            },
        )
        self.assertFalse(form.is_valid())

    def test_update_failure_doesnt_delete_value(self):
        dhcp_snippet = factory.make_DHCPSnippet()
        value = dhcp_snippet.value.data
        form = DHCPSnippetForm(
            instance=dhcp_snippet,
            data={
                "node": factory.make_Node().system_id,
                "subnet": factory.make_Subnet().id,
            },
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(value, reload_object(dhcp_snippet).value.data)

    def test_update_global_snippet_resets_node(self):
        node = factory.make_Node()
        dhcp_snippet = factory.make_DHCPSnippet(node=node)
        form = DHCPSnippetForm(
            instance=dhcp_snippet, data={"global_snippet": True}
        )
        self.assertTrue(form.is_valid(), form.errors)
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        request = HttpRequest()
        request.user = factory.make_User()
        dhcp_snippet = form.save(endpoint, request)
        self.assertIsNone(dhcp_snippet.node)

    def test_update_global_snippet_resets_subnet(self):
        subnet = factory.make_Subnet()
        dhcp_snippet = factory.make_DHCPSnippet(subnet=subnet)
        form = DHCPSnippetForm(
            instance=dhcp_snippet, data={"global_snippet": True}
        )
        self.assertTrue(form.is_valid(), form.errors)
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        request = HttpRequest()
        request.user = factory.make_User()
        dhcp_snippet = form.save(endpoint, request)
        self.assertIsNone(dhcp_snippet.subnet)

    def test_is_not_valid_when_validate_dhcp_config_fails(self):
        dhcpd_error = {
            "error": factory.make_name("error"),
            "line_num": random.randint(0, 1000),
            "line": factory.make_name("line"),
            "position": factory.make_name("position"),
        }
        self.patch(dhcpsnippet, "validate_dhcp_config").return_value = [
            dhcpd_error
        ]
        form = DHCPSnippetForm(
            data={
                "name": factory.make_name("name"),
                "value": factory.make_string(),
                "description": factory.make_string(),
                "enabled": True,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertEqual({"value": [dhcpd_error["error"]]}, form.errors)
        self.assertItemsEqual([], VersionedTextFile.objects.all())
        self.assertItemsEqual([], DHCPSnippet.objects.all())
