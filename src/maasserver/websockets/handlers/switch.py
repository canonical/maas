# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The switch handler for the WebSocket connection."""

__all__ = [
    "SwitchHandler",
    ]

from maasserver.enum import NODE_PERMISSION
from maasserver.exceptions import NodeActionError
from maasserver.models.node import Node
from maasserver.node_action import compile_node_actions
from maasserver.utils.orm import reload_object
from maasserver.websockets.base import HandlerDoesNotExistError
from maasserver.websockets.handlers.device import DeviceHandler
from maasserver.websockets.handlers.node import (
    node_prefetch,
    NodeHandler,
)
from provisioningserver.logger import get_maas_logger


maaslog = get_maas_logger("websockets.switch")


class SwitchHandler(NodeHandler):

    class Meta(NodeHandler.Meta):
        abstract = False
        queryset = node_prefetch(
            Node.objects.filter(
                parent=None,
                switch__isnull=False))
        allowed_methods = [
            'list',
            'get',
            'update',
            'action']
        exclude = DeviceHandler.Meta.exclude
        list_fields = [
            "id",
            "system_id",
            "hostname",
            "owner",
            "domain",
            "zone",
            "parent",
            "pxe_mac",
            ]
        # XXX: Which channel should we listen for?
        listen_channels = []

    def get_queryset(self):
        """Return `QuerySet` for devices only viewable by `user`."""
        return Node.objects.get_nodes(
            self.user, NODE_PERMISSION.VIEW, from_nodes=self._meta.queryset)

    def get_object(self, params):
        """Get object by using the `pk` in `params`."""
        obj = super(SwitchHandler, self).get_object(params)
        if reload_object(self.user).is_superuser or obj.owner == self.user:
            return obj
        raise HandlerDoesNotExistError(params[self._meta.pk])

    def action(self, params):
        """Perform the action on the object."""
        obj = self.get_object(params)
        action_name = params.get("action")
        actions = compile_node_actions(obj, self.user)
        action = actions.get(action_name)
        if action is None:
            raise NodeActionError(
                "%s action is not available for this device." % action_name)
        extra_params = params.get("extra", {})
        return action.execute(**extra_params)
