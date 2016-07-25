# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Status monitoring service."""

__all__ = [
    'mark_nodes_failed_after_expiring',
    'StatusMonitorService',
    ]

from maasserver.enum import (
    NODE_STATUS_CHOICES_DICT,
    NODE_TYPE,
)
from maasserver.models.node import Node
from maasserver.models.timestampedmodel import now
from maasserver.node_status import (
    NODE_FAILURE_MONITORED_STATUS_TIMEOUTS,
    NODE_FAILURE_MONITORED_STATUS_TRANSITIONS,
)
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.utils.twisted import synchronous
from twisted.application.internet import TimerService


def mark_nodes_failed_after_expiring():
    """Mark all nodes in that database as failed where the status did not
    transition in time. `status_expires` is checked on the node to see if the
    current time is newer than the expired time.

    Status monitors are only available for Machines that are Commissioning,
    Deploying or Releasing.
    """
    current_db_time = now()
    expired_nodes = Node.objects.filter(
        node_type=NODE_TYPE.MACHINE,
        status__in=NODE_FAILURE_MONITORED_STATUS_TRANSITIONS.keys(),
        status_expires__isnull=False,
        status_expires__lte=current_db_time)
    for node in expired_nodes:
        comment = "Machine operation '%s' timed out after %s minutes." % (
            NODE_STATUS_CHOICES_DICT[node.status],
            NODE_FAILURE_MONITORED_STATUS_TIMEOUTS[node.status],
            )
        node.mark_failed(commit=False, comment=comment)
        node.status_expires = None
        node.save()


class StatusMonitorService(TimerService, object):
    """Service to periodically monitor node statues and mark them failed.

    This will run immediately when it's started, then once every 2 mintues,
    though the interval can be overridden by passing it to the
    constructor.
    """

    def __init__(self, interval=(2 * 60)):
        mark_failed = synchronous(
            transactional(mark_nodes_failed_after_expiring))
        super(StatusMonitorService, self).__init__(
            interval, deferToDatabase, mark_failed)
