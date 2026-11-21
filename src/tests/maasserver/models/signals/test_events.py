# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for node transition event."""

from maasserver.enum import NODE_STATUS_CHOICES_DICT
from maasserver.models import Event
from maasserver.models.signals import power as node_query
from maasserver.node_status import get_failed_status, NODE_STATUS
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from provisioningserver.events import EVENT_DETAILS, EVENT_TYPES


class TestStatusTransitionEvent(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        # Circular imports.
        from maasserver.models import signals

        self.patch(signals.events, "STATE_TRANSITION_EVENT_CONNECT", True)

    def test_changing_status_of_node_emits_event(self):
        self.addCleanup(node_query.signals.enable)
        node_query.signals.disable()

        old_status = NODE_STATUS.COMMISSIONING
        node = factory.make_Node(status=old_status)
        node.update_status(get_failed_status(old_status))
        node.save()

        latest_event = Event.objects.filter(node=node).last()
        description = "From '{}' to '{}'".format(
            NODE_STATUS_CHOICES_DICT[old_status],
            NODE_STATUS_CHOICES_DICT[node.status],
        )
        self.assertEqual(
            (
                EVENT_TYPES.NODE_CHANGED_STATUS,
                EVENT_DETAILS[EVENT_TYPES.NODE_CHANGED_STATUS].description,
                description,
            ),
            (
                latest_event.type.name,
                latest_event.type.description,
                latest_event.description,
            ),
        )

    def test_changing_to_allocated_includes_user_name(self):
        old_status = NODE_STATUS.READY
        user = factory.make_User()
        node = factory.make_Node(status=old_status, with_boot_disk=True)
        node.acquire(user)

        latest_event = Event.objects.filter(node=node).last()
        description = "From '{}' to '{}' (to {})".format(
            NODE_STATUS_CHOICES_DICT[old_status],
            NODE_STATUS_CHOICES_DICT[node.status],
            user.username,
        )
        self.assertEqual(
            EVENT_TYPES.NODE_CHANGED_STATUS, latest_event.type.name
        )
        self.assertEqual(
            EVENT_DETAILS[EVENT_TYPES.NODE_CHANGED_STATUS].description,
            latest_event.type.description,
        )
        self.assertEqual(description, latest_event.description)
