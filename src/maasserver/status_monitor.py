# Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Status monitoring service."""


from datetime import timedelta

from django.db.models import Prefetch
from twisted.application.internet import TimerService

from maasserver.enum import NODE_STATUS, NODE_STATUS_CHOICES_DICT
from maasserver.models import Script, ScriptResult, ScriptSet
from maasserver.models.config import Config
from maasserver.models.node import Node
from maasserver.models.timestampedmodel import now
from maasserver.node_status import get_node_timeout, MONITORED_STATUSES
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from metadataserver.enum import SCRIPT_STATUS
from provisioningserver.logger import get_maas_logger
from provisioningserver.refresh.node_info_scripts import NODE_INFO_SCRIPTS
from provisioningserver.utils.twisted import synchronous

maaslog = get_maas_logger("node")


def mark_nodes_failed_after_expiring(now, node_timeout):
    """Mark all nodes in that database as failed where the status did not
    transition in time. `status_expires` is checked on the node to see if the
    current time is newer than the expired time.
    """
    expired_nodes = Node.objects.filter(
        status__in=MONITORED_STATUSES,
        status_expires__isnull=False,
        status_expires__lte=now,
    )
    for node in expired_nodes:
        minutes = get_node_timeout(node.status, node_timeout)
        maaslog.info(
            "%s: Operation '%s' timed out after %s minutes."
            % (node.hostname, NODE_STATUS_CHOICES_DICT[node.status], minutes)
        )
        node.mark_failed(
            comment="Node operation '%s' timed out after %s minutes."
            % (NODE_STATUS_CHOICES_DICT[node.status], minutes),
            script_result_status=SCRIPT_STATUS.ABORTED,
        )


def mark_nodes_failed_after_missing_script_timeout(now, node_timeout):
    """Check on the status of commissioning or testing nodes.

    For any node currently commissioning or testing check that a region is
    still receiving its heartbeat and no running script has gone past its
    run limit. If the node fails either condition its put into a failed status.
    """
    # maas-run-remote-scripts sends a heartbeat every two minutes. If we
    # haven't received a heartbeat within node_timeout(20 min by default)
    # it's dead.
    heartbeat_expired = now - timedelta(minutes=node_timeout)
    # Get the list of nodes currently running testing. status_expires is used
    # while the node is booting. Once MAAS receives the signal that testing
    # has begun it resets status_expires and checks for the heartbeat instead.
    qs = Node.objects.filter(
        status__in=[NODE_STATUS.COMMISSIONING, NODE_STATUS.TESTING],
        status_expires=None,
    )
    qs = qs.prefetch_related(
        Prefetch(
            "current_commissioning_script_set",
            ScriptSet.objects.prefetch_related(
                Prefetch(
                    "scriptresult_set",
                    ScriptResult.objects.defer(
                        "output", "stdout", "stderr", "result"
                    ).prefetch_related(
                        Prefetch(
                            "script",
                            Script.objects.only(
                                "script_type", "name", "may_reboot", "timeout"
                            ),
                        )
                    ),
                )
            ),
        ),
        Prefetch(
            "current_testing_script_set",
            ScriptSet.objects.prefetch_related(
                Prefetch(
                    "scriptresult_set",
                    ScriptResult.objects.defer(
                        "output", "stdout", "stderr", "result"
                    ).prefetch_related(
                        Prefetch(
                            "script",
                            Script.objects.only(
                                "script_type", "name", "may_reboot", "timeout"
                            ),
                        )
                    ),
                )
            ),
        ),
    )
    for node in qs:
        if node.status == NODE_STATUS.COMMISSIONING:
            script_set = node.current_commissioning_script_set
        elif node.status == NODE_STATUS.TESTING:
            script_set = node.current_testing_script_set
        script_results = [
            script_result
            for script_result in script_set
            if script_result.status == SCRIPT_STATUS.RUNNING
        ]
        maybe_rebooting = False
        for script_result in script_results:
            if script_result.script and script_result.script.may_reboot:
                maybe_rebooting = True
                break
        flatlined = (
            script_set.last_ping is not None
            and script_set.last_ping < heartbeat_expired
        )
        if maybe_rebooting and flatlined:
            # If the script currently running may_reboot and the nodes
            # heartbeat has flatlined assume the node is rebooting. Set the
            # node.status_expires time to the boot timeout minus what has
            # already passed.
            minutes = get_node_timeout(node.status, node_timeout)
            node.status_expires = (
                now - (now - script_set.last_ping) + timedelta(minutes=minutes)
            )
            node.save(update_fields=["status_expires"])
            continue
        elif flatlined:
            maaslog.info(
                "%s: Has not been heard from for the last %s minutes"
                % (node.hostname, node_timeout)
            )
            node.mark_failed(
                comment=(
                    "Node has not been heard from for the last %s minutes"
                    % node_timeout
                ),
                script_result_status=SCRIPT_STATUS.TIMEDOUT,
            )
            if not node.enable_ssh:
                maaslog.info(
                    "%s: Stopped because SSH is disabled" % node.hostname
                )
                node.stop(comment="Node stopped because SSH is disabled")
            continue

        # Check for scripts which have gone past their timeout.
        for script_result in script_results:
            timeout = None
            for param in script_result.parameters.values():
                if param.get("type") == "runtime":
                    timeout = param.get("value")
                    break
            if (
                timeout is None
                and script_result.name in NODE_INFO_SCRIPTS
                and "timeout" in NODE_INFO_SCRIPTS[script_result.name]
            ):
                timeout = NODE_INFO_SCRIPTS[script_result.name]["timeout"]
            elif (
                timeout is None
                and script_result.script is not None
                and script_result.script.timeout.seconds > 0
            ):
                timeout = script_result.script.timeout
            else:
                continue
            # The node running the scripts checks if the script has run past
            # its time limit. The node will try to kill the script and move on
            # by signaling the region. If after 5 minutes past the timeout the
            # region hasn't received the signal mark_failed and stop the node.
            script_expires = (
                script_result.started + timeout + timedelta(minutes=5)
            )
            if script_expires < now:
                script_result.status = SCRIPT_STATUS.TIMEDOUT
                script_result.save(update_fields=["status"])
                maaslog.info(
                    "%s: %s has run past it's timeout(%s)"
                    % (node.hostname, script_result.name, str(timeout))
                )
                node.mark_failed(
                    comment="%s has run past it's timeout(%s)"
                    % (script_result.name, str(timeout)),
                    script_result_status=SCRIPT_STATUS.ABORTED,
                )
                if not node.enable_ssh:
                    maaslog.info(
                        "%s: Stopped because SSH is disabled" % node.hostname
                    )
                    node.stop(comment="Node stopped because SSH is disabled")
                break


@synchronous
@transactional
def check_status():
    """Check the status_expires and script timeout on all nodes."""
    current_time = now()
    node_timeout = Config.objects.get_config("node_timeout")
    mark_nodes_failed_after_expiring(current_time, node_timeout)
    mark_nodes_failed_after_missing_script_timeout(current_time, node_timeout)


class StatusMonitorService(TimerService):
    """Service to periodically monitor node statues and mark them failed.

    This will run immediately when it's started, then once every 60 seconds,
    though the interval can be overridden by passing it to the constructor.
    """

    def __init__(self, interval=60):
        super().__init__(interval, deferToDatabase, check_status)
