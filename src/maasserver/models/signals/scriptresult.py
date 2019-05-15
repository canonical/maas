# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Emit ScriptResult status transition event."""

__all__ = [
    "signals",
]

from maasserver.models import Event
from maasserver.utils.signals import SignalsManager
from metadataserver.enum import (
    RESULT_TYPE,
    SCRIPT_STATUS,
    SCRIPT_STATUS_CHOICES,
)
from metadataserver.models.scriptresult import ScriptResult
from provisioningserver.events import EVENT_TYPES


signals = SignalsManager()


def emit_script_result_status_transition_event(instance, old_values, **kwargs):
    """Send a status transition event."""
    script_result = instance
    [old_status] = old_values

    if (script_result.script_set.result_type == RESULT_TYPE.TESTING and
            old_status == SCRIPT_STATUS.PENDING and script_result.status in (
                SCRIPT_STATUS.INSTALLING, SCRIPT_STATUS.RUNNING)):
            storage_name = script_result.parameters.get(
                'storage', {}).get('value', {}).get('name')
            Event.objects.create_node_event(
                script_result.script_set.node, EVENT_TYPES.RUNNING_TEST,
                event_description="%s on %s" % (
                    script_result.name, storage_name) if storage_name else
                script_result.name)

    elif script_result.status in (
            SCRIPT_STATUS.FAILED, SCRIPT_STATUS.TIMEDOUT,
            SCRIPT_STATUS.ABORTED):
        Event.objects.create_node_event(
            script_result.script_set.node,
            EVENT_TYPES.SCRIPT_DID_NOT_COMPLETE,
            event_description="%s %s" % (
                script_result.name, SCRIPT_STATUS_CHOICES[
                    script_result.status][1].lower()))
    else:
        old_status_name = None
        new_status_name = None
        for status, status_name in SCRIPT_STATUS_CHOICES:
            if old_status == status:
                old_status_name = status_name
            elif script_result.status == status:
                new_status_name = status_name
        Event.objects.create_node_event(
            script_result.script_set.node,
            EVENT_TYPES.SCRIPT_RESULT_CHANGED_STATUS,
            event_description="%s changed status from '%s' to '%s'" % (
                script_result.name, old_status_name, new_status_name))
        if ('install.log' in script_result.name and not
                script_result.script_set.node.netboot):
            Event.objects.create_node_event(
                script_result.script_set.node, EVENT_TYPES.REBOOTING)


signals.watch_fields(
    emit_script_result_status_transition_event,
    ScriptResult, ['status'], delete=False)

# Enable all signals by default.
signals.enable()
