# Copyright 2017-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The NodeResult handler for the WebSocket connection."""


from operator import attrgetter

from django.core.exceptions import ValidationError

from maasserver.models.node import Node
from maasserver.websockets.base import (
    dehydrate_datetime,
    HandlerDoesNotExistError,
    HandlerPKError,
)
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)
from metadataserver.enum import HARDWARE_TYPE
from metadataserver.models import ScriptResult


class NodeResultHandler(TimestampedModelHandler):
    class Meta:
        queryset = ScriptResult.objects.prefetch_related(
            "script", "script_set"
        ).defer(
            "output",
            "stdout",
            "stderr",
            "script__parameters",
            "script__packages",
            "script_set__tags",
        )
        pk = "id"
        allowed_methods = [
            "clear",
            "get",
            "get_result_data",
            "get_history",
            "list",
        ]
        listen_channels = ["scriptresult"]
        exclude = ["script_set", "script_name", "output", "stdout", "stderr"]
        list_fields = [
            "id",
            "updated",
            "script",
            "parameters",
            "physical_blockdevice",
            "interface",
            "script_version",
            "status",
            "exit_status",
            "started",
            "ended",
            "suppressed",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "system_ids" not in self.cache:
            self.cache["system_ids"] = {}

    def dehydrate_parameters(self, parameters):
        # Don't show password parameter values over the websocket.
        for parameter in parameters.values():
            if parameter.get("type") == "password" and "value" in parameter:
                parameter["value"] = "REDACTED"
        return parameters

    def dehydrate_started(self, started):
        return dehydrate_datetime(started)

    def dehydrate_ended(self, ended):
        return dehydrate_datetime(ended)

    def dehydrate(self, obj, data, for_list=False):
        """Add extra fields to `data`."""
        data["name"] = obj.name
        data["status_name"] = obj.status_name
        data["runtime"] = obj.runtime
        data["starttime"] = obj.starttime
        data["endtime"] = obj.endtime
        data["estimated_runtime"] = obj.estimated_runtime
        data["result_type"] = obj.script_set.result_type
        data["suppressed"] = obj.suppressed
        if obj.script is not None:
            data["hardware_type"] = obj.script.hardware_type
            data["tags"] = ", ".join(obj.script.tags)
        else:
            # Only builtin commissioning scripts don't have an associated
            # Script object.
            data["hardware_type"] = HARDWARE_TYPE.NODE
            data["tags"] = "commissioning"
        try:
            results = obj.read_results()
        except ValidationError as e:
            data["results"] = [
                {
                    "name": "error",
                    "title": "Error",
                    "description": "An error has occured while processing.",
                    "value": str(e),
                    "surfaced": True,
                }
            ]
        else:
            data["results"] = []
            for key, value in results.get("results", {}).items():
                if obj.script is not None:
                    if isinstance(obj.script.results, dict):
                        title = obj.script.results.get(key, {}).get(
                            "title", key
                        )
                        description = obj.script.results.get(key, {}).get(
                            "description", ""
                        )
                    # Only show surfaced results for builtin scripts. Result
                    # data from the user script is only shown in on the storage
                    # or test tabs.
                    surfaced = obj.script.default
                else:
                    # Only builtin commissioning scripts don't have an
                    # associated Script object. If MAAS ever includes result
                    # data in the builtin commissioning scripts show it.
                    title = key
                    description = ""
                    surfaced = True
                data["results"].append(
                    {
                        "name": key,
                        "title": title,
                        "description": description,
                        "value": value,
                        "surfaced": surfaced,
                    }
                )
        return data

    def get_node(self, params):
        """Get node object from params."""
        if "system_id" not in params:
            raise HandlerPKError("Missing system_id in params")
        system_id = params["system_id"]

        if system_id in self.cache["system_ids"]:
            return self.cache["system_ids"][system_id]

        try:
            node = Node.objects.get(system_id=params["system_id"])
        except Node.DoesNotExist:
            raise HandlerDoesNotExistError(
                f"Node with system id ({params['system_id']}) does not exist"
            )

        self.cache["system_ids"][system_id] = node
        return node

    def list(self, params):
        """List objects.

        :param system_id: `Node.system_id` for the script results.
        :param result_type: Only return results with this result type.
        :param hardware_type: Only return results with this hardware type.
        :param physical_blockdevice_id: Only return the results associated
           with the blockdevice_id.
        :param interface_id: Only return the results assoicated with the
           interface_id.
        :param has_surfaced: Only return results if they have surfaced.
        """
        node = self.get_node(params)
        queryset = node.get_latest_script_results.defer(
            "output",
            "stdout",
            "stderr",
            "script__parameters",
            "script__packages",
            "script_set__tags",
        )

        if "result_type" in params:
            queryset = queryset.filter(
                script_set__result_type=params["result_type"]
            )
        if "hardware_type" in params:
            queryset = queryset.filter(
                script__hardware_type=params["hardware_type"]
            )
        if "physical_blockdevice_id" in params:
            queryset = queryset.filter(
                physical_blockdevice_id=params["physical_blockdevice_id"]
            )
        if "interface_id" in params:
            queryset = queryset.filter(interface_id=params["interface_id"])
        if "has_surfaced" in params:
            if params["has_surfaced"]:
                queryset = queryset.exclude(result="")
        if "start" in params:
            queryset = queryset[params["start"] :]
        if "limit" in params:
            queryset = queryset[: params["limit"]]

        objs = list(queryset)
        getpk = attrgetter(self._meta.pk)
        self.cache["loaded_pks"].update(getpk(obj) for obj in objs)
        return [self.full_dehydrate(obj, for_list=True) for obj in objs]

    def get_result_data(self, params):
        """Return the raw script result data."""
        id = params.get("id")
        data_type = params.get("data_type", "combined")
        if data_type not in {"combined", "stdout", "stderr", "result"}:
            return "Unknown data_type %s" % data_type
        if data_type == "combined":
            data_type = "output"
        script_result = (
            ScriptResult.objects.filter(id=id)
            .only("status", data_type)
            .first()
        )
        if script_result is None:
            return "Unknown ScriptResult id %s" % id
        data = getattr(script_result, data_type)
        return data.decode().strip()

    def get_history(self, params):
        """Return a list of historic results."""
        id = params.get("id")
        script_result = (
            ScriptResult.objects.filter(id=id)
            .only(
                "status",
                "script_id",
                "script_set_id",
                "physical_blockdevice_id",
                "interface_id",
                "script_name",
            )
            .first()
        )
        history_qs = script_result.history.only(
            "id",
            "updated",
            "status",
            "started",
            "ended",
            "script_id",
            "script_name",
            "script_set_id",
            "physical_blockdevice_id",
            "interface_id",
            "suppressed",
        )
        return [
            {
                "id": history.id,
                "updated": dehydrate_datetime(history.updated),
                "status": history.status,
                "status_name": history.status_name,
                "runtime": history.runtime,
                "starttime": history.starttime,
                "endtime": history.endtime,
                "estimated_runtime": history.estimated_runtime,
                "suppressed": history.suppressed,
            }
            for history in history_qs
        ]

    def clear(self, params):
        """Clears the current node for events.

        Called by the client to inform the region it no longer cares
        about events for this node.
        """
        self.cache["system_ids"].pop(params.pop("system_id", None), None)
        return None

    def on_listen(self, channel, action, pk):
        """Called by the protocol when a channel notification occurs."""
        try:
            obj = self.listen(channel, action, pk)
        except HandlerDoesNotExistError:
            return None
        if obj is None:
            return None
        if obj.script_set.node.system_id not in self.cache["system_ids"]:
            # Notification is not for a node that is being listed,
            # do nothing with the notification.
            return None
        # Client is listening for events for this node, send the new event.
        return (
            self._meta.handler_name,
            action,
            self.full_dehydrate(obj, for_list=True),
        )
