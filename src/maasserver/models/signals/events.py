# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Emit node state transition event."""

from maasserver.enum import NODE_STATUS_CHOICES_DICT, NODE_TYPE
from maasserver.models import Event
from maasserver.models.node import (
    Controller,
    Device,
    Machine,
    Node,
    NODE_STATUS,
    RackController,
    RegionController,
)
from maasserver.utils.signals import SignalsManager
from provisioningserver.events import EVENT_DETAILS, EVENT_TYPES

NODE_CLASSES = [
    Node,
    Machine,
    Device,
    Controller,
    RackController,
    RegionController,
]


signals = SignalsManager()

# Useful to disconnect this in testing. TODO: Use the signals manager instead.
STATE_TRANSITION_EVENT_CONNECT = True


def emit_state_transition_event(instance, old_values, **kwargs):
    """Send a status transition event."""
    if (
        instance.node_type != NODE_TYPE.MACHINE
        or not STATE_TRANSITION_EVENT_CONNECT
    ):
        return
    node = instance
    [old_status] = old_values

    type_name = EVENT_TYPES.NODE_CHANGED_STATUS
    event_details = EVENT_DETAILS[type_name]
    description = "From '{}' to '{}'".format(
        NODE_STATUS_CHOICES_DICT[old_status],
        NODE_STATUS_CHOICES_DICT[node.status],
    )

    # Special-case for allocating nodes: we can include usernames here
    # to make the event log more useful.
    if node.status == NODE_STATUS.ALLOCATED:
        description += " (to %s)" % node.owner.username

    Event.objects.register_event_and_event_type(
        type_name,
        type_level=event_details.level,
        type_description=event_details.description,
        event_description=description,
        system_id=node.system_id,
    )


for klass in NODE_CLASSES:
    # Watch the status of all classes, as the node might switch types.
    # Only if its a machine will the handler care.
    signals.watch_fields(
        emit_state_transition_event, klass, ["status"], delete=False
    )

# Enable all signals by default.
signals.enable()
