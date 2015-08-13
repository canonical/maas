# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Fabric`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type

from maasserver.api.support import OperationsHandler
from maasserver.enum import NODE_PERMISSION
from maasserver.models import Fabric
from piston.utils import rc


DISPLAYED_FABRIC_FIELDS = (
    'id',
    'name',
    'vlans',
)


class FabricsHandler(OperationsHandler):
    """Manage fabrics."""
    api_doc_section_name = "Fabrics"
    create = update = delete = None
    fields = DISPLAYED_FABRIC_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ('fabrics_handler', [])

    def read(self, request):
        """List all fabrics."""
        return Fabric.objects.all()


class FabricHandler(OperationsHandler):
    """Manage fabric."""
    api_doc_section_name = "Fabric"
    create = update = None
    model = Fabric
    fields = DISPLAYED_FABRIC_FIELDS

    @classmethod
    def resource_uri(cls, fabric=None):
        # See the comment in NodeHandler.resource_uri.
        fabric_id = "fabric_id"
        if fabric is not None:
            fabric_id = fabric.id
        return ('fabric_handler', (fabric_id,))

    @classmethod
    def vlans(cls, fabric):
        """Return VLAN's in fabric."""
        return fabric.vlan_set.all()

    def read(self, request, fabric_id):
        """Read fabric.

        Returns 404 if the fabric is not found.
        """
        return Fabric.objects.get_fabric_or_404(
            fabric_id, request.user, NODE_PERMISSION.VIEW)

    def delete(self, request, fabric_id):
        """Delete fabric.

        Returns 404 if the fabric is not found.
        """
        fabric = Fabric.objects.get_fabric_or_404(
            fabric_id, request.user, NODE_PERMISSION.ADMIN)
        fabric.delete()
        return rc.DELETED
