# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The NodeResult handler for the WebSocket connection."""

__all__ = [
    "NodeResultHandler",
    ]

from maasserver.models.node import Node
from maasserver.websockets.base import HandlerDoesNotExistError
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)
from metadataserver.models import ScriptResult


class NodeResultHandler(TimestampedModelHandler):

    class Meta:
        queryset = ScriptResult.objects.all()
        pk = 'id'
        allowed_methods = [
            'list',
            'get_result_data',
        ]
        listen_channels = ['scriptresult']
        exclude = [
            "output",
            "stdout",
            "stderr",
            "result",
        ]
        list_fields = [
            "id",
            "node_id",
            "script_set",
            "script",
            "parameters",
            "physical_blockdevice",
            "script_version",
            "status",
            "exit_status",
            "script_name",
            "started",
            "ended",
        ]

    def dehydrate(self, obj, data, for_list=False):
        """Add extra history list to `data`."""
        data["history_list"] = [
            {
                "id": history.id,
                "date": history.updated,
            } for history in obj.history
        ]
        return data

    def list(self, params):
        """List objects.

        :param system_id: `Node.system_id` for the script results.
        :param result_type: Only return results with this result type.
        :param hardware_type: Only return results with this hardware type.
        :param physical_blockdevice_id: Only return the results associated
           with the blockdevice_id.
        :param has_surfaced: Only return results if they have surfaced.
        """
        try:
            node = Node.objects.get(system_id=params["system_id"])
        except Node.DoesNotExist:
            raise HandlerDoesNotExistError(params["system_id"])
        queryset = node.get_latest_script_results

        if "result_type" in params:
            queryset = queryset.filter(
                script_set__result_type=params["result_type"])
        if "hardware_type" in params:
            queryset = queryset.filter(
                script__hardware_type=params["hardware_type"])
        if "physical_blockdevice_id" in params:
            queryset = queryset.filter(physical_blockdevice_id=params[
                "physical_blockdevice_id"])
        if "has_surfaced" in params:
            if params["has_surfaced"]:
                queryset = queryset.exclude(result='')

        return [
            self.full_dehydrate(obj, for_list=True)
            for obj in queryset
        ]

    def get_result_data(self, script_id, data_type):
        """Return the raw script result data."""
        script_result = ScriptResult.objects.get(script__id=script_id)
        if data_type == 'output':
            return script_result.output
        elif data_type == 'stdout':
            return script_result.stdout
        elif data_type == 'stderr':
            return script_result.stderr
        elif data_type == 'result':
            return script_result.result
