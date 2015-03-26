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
    "TransitionMonitor",
]

from copy import copy
from datetime import (
    datetime,
    timedelta,
)

from maasserver.rpc import getClientFor
from maasserver.utils.orm import transactional
from provisioningserver.logger import get_maas_logger
from provisioningserver.rpc.cluster import (
    CancelMonitor,
    StartMonitors,
)
from provisioningserver.utils.twisted import (
    asynchronous,
    synchronous,
)
from twisted.protocols import amp


maaslog = get_maas_logger("timers")


@synchronous
@transactional
def handle_monitor_expired(id, context):
    """Handle the 'monitor expired' signal.

    for :py:class:`~provisioningserver.rpc.region.MonitorExpired.
    """
    from maasserver.models import Node  # Avoid circular import.
    try:
        node = Node.objects.get(system_id=id)
    except Node.DoesNotExist:
        # Node doesn't exist, ignore.
        pass
    else:
        node.handle_monitor_expired(context)


class TransitionMonitor:
    """Convenience for working with transition monitors.

    This instance can be created in a transaction but can be then used outside
    of that transaction because it captures the database state it needs. Use
    like so::

      monitor = (
          TransitionMonitor.fromNode(my_node)
          .status_should_be(NODE_STATUS.WIBBLE)
          .within(seconds=1234)
          .start())

    """

    @classmethod
    def fromNode(cls, node):
        return cls(node.nodegroup.uuid, node.system_id)

    def __init__(self, nodegroup_uuid, system_id):
        super(TransitionMonitor, self).__init__()
        self.nodegroup_uuid = nodegroup_uuid
        self.system_id = system_id
        self.status = None
        self.timeout = None

    def within(self, seconds):
        assert isinstance(seconds, (int, long, float)), (
            "Expected a number, got: %r" % (seconds,))
        assert 0 <= seconds
        monitor = copy(self)
        monitor.timeout = timedelta(seconds=seconds)
        return monitor

    def status_should_be(self, status):
        monitor = copy(self)
        monitor.status = status
        return monitor

    @asynchronous(timeout=5)
    def start(self):
        """Start cluster-side transition monitor."""

        if self.status is None:
            raise ValueError("No target status defined.")
        if self.timeout is None:
            raise ValueError("No time-out defined.")

        context = {
            'node_status': self.status,
            'timeout': self.timeout.total_seconds(),
        }
        monitor = {
            'context': context,
            'deadline': datetime.now(tz=amp.utc) + self.timeout,
            'id': self.system_id,
        }

        def start_monitor(client):
            return client(StartMonitors, monitors=[monitor])

        d = getClientFor(self.nodegroup_uuid)
        d.addCallback(start_monitor)
        return d

    @asynchronous(timeout=5)
    def stop(self):
        """Stop cluster-side transition monitor."""

        def stop_monitor(client):
            return client(CancelMonitor, id=self.system_id)

        d = getClientFor(self.nodegroup_uuid)
        d.addCallback(stop_monitor)
        return d
