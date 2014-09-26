# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for node transition event."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


from maasserver.enum import NODE_STATUS_CHOICES_DICT
from maasserver.models import Event
from maasserver.node_status import (
    get_failed_status,
    NODE_STATUS,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from provisioningserver.events import (
    EVENT_DETAILS,
    EVENT_TYPES,
    )


class TestStatusTransitionEvent(MAASServerTestCase):

    def setUp(self):
        super(TestStatusTransitionEvent, self).setUp()
        # Circular imports.
        from maasserver import event_connect
        self.patch(event_connect, 'STATE_TRANSITION_EVENT_CONNECT', True)

    def test_changing_status_of_node_emits_event(self):
        old_status = NODE_STATUS.COMMISSIONING
        node = factory.make_Node(status=old_status)
        node.status = get_failed_status(old_status)
        node.save()

        latest_event = Event.objects.filter(node=node).last()
        description = "From '%s' to '%s'" % (
            NODE_STATUS_CHOICES_DICT[old_status],
            NODE_STATUS_CHOICES_DICT[node.status],
        )
        self.assertEqual(
            (
                EVENT_TYPES.NODE_CHANGED_STATUS,
                EVENT_DETAILS[
                    EVENT_TYPES.NODE_CHANGED_STATUS].description,
                description,
            ),
            (
                latest_event.type.name,
                latest_event.type.description,
                latest_event.description,
            ))
