# Copyright 2015-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The event handler for the WebSocket connection."""

from maasserver.models.event import Event
from maasserver.models.eventtype import LOGGING_LEVELS
from maasserver.models.node import Node
from maasserver.websockets.base import HandlerDoesNotExistError, HandlerPKError
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)


def dehydrate_event_type_level(level):
    """Dehydrate the `EventType.level`."""
    return LOGGING_LEVELS[level].lower()


class EventHandler(TimestampedModelHandler):
    class Meta:
        queryset = Event.objects.all().select_related("type")
        pk = "id"
        allowed_methods = ["list", "clear"]
        exclude = ["node"]
        listen_channels = ["event"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "node_ids" not in self.cache:
            self.cache["node_ids"] = []

    def dehydrate_type(self, event_type):
        """Dehydrate the `EventType` on this event."""
        return {
            "level": dehydrate_event_type_level(event_type.level),
            "name": event_type.name,
            "description": event_type.description,
        }

    def dehydrate(self, obj, data, for_list=False):
        """Add extra fields to `data`."""
        data["node_id"] = obj.node_id
        return data

    def get_node(self, params):
        """Get node object from params"""
        if "node_id" not in params:
            raise HandlerPKError("Missing node_id in params")
        node_id = params["node_id"]
        try:
            node = Node.objects.get(id=node_id)
        except Node.DoesNotExist:
            raise HandlerDoesNotExistError(  # noqa: B904
                f"Node with id ({node_id}) does not exist"
            )
        return node

    def list(self, params):
        """List objects.

        :param system_id: `Node.system_id` for the events.
        :param offset: Offset into the queryset to return.
        :param limit: Maximum number of objects to return. Default is 1000.
        """
        node = self.get_node(params)
        self.cache["node_ids"].append(node.id)
        queryset = self.get_queryset(for_list=True)
        queryset = queryset.filter(node=node)
        queryset = queryset.order_by("-id")

        if "start" in params:
            queryset = queryset.filter(id__lt=params["start"])
        limit = params.get("limit", 1000)
        queryset = queryset[:limit]
        return [self.full_dehydrate(obj, for_list=True) for obj in queryset]

    def clear(self, params):
        """Clears the current node for events.

        Called by the client to inform the region it no longer cares
        about events for this node.
        """
        node = self.get_node(params)
        if node.id in self.cache["node_ids"]:
            self.cache["node_ids"].remove(node.id)
        return None

    def on_listen(self, channel, action, pk):
        """Called by the protocol when a channel notification occurs."""
        # Only care about create everything else is ignored.
        if action != "create":
            return None
        try:
            obj = self.listen(channel, action, pk)
        except HandlerDoesNotExistError:
            return None
        if obj is None:
            return None
        if obj.node_id not in self.cache["node_ids"]:
            # Notification is not for a node that is being listed,
            # do nothing with the notification.
            return None
        # Client is listening for events for this node, send the new event.
        return (
            self._meta.handler_name,
            action,
            self.full_dehydrate(obj, for_list=True),
        )
