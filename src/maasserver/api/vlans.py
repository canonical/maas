# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `VLAN`."""

from django.core.exceptions import PermissionDenied
from django.http import Http404
from piston3.utils import rc

from maasserver.api.support import OperationsHandler
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms.vlan import VLANForm
from maasserver.models import Fabric, Space, VLAN
from maasserver.permissions import NodePermission

DISPLAYED_VLAN_FIELDS = (
    "id",
    "name",
    "vid",
    "fabric",
    "fabric_id",
    "mtu",
    "primary_rack",
    "secondary_rack",
    "dhcp_on",
    "external_dhcp",
    "relay_vlan",
    "space",
)


class VlansHandler(OperationsHandler):
    """Manage VLANs on a fabric."""

    api_doc_section_name = "VLANs"
    update = delete = None
    fields = DISPLAYED_VLAN_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ("vlans_handler", ["fabric_id"])

    def read(self, request, fabric_id):
        """@description-title List VLANs
        @description List all VLANs belonging to given fabric.

        @param (int) "{fabric_id}" [required=true] The fabric for which to list
        the VLANs.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing a list of VLANs
        in the given fabric.
        @success-example "success-json" [exkey=vlan-list] placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested fabric_id is not found.
        @error-example "not-found"
            No Fabric matches the given query.
        """
        fabric = Fabric.objects.get_fabric_or_404(
            fabric_id, request.user, NodePermission.view
        )
        return fabric.vlan_set.all()

    def create(self, request, fabric_id):
        """@description-title Create a VLAN
        @description Creates a new VLAN.

        @param (int) "{fabric_id}" [required=true] The fabric_id on which to
        add the new VLAN.

        @param (string) "name" [required=false] Name of the VLAN.

        @param (string) "description" [required=false] Description of the new
        VLAN.

        @param (int) "vid" [required=true] VLAN ID of the new VLAN.

        @param (int) "mtu" [required=false] The MTU to use on the VLAN.

        @param (string) "space" [required=false] The space this VLAN should be
        placed in. Passing in an empty string (or the string 'undefined') will
        cause the VLAN to be placed in the 'undefined' space.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing information
        about the new VLAN.
        @success-example "success-json" [exkey=vlan-create] placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested fabric_id is not found.
        @error-example "not-found"
            No Fabric matches the given query.
        """
        fabric = Fabric.objects.get_fabric_or_404(
            fabric_id, request.user, NodePermission.admin
        )
        form = VLANForm(fabric=fabric, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)


class VlanHandler(OperationsHandler):
    """Manage a VLAN on a fabric."""

    api_doc_section_name = "VLAN"
    create = None
    model = VLAN
    fields = DISPLAYED_VLAN_FIELDS

    @classmethod
    def resource_uri(cls, *args):
        # See the comment in NodeHandler.resource_uri.
        if len(args) == 1 and isinstance(args[0], VLAN):
            # If a VLAN is passed in, resolve the URL directly to /vlans/<id>.
            return ("vlanid_handler", [args[0].id])
        else:
            # For context help, we want to document the user-friendly (two
            # parameter) way to access the VLAN API.
            return ("vlan_handler", ["fabric_id", "vid"])

    @classmethod
    def primary_rack(handler, vlan):
        if vlan.primary_rack:
            return vlan.primary_rack.system_id
        else:
            return None

    @classmethod
    def secondary_rack(handler, vlan):
        if vlan.secondary_rack:
            return vlan.secondary_rack.system_id
        else:
            return None

    @classmethod
    def space(handler, vlan):
        if vlan.space:
            return vlan.space.get_name()
        else:
            return Space.UNDEFINED

    @classmethod
    def fabric(cls, vlan):
        """Return fabric name."""
        return vlan.fabric.get_name()

    @classmethod
    def name(cls, vlan):
        """Return the VLAN name."""
        return vlan.get_name()

    def _get_vlan(self, user, permission, **kwargs):
        vlan_id = kwargs.get("vlan_id")
        vid = kwargs.get("vid")
        fabric_id = kwargs.get("fabric_id")
        if vlan_id is not None:
            # Accessing a specific VLAN by ID. First try getting the VLAN,
            # then check if the user has permission for its associated Fabric.
            try:
                vlan = VLAN.objects.get(id=vlan_id)
            except VLAN.DoesNotExist:
                raise Http404("VLAN with specified ID does not exist.")
            fabric = vlan.fabric
            if not user.has_perm(permission, fabric):
                raise PermissionDenied()
        elif fabric_id is not None and vid is not None:
            # User passed in a URL like /fabrics/<fabric_id>/vlans/<vid>.
            fabric = Fabric.objects.get_fabric_or_404(
                fabric_id, user, permission
            )
            vlan = VLAN.objects.get_object_by_specifiers_or_raise(
                vid, fabric=fabric
            )
        else:
            raise Http404("A vlan_id or (fabric_id, vid) pair is required.")
        return vlan

    def read(self, request, **kwargs):
        """@description-title Retrieve VLAN
        @description Retrieves a VLAN on a given fabric_id.

        @param (int) "{fabric_id}" [required=true] The fabric_id containing the
        VLAN.

        @param (int) "{vid}" [required=true] The VLAN ID.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing information
        about the requested VLAN.
        @success-example "success-json" [exkey=vlan-read] placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested fabric_id or vid is not
        found.
        @error-example "not-found"
            No Fabric matches the given query.
        """
        vlan = self._get_vlan(request.user, NodePermission.view, **kwargs)
        return vlan

    def update(self, request, **kwargs):
        """@description-title Update VLAN
        @description Updates a given VLAN.

        @param (int) "{fabric_id}" [required=true] Fabric ID containing the
        VLAN.

        @param (int) "{vid}" [required=true] VLAN ID of the VLAN.

        @param (string) "name" [required=false] Name of the VLAN.

        @param (string) "description" [required=false] Description of the VLAN.

        @param (int) "mtu" [required=false] The MTU to use on the VLAN.

        @param (boolean) "dhcp_on" [required=false] Whether or not DHCP should
        be managed on the VLAN.

        @param (string) "primary_rack" [required=false] The primary rack
        controller managing the VLAN (system_id).

        @param (string) "secondary_rack" [required=false] The secondary rack
        controller managing the VLAN (system_id).

        @param (int) "relay_vlan" [required=false] Relay VLAN ID. Only set when
        this VLAN will be using a DHCP relay to forward DHCP requests to
        another VLAN that MAAS is managing. MAAS will not run the DHCP relay
        itself, it must be configured to proxy reqests to the primary and/or
        secondary rack controller interfaces for the VLAN specified in this
        field.

        @param (string) "space" [required=false] The space this VLAN should be
        placed in. Passing in an empty string (or the string 'undefined') will
        cause the VLAN to be placed in the 'undefined' space.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing information
        about the updated VLAN.
        @success-example "success-json" [exkey=vlan-update] placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested fabric_id or vid is not
        found.
        @error-example "not-found"
            No Fabric matches the given query.
        """
        vlan = self._get_vlan(request.user, NodePermission.admin, **kwargs)
        data = {}
        # If the user passed in a space, make the undefined space name a
        # synonym for the empty space. But the Django request data object is
        # immutable, so we must first copy its contents into our own dict.
        for k, v in request.data.items():
            data[k] = v
        if "space" in data and data["space"] == Space.UNDEFINED:
            data["space"] = ""
        form = VLANForm(instance=vlan, data=data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, **kwargs):
        """@description-title Delete a VLAN
        @description Delete VLAN on a given fabric.

        @param (int) "{fabric_id}" [required=true] Fabric ID containing the
        VLAN to delete.

        @param (int) "{vid}" [required=true] VLAN ID of the VLAN to delete.

        @success (http-status-code) "204" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested fabric_id or vid is not
        found.
        @error-example "not-found"
            No Fabric matches the given query.
        """
        vlan = self._get_vlan(request.user, NodePermission.admin, **kwargs)
        vlan.delete()
        return rc.DELETED
