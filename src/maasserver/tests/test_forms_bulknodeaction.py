# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `BulkNodeActionForm`."""

__all__ = []

from django.db import transaction
from maasserver.enum import NODE_STATUS
from maasserver.exceptions import NodeActionError
from maasserver.forms import (
    BulkNodeActionForm,
    SetZoneBulkAction,
)
from maasserver.models import Node
from maasserver.node_action import (
    Delete,
    PowerOff,
    PowerOn,
)
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)


class TestBulkNodeActionForm(MAASServerTestCase):
    """Tests for `BulkNodeActionForm`."""

    def test_first_action_is_empty(self):
        form = BulkNodeActionForm(user=factory.make_admin())
        action = form.fields['action']
        default_action = action.choices[0][0]
        required = action.required
        # The default action is the empty string (i.e. no action)
        # and it's a required field.
        self.assertEqual(('', True), (default_action, required))

    def test_admin_is_offered_bulk_node_change(self):
        form = BulkNodeActionForm(user=factory.make_admin())
        choices = form.fields['action'].choices
        self.assertNotEqual(
            [],
            [choice for choice in choices if choice[0] == 'set_zone'])

    def test_nonadmin_is_not_offered_bulk_node_change(self):
        form = BulkNodeActionForm(user=factory.make_User())
        choices = form.fields['action'].choices
        self.assertEqual(
            [],
            [choice for choice in choices if choice[0] == 'set_zone'])

    def test_rejects_empty_system_ids(self):
        form = BulkNodeActionForm(
            user=factory.make_admin(),
            data=dict(action=Delete.name, system_id=[]))
        self.assertFalse(form.is_valid(), form._errors)
        self.assertEqual(
            ["No node selected."],
            form._errors['system_id'])

    def test_rejects_invalid_system_ids(self):
        node = factory.make_Node()
        system_id_to_delete = [node.system_id, "wrong-system_id"]
        form = BulkNodeActionForm(
            user=factory.make_admin(),
            data=dict(
                action=Delete.name,
                system_id=system_id_to_delete))
        self.assertFalse(form.is_valid(), form._errors)
        self.assertEqual(
            ["Some of the given system ids are invalid system ids."],
            form._errors['system_id'])

    def test_rejects_if_no_action(self):
        form = BulkNodeActionForm(
            user=factory.make_admin(),
            data=dict(system_id=[factory.make_Node().system_id]))
        self.assertFalse(form.is_valid(), form._errors)

    def test_rejects_if_invalid_action(self):
        form = BulkNodeActionForm(
            user=factory.make_admin(),
            data=dict(
                action="invalid-action",
                system_id=[factory.make_Node().system_id]))
        self.assertFalse(form.is_valid(), form._errors)

    def test_set_zone_does_not_work_if_not_admin(self):
        node = factory.make_Node()
        form = BulkNodeActionForm(
            user=factory.make_User(),
            data={
                'action': SetZoneBulkAction.name,
                'zone': factory.make_Zone().name,
                'system_id': [node.system_id],
            })
        self.assertFalse(form.is_valid())
        self.assertIn(
            "Select a valid choice. "
            "set_zone is not one of the available choices.",
            form._errors['action'])

    def test_zone_field_rejects_empty_zone(self):
        # If the field is present, the zone name has to be valid
        # and the empty string is not a valid zone name.
        form = BulkNodeActionForm(
            user=factory.make_admin(),
            data={
                'action': SetZoneBulkAction.name,
                'zone': '',
            })
        self.assertFalse(form.is_valid(), form._errors)
        self.assertEqual(
            ["This field is required."],
            form._errors['zone'])

    def test_zone_field_present_if_data_is_empty(self):
        form = BulkNodeActionForm(
            user=factory.make_admin(),
            data={})
        self.assertIn('zone', form.fields)

    def test_zone_field_not_present_action_is_not_SetZoneBulkAction(self):
        form = BulkNodeActionForm(
            user=factory.make_admin(),
            data={'action': factory.make_name('action')})
        self.assertNotIn('zone', form.fields)


class TestBulkNodeActionFormSave(MAASTransactionServerTestCase):
    """Tests for `BulkNodeActionForm.save()`.

    These are transactional tests, meaning that commits to the database must
    be made to test behaviour.
    """

    def test_performs_action(self):
        with transaction.atomic():
            node1 = factory.make_Node()
            node2 = factory.make_Node()
            node3 = factory.make_Node()
            system_id_to_delete = [node1.system_id, node2.system_id]
            form = BulkNodeActionForm(
                user=factory.make_admin(),
                data=dict(
                    action=Delete.name,
                    system_id=system_id_to_delete))
            self.assertTrue(form.is_valid(), form._errors)

        with transaction.atomic():
            done, not_actionable, not_permitted = form.save()

        self.assertEqual(
            [2, 0, 0],
            [done, not_actionable, not_permitted])

        with transaction.atomic():
            existing_nodes = list(Node.objects.filter(
                system_id__in=system_id_to_delete))
            node3_system_id = reload_object(node3).system_id
            self.assertEqual(
                [[], node3.system_id],
                [existing_nodes, node3_system_id])

    def test_perform_action_catches_start_action_errors(self):
        error_text = factory.make_string(prefix="NodeActionError")
        exc = NodeActionError(error_text)
        self.patch(PowerOn, "execute").side_effect = exc

        with transaction.atomic():
            user = factory.make_User()
            factory.make_SSHKey(user)
            node = factory.make_Node(status=NODE_STATUS.READY, owner=user)
            form = BulkNodeActionForm(
                user=user,
                data=dict(
                    action=PowerOn.name,
                    system_id=[node.system_id]))
            self.assertTrue(form.is_valid(), form._errors)

        with transaction.atomic():
            done, not_actionable, not_permitted = form.save()

        self.assertEqual(
            [0, 1, 0],
            [done, not_actionable, not_permitted])

    def test_gives_stat_when_not_applicable(self):
        with transaction.atomic():
            node1 = factory.make_Node(status=NODE_STATUS.NEW)
            node2 = factory.make_Node(status=NODE_STATUS.FAILED_COMMISSIONING)
            system_id_for_action = [node1.system_id, node2.system_id]
            form = BulkNodeActionForm(
                user=factory.make_admin(),
                data=dict(
                    action=PowerOn.name,
                    system_id=system_id_for_action))
            self.assertTrue(form.is_valid(), form._errors)

        with transaction.atomic():
            done, not_actionable, not_permitted = form.save()

        self.assertEqual(
            [0, 2, 0],
            [done, not_actionable, not_permitted])

    def test_gives_stat_when_no_permission(self):
        with transaction.atomic():
            user = factory.make_User()
            node = factory.make_Node(
                status=NODE_STATUS.DEPLOYED, owner=factory.make_User())
            system_id_for_action = [node.system_id]
            form = BulkNodeActionForm(
                user=user,
                data=dict(
                    action=PowerOff.name,
                    system_id=system_id_for_action))
            self.assertTrue(form.is_valid(), form._errors)

        with transaction.atomic():
            done, not_actionable, not_permitted = form.save()

        self.assertEqual(
            [0, 0, 1],
            [done, not_actionable, not_permitted])

    def test_gives_stat_when_action_is_inhibited(self):
        with transaction.atomic():
            node = factory.make_Node(
                status=NODE_STATUS.ALLOCATED, owner=factory.make_User())
            form = BulkNodeActionForm(
                user=factory.make_admin(),
                data=dict(
                    action=PowerOn.name,
                    system_id=[node.system_id]))
            self.assertTrue(form.is_valid(), form._errors)

        with transaction.atomic():
            done, not_actionable, not_permitted = form.save()

        self.assertEqual(
            [0, 1, 0],
            [done, not_actionable, not_permitted])

    def test_set_zone_sets_zone_on_node(self):
        with transaction.atomic():
            node = factory.make_Node()
            zone = factory.make_Zone()
            form = BulkNodeActionForm(
                user=factory.make_admin(),
                data={
                    'action': 'set_zone',
                    'zone': zone.name,
                    'system_id': [node.system_id],
                })
            self.assertTrue(form.is_valid(), form._errors)

        with transaction.atomic():
            done, not_actionable, not_permitted = form.save()

        self.assertEqual(
            [1, 0, 0],
            [done, not_actionable, not_permitted])

        with transaction.atomic():
            node = reload_object(node)
            self.assertEqual(zone, node.zone)

    def test_set_zone_leaves_unselected_nodes_alone(self):
        with transaction.atomic():
            unselected_node = factory.make_Node()
            original_zone = unselected_node.zone
            form = BulkNodeActionForm(
                user=factory.make_admin(),
                data={
                    'action': SetZoneBulkAction.name,
                    'zone': factory.make_Zone().name,
                    'system_id': [factory.make_Node().system_id],
                })
            self.assertTrue(form.is_valid(), form._errors)

        with transaction.atomic():
            done, not_actionable, not_permitted = form.save()

        self.assertEqual(
            [1, 0, 0],
            [done, not_actionable, not_permitted])

        with transaction.atomic():
            unselected_node = reload_object(unselected_node)
            self.assertEqual(original_zone, unselected_node.zone)
