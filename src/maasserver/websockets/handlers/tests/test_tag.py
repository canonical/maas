# Copyright 2015-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maascommon.events import AUDIT
from maasserver.enum import NODE_TYPE
from maasserver.models import Event, Tag
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from maasserver.websockets.base import (
    dehydrate_datetime,
    HandlerPermissionError,
    HandlerValidationError,
)
from maasserver.websockets.handlers.tag import TagHandler
from provisioningserver.events import EVENT_TYPES


class TestTagHandler(MAASServerTestCase):
    def dehydrate_tag(self, tag):
        data = {
            "id": tag.id,
            "name": tag.name,
            "definition": tag.definition,
            "comment": tag.comment,
            "kernel_opts": tag.kernel_opts,
            "updated": dehydrate_datetime(tag.updated),
            "created": dehydrate_datetime(tag.created),
            "machine_count": tag.node_set.filter(
                node_type=NODE_TYPE.MACHINE
            ).count(),
            "device_count": tag.node_set.filter(
                node_type=NODE_TYPE.DEVICE
            ).count(),
            "controller_count": tag.node_set.filter(
                node_type__in=(
                    NODE_TYPE.REGION_CONTROLLER,
                    NODE_TYPE.RACK_CONTROLLER,
                    NODE_TYPE.REGION_AND_RACK_CONTROLLER,
                )
            ).count(),
        }
        return data

    def test_get(self):
        user = factory.make_User()
        handler = TagHandler(user, {}, None)
        tag = factory.make_Tag()
        self.assertEqual(self.dehydrate_tag(tag), handler.get({"id": tag.id}))

    def test_get_include_counts(self):
        tag = factory.make_Tag()
        tag.node_set.add(
            factory.make_Node(),
            factory.make_Device(),
            factory.make_Device(),
            factory.make_RackController(),
            factory.make_RegionController(),
            factory.make_RegionRackController(),
        )
        handler = TagHandler(factory.make_admin(), {}, None)
        details = handler.get({"id": tag.id})
        self.assertEqual(details["machine_count"], 1)
        self.assertEqual(details["device_count"], 2)
        self.assertEqual(details["controller_count"], 3)

    def test_list(self):
        user = factory.make_User()
        handler = TagHandler(user, {}, None)
        factory.make_Tag()
        expected_tags = [self.dehydrate_tag(tag) for tag in Tag.objects.all()]
        self.assertCountEqual(expected_tags, handler.list({}))

    def test_create(self):
        mock_populate_nodes = self.patch(Tag, "populate_nodes")
        handler = TagHandler(factory.make_admin(), {}, None)
        result = handler.create(
            {
                "name": factory.make_name("name"),
                "comment": factory.make_name("comment"),
                "kernel_opts": factory.make_name("kernel_opts"),
                "definition": '//node[@id="memory"]/size = 1073741824',
            }
        )
        [tag] = Tag.objects.all()
        self.assertEqual(self.dehydrate_tag(tag), result)
        mock_populate_nodes.assert_called_once()
        # an audit log entry is created
        event = Event.objects.get(type__level=AUDIT)
        self.assertEqual(event.type.name, EVENT_TYPES.TAG)
        self.assertEqual(event.description, f"Tag '{tag.name}' created.")

    def test_create_no_admin(self):
        handler = TagHandler(factory.make_User(), {}, None)
        self.assertRaises(
            HandlerPermissionError,
            handler.create,
            {
                "name": factory.make_name("name"),
                "comment": factory.make_name("comment"),
                "kernel_opts": factory.make_name("kernel_opts"),
                "definition": '//node[@id="memory"]/size = 1073741824',
            },
        )
        self.assertFalse(Tag.objects.exists())

    def test_update(self):
        mock_populate_nodes = self.patch(Tag, "populate_nodes")
        handler = TagHandler(factory.make_admin(), {}, None)
        tag = factory.make_Tag()
        old_name = tag.name
        new_name = factory.make_name("name")
        new_definition = '//node[@id="memory"]/size = 1073741824'
        result = handler.update(
            {
                "id": tag.id,
                "name": new_name,
                "definition": new_definition,
            }
        )
        tag = reload_object(tag)
        self.assertEqual(self.dehydrate_tag(tag), result)
        self.assertEqual(tag.name, new_name)
        self.assertEqual(tag.definition, new_definition)
        mock_populate_nodes.assert_called_once()
        event = Event.objects.get(type__level=AUDIT)
        self.assertEqual(event.type.name, EVENT_TYPES.TAG)
        self.assertEqual(
            event.description, f"Tag '{old_name}' renamed to '{new_name}'."
        )

    def test_update_no_admin(self):
        handler = TagHandler(factory.make_User(), {}, None)
        tag = factory.make_Tag()
        new_name = factory.make_name("name")
        new_definition = '//node[@id="memory"]/size = 1073741824'
        self.assertRaises(
            HandlerPermissionError,
            handler.update,
            {
                "id": tag.id,
                "name": new_name,
                "definition": new_definition,
            },
        )
        tag = reload_object(tag)
        self.assertNotEqual(tag.name, new_name)
        self.assertNotEqual(tag.definition, new_definition)

    def test_update_validate_xpath(self):
        handler = TagHandler(factory.make_admin(), {}, None)
        tag = factory.make_Tag()
        error = self.assertRaises(
            HandlerValidationError,
            handler.update,
            {
                "id": tag.id,
                "definition": "invalid::tag",
            },
        )
        self.assertEqual(
            error.message_dict,
            {"definition": ["Invalid xpath expression: Invalid expression"]},
        )

    def test_delete(self):
        handler = TagHandler(factory.make_admin(), {}, None)
        tag = factory.make_Tag()
        handler.delete({"id": tag.id})
        self.assertFalse(Tag.objects.exists())
        event = Event.objects.get(type__level=AUDIT)
        self.assertEqual(event.type.name, EVENT_TYPES.TAG)
        self.assertEqual(event.description, f"Tag '{tag.name}' deleted.")

    def test_delete_no_admin(self):
        handler = TagHandler(factory.make_User(), {}, None)
        tag = factory.make_Tag()
        self.assertRaises(
            HandlerPermissionError, handler.delete, {"id": tag.id}
        )
        self.assertIsNotNone(reload_object(tag))

    def test_node_filter(self):
        tag = factory.make_Tag()
        factory.make_Machine(hostname="untagged")
        tag.node_set.add(
            factory.make_Machine(hostname="nope1"),
            factory.make_Machine(hostname="nope2"),
        )
        machine = factory.make_Machine(hostname="matching")
        tag2 = factory.make_Tag()
        tag2.node_set.add(machine)
        tag2.node_set.add(factory.make_Machine())
        handler = TagHandler(factory.make_admin(), {}, None)
        listing = handler.list(
            {
                "node_filter": {
                    "hostname": [machine.hostname],
                }
            }
        )
        self.assertEqual(len(listing), 1, listing)
        self.assertEqual(listing[0]["name"], tag2.name)
        self.assertEqual(listing[0]["machine_count"], 1)

    def test_node_filter_by_physical_disk_count(self):
        tag = factory.make_Tag()
        factory.make_Tag()
        machine = factory.make_Machine()
        factory.make_PhysicalBlockDevice(node=machine)
        tag.node_set.add(machine)

        handler = TagHandler(factory.make_admin(), {}, None)
        listing = handler.list(
            {
                "node_filter": {
                    "physical_disk_count": 2,
                }
            }
        )
        self.assertEqual(len(listing), 1, listing)
        self.assertEqual(listing[0]["name"], tag.name)
        self.assertEqual(listing[0]["machine_count"], 1)
