# Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The switch handler for the WebSocket connection."""


from maasserver.exceptions import NodeActionError
from maasserver.models.node import Node
from maasserver.node_action import compile_node_actions
from maasserver.permissions import NodePermission
from maasserver.websockets.base import HandlerDoesNotExistError
from maasserver.websockets.handlers.machine import MachineHandler
from maasserver.websockets.handlers.node import node_prefetch, NodeHandler


class SwitchHandler(NodeHandler):
    class Meta(NodeHandler.Meta):
        abstract = False
        queryset = node_prefetch(
            Node.objects.filter(parent=None, switch__isnull=False)
        )
        allowed_methods = [
            "list",
            "get",
            "update",
            "action",
            "get_summary_xml",
            "get_summary_yaml",
        ]
        exclude = MachineHandler.Meta.exclude
        list_fields = MachineHandler.Meta.list_fields
        listen_channels = ["machine", "device", "controller", "switch"]

    def get_queryset(self, for_list=False):
        """Return `QuerySet` for devices only viewable by `user`."""
        # FIXME - Return a different query set when for_list is true. This
        # should contain only the items needed to display a switch when listing
        # in the UI.
        return Node.objects.get_nodes(
            self.user, NodePermission.view, from_nodes=self._meta.queryset
        )

    def get_object(self, params):
        """Get object by using the `pk` in `params`."""
        obj = super().get_object(params)
        if self.user.is_superuser or obj.owner == self.user:
            return obj
        raise HandlerDoesNotExistError(params[self._meta.pk])

    def action(self, params):
        """Perform the action on the object."""
        obj = self.get_object(params)
        action_name = params.get("action")
        actions = compile_node_actions(obj, self.user, request=self.request)
        action = actions.get(action_name)
        if action is None:
            raise NodeActionError(
                "%s action is not available for this device." % action_name
            )
        extra_params = params.get("extra", {})
        return action.execute(**extra_params)

    def on_listen(self, channel, action, pk):
        if channel != "switch" and action != "update":
            return None
        return super().on_listen(channel, action, pk)
