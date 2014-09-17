# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to monitors."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "handle_monitor_expired",
]

from maasserver.models import Node
from maasserver.utils.async import transactional
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils.twisted import synchronous


maaslog = get_maas_logger("timers")


@synchronous
@transactional
def handle_monitor_expired(id, context):
    """Handle the 'monitor expired' signal.

    for :py:class:`~provisioningserver.rpc.region.MonitorExpired.
    """
    try:
        node = Node.objects.get(system_id=id)
    except Node.DoesNotExist:
        # Node doesn't exist, ignore.
        pass
    else:
        node.handle_monitor_expired(context)
