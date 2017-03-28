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
from metadataserver.enum import SCRIPT_STATUS
from metadataserver.models import ScriptResult
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
        node.save(update_fields=['status_expires', 'status'])

        qs = ScriptResult.objects.filter(
            script_set__in=[
                node.current_commissioning_script_set,
                node.current_testing_script_set,
                node.current_installation_script_set,
            ],
            status__in=[SCRIPT_STATUS.PENDING, SCRIPT_STATUS.RUNNING])
        for script_result in qs:
            script_result.status = SCRIPT_STATUS.TIMEDOUT
            script_result.save(update_fields=['status'])


def fail_testing(node, reason):
    """Fail testing on a node due to a timeout.

    Set a node's status to FAILED_TESTING and log the reason for failing. If
    enable_ssh is False stop the node as well. Any tests currently pending or
    running are set to a TIMEDOUT status.
    """
    if not node.enable_ssh:
        node.stop(node.owner, comment=reason)

    node.status = NODE_STATUS.FAILED_TESTING
    node.error_description = reason
    node.save(update_fields=['status', 'error_description'])

    qs = node.current_testing_script_set.scriptresult_set.filter(
        status__in={SCRIPT_STATUS.PENDING, SCRIPT_STATUS.RUNNING})
    for script_result in qs:
        script_result.status = SCRIPT_STATUS.TIMEDOUT
        script_result.save(update_fields=['status'])


def mark_testing_nodes_failed_after_missing_timeout():
    """Check on the status of testing nodes.

    For any node currently testing check that a region is still receiving its
    heartbeat and no running script has gone past its run limit. If the node
    fails either condition its put into FAILED_TESTING status.
    """
    now = datetime.now()
    # maas-run-remote-scripts sends a heartbeat every two minutes. We allow
    # for a node to miss up to five heartbeats to account for network blips.
    heartbeat_expired = now - timedelta(minutes=(2 * 5))
    # Get the list of nodes currently running testing. status_expires is used
    # while the node is booting. Once MAAS receives the signal that testing
    # has begun it resets status_expires and checks for the heartbeat instead.
    qs = Node.objects.filter(
        status=NODE_STATUS.TESTING, status_expires=None).prefetch_related(
            'current_testing_script_set')
    for node in qs:
        if node.current_testing_script_set.last_ping < heartbeat_expired:
            fail_testing(node, 'Node has missed the last 5 heartbeats')
            continue

        # Check for scripts which have gone past their timeout.
        script_qs = node.current_testing_script_set.scriptresult_set.filter(
            status=SCRIPT_STATUS.RUNNING).prefetch_related('script')
        for script_result in script_qs:
            if (script_result.script is not None and
                    script_result.script.timeout.seconds == 0):
                continue
            # Give tests an extra minute for cleanup and signaling done.
            script_expires = (
                script_result.started + script_result.script.timeout +
                timedelta(minutes=1))
            if script_expires < now:
                fail_testing(
                    node, "%s has run past it's timeout(%s)" % (
                        script_result.name, str(script_result.script.timeout)))
                break


@synchronous
@transactional
def check_status():
    """Check the status_expires and test status on all nodes."""
    mark_nodes_failed_after_expiring()
    mark_testing_nodes_failed_after_missing_timeout()


class StatusMonitorService(TimerService, object):
    """Service to periodically monitor node statues and mark them failed.

    This will run immediately when it's started, then once every 60 seconds,
    though the interval can be overridden by passing it to the constructor.
    """

    def __init__(self, interval=60):
        super(StatusMonitorService, self).__init__(
            interval, deferToDatabase, check_status)
