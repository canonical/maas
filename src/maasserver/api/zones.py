# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Zone`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'ZoneHandler',
    'ZonesHandler',
    ]

from django.shortcuts import get_object_or_404
from maasserver.api.support import (
    admin_method,
    OperationsHandler,
)
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms import ZoneForm
from maasserver.models import Zone
from maasserver.utils.orm import get_one
from piston3.utils import rc


class ZoneHandler(OperationsHandler):
    """Manage a physical zone.

    Any node is in a physical zone, or "zone" for short.  The meaning of a
    physical zone is up to you: it could identify e.g. a server rack, a
    network, or a data centre.  Users can then allocate nodes from specific
    physical zones, to suit their redundancy or performance requirements.

    This functionality is only available to administrators.  Other users can
    view physical zones, but not modify them.
    """
    api_doc_section_name = "Zone"
    model = Zone
    fields = ('name', 'description')

    # Creation happens on the ZonesHandler.
    create = None

    def read(self, request, name):
        """GET request.  Return zone.

        Returns 404 if the zone is not found.
        """
        return get_object_or_404(Zone, name=name)

    @admin_method
    def update(self, request, name):
        """PUT request.  Update zone.

        Returns 404 if the zone is not found.
        """
        zone = get_object_or_404(Zone, name=name)
        form = ZoneForm(instance=zone, data=request.data)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)
        return form.save()

    @admin_method
    def delete(self, request, name):
        """DELETE request.  Delete zone.

        Returns 404 if the zone is not found.
        Returns 204 if the zone is successfully deleted.
        """
        zone = get_one(Zone.objects.filter(name=name))
        if zone is not None:
            zone.delete()
        return rc.DELETED

    @classmethod
    def resource_uri(cls, zone=None):
        # See the comment in NodeHandler.resource_uri.
        if zone is None:
            name = 'name'
        else:
            name = zone.name
        return ('zone_handler', (name, ))


class ZonesHandler(OperationsHandler):
    """Manage physical zones."""
    api_doc_section_name = "Zones"
    update = delete = None

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('zones_handler', [])

    @admin_method
    def create(self, request):
        """Create a new physical zone.

        :param name: Identifier-style name for the new zone.
        :type name: unicode
        :param description: Free-form description of the new zone.
        :type description: unicode
        """
        form = ZoneForm(request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def read(self, request):
        """List zones.

        Get a listing of all the physical zones.
        """
        return Zone.objects.all().order_by('name')
