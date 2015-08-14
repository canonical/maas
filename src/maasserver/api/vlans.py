# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `VLAN`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type

from django.shortcuts import get_object_or_404
from maasserver.api.support import OperationsHandler
from maasserver.enum import NODE_PERMISSION
from maasserver.models import (
    Fabric,
    VLAN,
)
from piston.utils import rc


DISPLAYED_VLAN_FIELDS = (
    'id',
    'name',
    'vid',
    'fabric',
)


class VlansHandler(OperationsHandler):
    """Manage VLANs on a fabric."""
    api_doc_section_name = "VLANs"
    create = update = delete = None
    fields = DISPLAYED_VLAN_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ('vlans_handler', ["fabric_id"])

    def read(self, request, fabric_id):
        """List all VLANs belonging to fabric.

        Returns 404 if the node is not found.
        """
        fabric = Fabric.objects.get_fabric_or_404(
            fabric_id, request.user, NODE_PERMISSION.VIEW)
        return fabric.vlan_set.all()


class VlanHandler(OperationsHandler):
    """Manage VLAN on a fabric."""
    api_doc_section_name = "VLAN"
    create = update = None
    model = VLAN
    fields = DISPLAYED_VLAN_FIELDS

    @classmethod
    def resource_uri(cls, vlan=None):
        # See the comment in NodeHandler.resource_uri.
        fabric_id = "fabric_id"
        vlan_id = "vlan_id"
        if vlan is not None:
            vlan_id = vlan.id
            fabric = vlan.fabric
            if fabric is not None:
                fabric_id = fabric.id
        return ('vlan_handler', (fabric_id, vlan_id))

    @classmethod
    def fabric(cls, vlan):
        """Return fabric name."""
        return vlan.fabric.name

    def read(self, request, fabric_id, vlan_id):
        """Read VLAN on fabric.

        Returns 404 if the fabric or VLAN is not found.
        """
        fabric = Fabric.objects.get_fabric_or_404(
            fabric_id, request.user, NODE_PERMISSION.VIEW)
        return get_object_or_404(VLAN, fabric=fabric, id=vlan_id)

    def delete(self, request, fabric_id, vlan_id):
        """Delete VLAN on fabric.

        Returns 404 if the node or interface is not found.
        """
        fabric = Fabric.objects.get_fabric_or_404(
            fabric_id, request.user, NODE_PERMISSION.ADMIN)
        vlan = get_object_or_404(VLAN, fabric=fabric, id=vlan_id)
        vlan.delete()
        return rc.DELETED
