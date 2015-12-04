# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Emit node state transition event."""

__all__ = []


from maasserver.enum import NODE_STATUS_CHOICES_DICT
from maasserver.models import (
    Event,
    Node,
)
from maasserver.models.node import NODE_STATUS
from maasserver.utils.signals import connect_to_field_change
from provisioningserver.events import (
    EVENT_DETAILS,
    EVENT_TYPES,
)

# Useful to disconnect this in testing.
STATE_TRANSITION_EVENT_CONNECT = True


def emit_state_transition_event(instance, old_values, **kwargs):
    """Send a status transition event."""
    if not STATE_TRANSITION_EVENT_CONNECT:
        return
    node = instance
    [old_status] = old_values

    type_name = EVENT_TYPES.NODE_CHANGED_STATUS
    event_details = EVENT_DETAILS[type_name]
    description = "From '%s' to '%s'" % (
        NODE_STATUS_CHOICES_DICT[old_status],
        NODE_STATUS_CHOICES_DICT[node.status],
    )

    # Special-case for allocating nodes: we can include usernames here
    # to make the event log more useful.
    if node.status == NODE_STATUS.ALLOCATED:
        description += " (to %s)" % node.owner.username

    Event.objects.register_event_and_event_type(
        node.system_id, type_name, type_level=event_details.level,
        type_description=event_details.description,
        event_description=description)


connect_to_field_change(
    emit_state_transition_event,
    Node, ['status'], delete=False)
