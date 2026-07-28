# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `BulkNodeActionForm`."""

from maasserver.forms import BulkNodeSetZoneForm
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object


class TestBulkNodeActionForm(MAASServerTestCase):
    """Tests for `BulkNodeActionForm`."""

    def test_rejects_empty_system_ids(self):
        form = BulkNodeSetZoneForm(
            user=factory.make_admin(),
            data={"system_id": [], "zone": factory.make_Zone().name},
        )
        self.assertFalse(form.is_valid(), form._errors)
        self.assertEqual(["No node selected."], form._errors["system_id"])

    def test_rejects_invalid_system_ids(self):
        node = factory.make_Node()
        system_ids = [node.system_id, "wrong-system_id"]
        form = BulkNodeSetZoneForm(
            user=factory.make_admin(),
            data={"system_id": system_ids, "zone": factory.make_Zone().name},
        )
        self.assertFalse(form.is_valid(), form._errors)
        self.assertEqual(
            ["Some of the given system ids are invalid system ids."],
            form._errors["system_id"],
        )

    def test_set_zone_does_not_work_if_not_superuser(self):
        node = factory.make_Node()
        form = BulkNodeSetZoneForm(
            user=factory.make_User(),
            data={
                "zone": factory.make_Zone().name,
                "system_id": [node.system_id],
            },
        )
        self.assertFalse(form.is_valid())

    def test_zone_field_rejects_empty_zone(self):
        # If the field is present, the zone name has to be valid
        # and the empty string is not a valid zone name.
        form = BulkNodeSetZoneForm(
            user=factory.make_admin(), data={"zone": ""}
        )
        self.assertFalse(form.is_valid(), form._errors)
        self.assertEqual(["This field is required."], form._errors["zone"])

    def test_set_zone_sets_zone_on_node(self):
        node = factory.make_Node()
        zone = factory.make_Zone()
        form = BulkNodeSetZoneForm(
            user=factory.make_admin(),
            data={"zone": zone.name, "system_id": [node.system_id]},
        )
        self.assertTrue(form.is_valid(), form._errors)

        done, not_actionable, not_permitted = form.save()

        self.assertEqual([1, 0, 0], [done, not_actionable, not_permitted])

        node = reload_object(node)
        self.assertEqual(zone, node.zone)

    def test_set_zone_leaves_unselected_nodes_alone(self):
        unselected_node = factory.make_Node()
        original_zone = unselected_node.zone
        form = BulkNodeSetZoneForm(
            user=factory.make_admin(),
            data={
                "zone": factory.make_Zone().name,
                "system_id": [factory.make_Node().system_id],
            },
        )
        self.assertTrue(form.is_valid(), form._errors)

        done, not_actionable, not_permitted = form.save()

        self.assertEqual([1, 0, 0], [done, not_actionable, not_permitted])

        unselected_node = reload_object(unselected_node)
        self.assertEqual(original_zone, unselected_node.zone)
