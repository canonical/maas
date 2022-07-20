# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Fabric`."""

from piston3.utils import rc

from maasserver.api.support import admin_method, OperationsHandler
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms.fabric import FabricForm
from maasserver.models import Fabric
from maasserver.permissions import NodePermission
from maasserver.utils.orm import prefetch_queryset

DISPLAYED_FABRIC_FIELDS = ("id", "name", "class_type", "vlans")


FABRIC_PREFETCH = [
    "vlan_set__primary_rack",
    "vlan_set__secondary_rack",
    "vlan_set__space",
    "vlan_set__relay_vlan__fabric__vlan_set",
    "vlan_set__relay_vlan__primary_rack",
    "vlan_set__relay_vlan__secondary_rack",
    "vlan_set__relay_vlan__space",
]


class FabricsHandler(OperationsHandler):
    """Manage fabrics."""

    api_doc_section_name = "Fabrics"
    update = delete = None
    fields = DISPLAYED_FABRIC_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ("fabrics_handler", [])

    def read(self, request):
        """@description-title List fabrics
        @description List all fabrics.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a list of
        fabric objects.
        @success-example "success-json" [exkey=fabrics-read] placeholder text
        """
        return prefetch_queryset(Fabric.objects.all(), FABRIC_PREFETCH)

    @admin_method
    def create(self, request):
        """@description-title Create a fabric
        @description Create a fabric.

        @param (string) "name" [required=false] Name of the fabric.

        @param (string) "description" [required=false] Description of the
        fabric.

        @param (string) "class_type" [required=false] Class type of the fabric.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the new fabric
        object.
        @success-example "success-json" [exkey=fabrics-create] placeholder text
        """
        form = FabricForm(data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)


class FabricHandler(OperationsHandler):
    """Manage fabric."""

    api_doc_section_name = "Fabric"
    create = None
    model = Fabric
    fields = DISPLAYED_FABRIC_FIELDS

    @classmethod
    def resource_uri(cls, fabric=None):
        # See the comment in NodeHandler.resource_uri.
        fabric_id = "id"
        if fabric is not None:
            fabric_id = fabric.id
        return ("fabric_handler", (fabric_id,))

    @classmethod
    def name(cls, fabric):
        """Return the name of the fabric."""
        return fabric.get_name()

    @classmethod
    def vlans(cls, fabric):
        """Return VLANs within the specified fabric."""
        return fabric.vlan_set.all()

    def read(self, request, id):
        """@description-title Read a fabric
        @description Read a fabric with the given id.

        @param (int) "{id}" [required=true] A fabric id.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the requested
        fabric object.
        @success-example "success-json" [exkey=fabrics-read-by-id] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested fabric is not found.
        @error-example "not-found"
            No Fabric matches the given query.
        """
        return Fabric.objects.get_fabric_or_404(
            id, request.user, NodePermission.view
        )

    def update(self, request, id):
        """@description-title Update fabric
        @description Update a fabric with the given id.

        @param (int) "{id}" [required=true] A fabric id.

        @param (string) "name" [required=false] Name of the fabric.

        @param (string) "description" [required=false] Description of the
        fabric.

        @param (string) "class_type" [required=false] Class type of the fabric.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the updated
        fabric object.
        @success-example "success-json" [exkey=fabrics-update] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested fabric is not found.
        @error-example "not-found"
            No Fabric matches the given query.
        """
        fabric = Fabric.objects.get_fabric_or_404(
            id, request.user, NodePermission.admin
        )
        form = FabricForm(instance=fabric, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, id):
        """@description-title Delete a fabric
        @description Delete a fabric with the given id.

        @param (int) "{id}" [required=true] A fabric id.

        @success (http-status-code) "server-success" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested fabric is not found.
        @error-example "not-found"
            No Fabric matches the given query.
        """
        fabric = Fabric.objects.get_fabric_or_404(
            id, request.user, NodePermission.admin
        )
        fabric.delete()
        return rc.DELETED
