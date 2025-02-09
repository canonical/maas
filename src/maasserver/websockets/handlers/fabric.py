# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The fabric handler for the WebSocket connection."""

from maasserver.forms.fabric import FabricForm
from maasserver.models.fabric import Fabric
from maasserver.permissions import NodePermission
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)


class FabricHandler(TimestampedModelHandler):
    class Meta:
        queryset = Fabric.objects.all().prefetch_related("vlan_set")
        pk = "id"
        form = FabricForm
        form_requires_request = False
        allowed_methods = [
            "list",
            "get",
            "create",
            "update",
            "delete",
            "set_active",
        ]
        listen_channels = ["fabric"]

    def dehydrate(self, obj, data, for_list=False):
        data["name"] = obj.get_name()
        # The default VLAN always has the lowest ID. We sort to place the
        # lowest ID first.
        data["vlan_ids"] = sorted(vlan.id for vlan in obj.vlan_set.all())
        # Pass the default vlan id explicitly, so that we don't reproduce the
        # logic in the javascript.
        data["default_vlan_id"] = data["vlan_ids"][0]
        return data

    def delete(self, parameters):
        """Delete this Domain."""
        domain = self.get_object(parameters)
        assert self.user.has_perm(NodePermission.admin, domain), (
            "Permission denied."
        )
        domain.delete()
