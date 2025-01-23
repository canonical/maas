# Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.dhcpsnippet`"""


from email.utils import format_datetime
import random

from maascommon.events import AUDIT
from maasserver.models import DHCPSnippet, Event, VersionedTextFile
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from maasserver.websockets.base import (
    dehydrate_datetime,
    HandlerPermissionError,
    HandlerValidationError,
)
from maasserver.websockets.handlers.dhcpsnippet import DHCPSnippetHandler


class TestDHCPSnippetHandler(MAASServerTestCase):
    def setUp(self):
        super().setUp()

    def dehydrate_dhcp_snippet(self, dhcp_snippet):
        node_system_id = None
        subnet_id = None
        iprange_id = None
        if dhcp_snippet.subnet is not None:
            subnet_id = dhcp_snippet.subnet.id
            if dhcp_snippet.iprange is not None:
                iprange_id = dhcp_snippet.iprange.id
        elif dhcp_snippet.node is not None:
            node_system_id = dhcp_snippet.node.system_id
        return {
            "id": dhcp_snippet.id,
            "name": dhcp_snippet.name,
            "description": dhcp_snippet.description,
            "value": dhcp_snippet.value.data,
            "history": [
                {
                    "id": value.id,
                    "value": value.data,
                    "created": format_datetime(value.created),
                }
                for value in dhcp_snippet.value.previous_versions()
            ],
            "enabled": dhcp_snippet.enabled,
            "node": node_system_id,
            "subnet": subnet_id,
            "iprange": iprange_id,
            "updated": dehydrate_datetime(dhcp_snippet.updated),
            "created": dehydrate_datetime(dhcp_snippet.created),
        }

    def test_get_global(self):
        user = factory.make_User()
        handler = DHCPSnippetHandler(user, {}, None)
        dhcp_snippet = factory.make_DHCPSnippet()
        self.assertEqual(
            self.dehydrate_dhcp_snippet(dhcp_snippet),
            handler.get({"id": dhcp_snippet.id}),
        )

    def test_get_with_subnet(self):
        user = factory.make_User()
        handler = DHCPSnippetHandler(user, {}, None)
        subnet = factory.make_Subnet()
        dhcp_snippet = factory.make_DHCPSnippet(subnet=subnet)
        self.assertEqual(
            self.dehydrate_dhcp_snippet(dhcp_snippet),
            handler.get({"id": dhcp_snippet.id}),
        )

    def test_get_with_node(self):
        user = factory.make_User()
        handler = DHCPSnippetHandler(user, {}, None)
        node = factory.make_Node()
        dhcp_snippet = factory.make_DHCPSnippet(node=node)
        self.assertEqual(
            self.dehydrate_dhcp_snippet(dhcp_snippet),
            handler.get({"id": dhcp_snippet.id}),
        )

    def test_list(self):
        user = factory.make_User()
        handler = DHCPSnippetHandler(user, {}, None)
        expected_dhcp_snippets = [
            self.dehydrate_dhcp_snippet(factory.make_DHCPSnippet())
            for _ in range(3)
        ]
        self.assertCountEqual(expected_dhcp_snippets, handler.list({}))

    def test_create_is_admin_only(self):
        user = factory.make_User()
        handler = DHCPSnippetHandler(user, {}, None)
        self.assertRaises(HandlerPermissionError, handler.create, {})

    def test_create(self):
        user = factory.make_admin()
        handler = DHCPSnippetHandler(user, {}, None)
        dhcp_snippet_name = factory.make_name("dhcp_snippet_name")
        handler.create(
            {"name": dhcp_snippet_name, "value": factory.make_string()}
        )
        self.assertIsNotNone(DHCPSnippet.objects.get(name=dhcp_snippet_name))
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(
            event.description, "Created DHCP snippet '%s'." % dhcp_snippet_name
        )

    def test_update_is_admin_only(self):
        user = factory.make_User()
        handler = DHCPSnippetHandler(user, {}, None)
        self.assertRaises(HandlerPermissionError, handler.update, {})

    def test_update(self):
        user = factory.make_admin()
        handler = DHCPSnippetHandler(user, {}, None)
        dhcp_snippet = factory.make_DHCPSnippet()
        node = factory.make_Node()
        handler.update({"id": dhcp_snippet.id, "node": node.system_id})
        dhcp_snippet = reload_object(dhcp_snippet)
        self.assertEqual(node, dhcp_snippet.node)
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(
            event.description, "Updated DHCP snippet '%s'." % dhcp_snippet.name
        )

    def test_delete_is_admin_only(self):
        user = factory.make_User()
        handler = DHCPSnippetHandler(user, {}, None)
        self.assertRaises(HandlerPermissionError, handler.delete, {})

    def test_delete(self):
        user = factory.make_admin()
        handler = DHCPSnippetHandler(user, {}, None)
        dhcp_snippet = factory.make_DHCPSnippet()
        handler.delete({"id": dhcp_snippet.id})
        self.assertRaises(
            DHCPSnippet.DoesNotExist,
            DHCPSnippet.objects.get,
            id=dhcp_snippet.id,
        )

    def test_revert_is_admin_only(self):
        user = factory.make_User()
        handler = DHCPSnippetHandler(user, {}, None)
        self.assertRaises(HandlerPermissionError, handler.delete, {})

    def test_revert(self):
        user = factory.make_admin()
        handler = DHCPSnippetHandler(user, {}, None)
        dhcp_snippet = factory.make_DHCPSnippet()
        textfile_ids = [dhcp_snippet.value.id]
        for _ in range(10):
            dhcp_snippet.value = dhcp_snippet.value.update(
                factory.make_string()
            )
            dhcp_snippet.save()
            textfile_ids.append(dhcp_snippet.value.id)
        revert_to = random.randint(-10, -1)
        reverted_ids = textfile_ids[revert_to:]
        remaining_ids = textfile_ids[:revert_to]
        handler.revert({"id": dhcp_snippet.id, "to": revert_to})
        dhcp_snippet = reload_object(dhcp_snippet)
        self.assertEqual(
            VersionedTextFile.objects.get(id=textfile_ids[revert_to - 1]).data,
            dhcp_snippet.value.data,
        )
        for i in reverted_ids:
            self.assertRaises(
                VersionedTextFile.DoesNotExist,
                VersionedTextFile.objects.get,
                id=i,
            )
        for i in remaining_ids:
            self.assertIsNotNone(VersionedTextFile.objects.get(id=i))

    def test_revert_requires_to(self):
        user = factory.make_admin()
        handler = DHCPSnippetHandler(user, {}, None)
        dhcp_snippet = factory.make_DHCPSnippet()
        self.assertRaises(
            HandlerValidationError, handler.revert, {"id": dhcp_snippet.id}
        )

    def test_revert_requires_to_to_be_an_int(self):
        user = factory.make_admin()
        handler = DHCPSnippetHandler(user, {}, None)
        dhcp_snippet = factory.make_DHCPSnippet()
        self.assertRaises(
            HandlerValidationError,
            handler.revert,
            {"id": dhcp_snippet.id, "to": factory.make_name("to")},
        )

    def test_revert_errors_on_invalid_id(self):
        user = factory.make_admin()
        handler = DHCPSnippetHandler(user, {}, None)
        dhcp_snippet = factory.make_DHCPSnippet()
        textfile = VersionedTextFile.objects.create(data=factory.make_string())
        self.assertRaises(
            HandlerValidationError,
            handler.revert,
            {"id": dhcp_snippet.id, "to": textfile.id},
        )
