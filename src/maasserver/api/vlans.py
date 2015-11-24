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

from django.core.exceptions import PermissionDenied
from django.http import Http404
from maasserver.api.support import OperationsHandler
from maasserver.enum import NODE_PERMISSION
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms_vlan import VLANForm
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
    'mtu',
)


class VlansHandler(OperationsHandler):
    """Manage VLANs on a fabric."""
    api_doc_section_name = "VLANs"
    update = delete = None
    fields = DISPLAYED_VLAN_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ('vlans_handler', ["fabric_id"])

    def read(self, request, fabric_id):
        """List all VLANs belonging to fabric.

        Returns 404 if the fabric is not found.
        """
        fabric = Fabric.objects.get_fabric_or_404(
            fabric_id, request.user, NODE_PERMISSION.VIEW)
        return fabric.vlan_set.all()

    def create(self, request, fabric_id):
        """Create a VLAN.

        :param name: Name of the VLAN.
        :param vid: VLAN ID of the VLAN.
        """
        fabric = Fabric.objects.get_fabric_or_404(
            fabric_id, request.user, NODE_PERMISSION.ADMIN)
        form = VLANForm(fabric=fabric, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)


class VlanHandler(OperationsHandler):
    """Manage VLAN on a fabric."""
    api_doc_section_name = "VLAN"
    create = update = None
    model = VLAN
    fields = DISPLAYED_VLAN_FIELDS

    @classmethod
    def resource_uri(cls, *args):
        # See the comment in NodeHandler.resource_uri.
        if len(args) == 1 and isinstance(args[0], VLAN):
            # If a VLAN is passed in, resolve the URL directly to /vlans/<id>.
            return ('vlanid_handler', [args[0].id])
        else:
            # For context help, we want to document the user-friendly (two
            # parameter) way to access the VLAN API.
            return ('vlan_handler', ["fabric_id", "vid"])

    @classmethod
    def fabric(cls, vlan):
        """Return fabric name."""
        return vlan.fabric.get_name()

    @classmethod
    def name(cls, vlan):
        """Return the VLAN name."""
        return vlan.get_name()

    def _get_vlan(self, user, permission, **kwargs):
        vlan_id = kwargs.get('vlan_id')
        vid = kwargs.get('vid')
        fabric_id = kwargs.get('fabric_id')
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
                fabric_id, user, permission)
            vlan = VLAN.objects.get_object_by_specifiers_or_raise(
                vid, fabric=fabric)
        else:
            raise Http404(
                "A vlan_id or (fabric_id, vid) pair is required.")
        return vlan

    def read(self, request, **kwargs):
        """Read VLAN on fabric.

        Returns 404 if the fabric or VLAN is not found.
        """
        vlan = self._get_vlan(request.user, NODE_PERMISSION.VIEW, **kwargs)
        return vlan

    def update(self, request, **kwargs):
        """Update VLAN.

        :param name: Name of the VLAN.
        :param vid: VLAN ID of the VLAN.

        Returns 404 if the fabric or VLAN is not found.
        """
        vlan = self._get_vlan(request.user, NODE_PERMISSION.ADMIN, **kwargs)
        form = VLANForm(instance=vlan, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, **kwargs):
        """Delete VLAN on fabric.

        Returns 404 if the fabric or VLAN is not found.
        """
        vlan = self._get_vlan(request.user, NODE_PERMISSION.ADMIN, **kwargs)
        vlan.delete()
        return rc.DELETED
