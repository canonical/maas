# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to timers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "handle_timer_expired",
]

from maasserver.models import Node
from maasserver.utils.async import transactional
from provisioningserver.enum import TIMER_TYPE
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils.twisted import synchronous


maaslog = get_maas_logger("timers")


@synchronous
@transactional
def handle_timer_expired(id, context):
    """Handle the 'timer expired' signal.

    for :py:class:`~provisioningserver.rpc.region.TimerExpired.
    """
    if context['type'] == TIMER_TYPE.NODE_STATE_CHANGE:
        # This is a node timer, pass the event on to the node.
        try:
            node = Node.objects.get(system_id=id)
        except Node.DoesNotExist:
            # Node doesn't exist, ignore.
            pass
        else:
            node.handle_timer_expired(context)
    else:
        # Unknown timer, log and exit.
        maaslog.error(
            "Timer of an unknown type (%s) expired", context['type'])
