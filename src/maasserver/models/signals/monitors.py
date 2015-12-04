# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Connect monitor utilities with signals."""

__all__ = [
    ]


from maasserver.models import Node
from maasserver.node_status import get_failed_status
from maasserver.utils.signals import connect_to_field_change

# Useful to disconnect this in testing.
MONITOR_CANCEL_CONNECT = True


def stop_transition_monitor_handler(instance, old_values, **kwargs):
    """When a monitored Node changes status, cancel the related monitor."""
    if not MONITOR_CANCEL_CONNECT:
        return
    node = instance
    [old_status] = old_values
    if get_failed_status(old_status) is not None:
        node.stop_transition_monitor()


connect_to_field_change(
    stop_transition_monitor_handler,
    Node, ['status'], delete=True)
