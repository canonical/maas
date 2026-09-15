# Copyright 2015-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The space handler for the WebSocket connection."""

import itertools

from maasserver.authorization import can_edit_global_entities
from maasserver.forms.space import SpaceForm
from maasserver.models.space import Space
from maasserver.permissions import NodePermission
from maasserver.websockets.base import HandlerPermissionError
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)


class SpaceHandler(TimestampedModelHandler):
    class Meta:
        queryset = Space.objects.all().prefetch_related("vlan_set__subnet_set")
        pk = "id"
        form = SpaceForm
        form_requires_request = False
        allowed_methods = [
            "create",
            "update",
            "delete",
            "get",
            "list",
            "set_active",
        ]
        listen_channels = ["space"]
        view_permission = NodePermission.view

    def dehydrate(self, obj, data, for_list=False):
        data["name"] = obj.get_name()
        vlans = obj.vlan_set.all()
        data["vlan_ids"] = sorted(vlan.id for vlan in vlans)
        data["subnet_ids"] = sorted(
            itertools.chain(
                *[
                    [subnet.id for subnet in vlan.subnet_set.all()]
                    for vlan in vlans
                ]
            )
        )
        return data

    def create(self, parameters):
        """Create a space."""
        if not can_edit_global_entities(self.user):
            raise HandlerPermissionError()
        return super().create(parameters)

    def update(self, parameters):
        """Update this space."""
        if not can_edit_global_entities(self.user):
            raise HandlerPermissionError()
        return super().update(parameters)

    def delete(self, parameters):
        """Delete this Space."""
        space = self.get_object(parameters)
        assert self.user.has_perm(NodePermission.admin, space), (
            "Permission denied."
        )
        space.delete()
