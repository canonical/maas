# Copyright 2016-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Status monitoring service."""

__all__ = [
    'mark_nodes_failed_after_expiring',
    'StatusMonitorService',
    ]

from datetime import (
    datetime,
    timedelta,
)

from maasserver.enum import (
    NODE_STATUS,
    NODE_STATUS_CHOICES_DICT,
)
from maasserver.models.node import Node
from maasserver.models.timestampedmodel import now
from maasserver.node_status import (
    NODE_FAILURE_MONITORED_STATUS_TIMEOUTS,
    NODE_FAILURE_MONITORED_STATUS_TRANSITIONS,
)
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from metadataserver.enum import SCRIPT_STATUS
from provisioningserver.refresh.node_info_scripts import NODE_INFO_SCRIPTS
from provisioningserver.utils.twisted import synchronous
from twisted.application.internet import TimerService


def mark_nodes_failed_after_expiring():
    """Mark all nodes in that database as failed where the status did not
    transition in time. `status_expires` is checked on the node to see if the
    current time is newer than the expired time.
    """
    current_db_time = now()
    expired_nodes = Node.objects.filter(
        status__in=NODE_FAILURE_MONITORED_STATUS_TRANSITIONS.keys(),
        status_expires__isnull=False,
        status_expires__lte=current_db_time)
    for node in expired_nodes:
        comment = "Node operation '%s' timed out after %s minutes." % (
            NODE_STATUS_CHOICES_DICT[node.status],
            NODE_FAILURE_MONITORED_STATUS_TIMEOUTS[node.status],
            )
        node.mark_failed(
            comment=comment, script_result_status=SCRIPT_STATUS.TIMEDOUT)


def mark_nodes_failed_after_missing_script_timeout():
    """Check on the status of commissioning or testing nodes.

    For any node currently commissioning or testing check that a region is
    still receiving its heartbeat and no running script has gone past its
    run limit. If the node fails either condition its put into a failed status.
    """
    now = datetime.now()
    # maas-run-remote-scripts sends a heartbeat every two minutes. We allow
    # for a node to miss up to five heartbeats to account for network blips.
    heartbeat_expired = now - timedelta(minutes=(2 * 5))
    # Get the list of nodes currently running testing. status_expires is used
    # while the node is booting. Once MAAS receives the signal that testing
    # has begun it resets status_expires and checks for the heartbeat instead.
    qs = Node.objects.filter(
        status__in=[NODE_STATUS.COMMISSIONING, NODE_STATUS.TESTING],
        status_expires=None).prefetch_related(
            'current_commissioning_script_set', 'current_testing_script_set')
    for node in qs:
        if node.status == NODE_STATUS.COMMISSIONING:
            script_set = node.current_commissioning_script_set
        elif node.status == NODE_STATUS.TESTING:
            script_set = node.current_testing_script_set
        if script_set.last_ping < heartbeat_expired:
            node.mark_failed(
                comment='Node has missed the last 5 heartbeats',
                script_result_status=SCRIPT_STATUS.TIMEDOUT,
            )
            if not node.enable_ssh:
                node.stop(
                    comment=(
                        'Node stopped due to missing the last 5 heartbeats'),
                )
            continue

        # Check for scripts which have gone past their timeout.
        script_qs = script_set.scriptresult_set.filter(
            status=SCRIPT_STATUS.RUNNING).prefetch_related('script')
        for script_result in script_qs:
            if script_result.name in NODE_INFO_SCRIPTS:
                timeout = NODE_INFO_SCRIPTS[script_result.name]['timeout']
            elif (script_result.script is not None and
                    script_result.script.timeout.seconds > 0):
                timeout = script_result.script.timeout
            else:
                continue
            # Give tests an extra minute for cleanup and signaling done.
            # Most NODE_INFO_SCRIPTS have a 10s timeout with the assumption
            # that they'll get an extra minute here.
            script_expires = (
                script_result.started + timeout + timedelta(minutes=1))
            if script_expires < now:
                node.mark_failed(
                    comment="%s has run past it's timeout(%s)" % (
                        script_result.name, str(timeout)),
                    script_result_status=SCRIPT_STATUS.TIMEDOUT)
                if not node.enable_ssh:
                    node.stop(
                        comment=(
                            "Node stopped due to %s running past it's "
                            "timeout(%s)" % (script_result.name, str(timeout)))
                    )
                break


@synchronous
@transactional
def check_status():
    """Check the status_expires and script timeout on all nodes."""
    mark_nodes_failed_after_expiring()
    mark_nodes_failed_after_missing_script_timeout()


class StatusMonitorService(TimerService, object):
    """Service to periodically monitor node statues and mark them failed.

    This will run immediately when it's started, then once every 60 seconds,
    though the interval can be overridden by passing it to the constructor.
    """

    def __init__(self, interval=60):
        super(StatusMonitorService, self).__init__(
            interval, deferToDatabase, check_status)
