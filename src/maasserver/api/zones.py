# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Zone`."""

__all__ = [
    'ZoneHandler',
    'ZonesHandler',
]

from maasserver.api.support import (
    AnonymousOperationsHandler,
    ModelCollectionOperationsHandler,
    ModelOperationsHandler,
)
from maasserver.forms import ZoneForm
from maasserver.models import Zone


DISPLAYED_ZONE_FIELDS = (
    'id',
    'name',
    'description',
)


class AnonZoneHandler(AnonymousOperationsHandler):
    """Anonymous access to zone."""
    read = create = update = delete = None
    model = Zone
    fields = DISPLAYED_ZONE_FIELDS


class ZoneHandler(ModelOperationsHandler):
    """Manage a physical zone.

    Any node is in a physical zone, or "zone" for short.  The meaning of a
    physical zone is up to you: it could identify e.g. a server rack, a
    network, or a data centre.  Users can then allocate nodes from specific
    physical zones, to suit their redundancy or performance requirements.

    This functionality is only available to administrators.  Other users can
    view physical zones, but not modify them.
    """

    model = Zone
    id_field = 'name'
    fields = DISPLAYED_ZONE_FIELDS
    model_form = ZoneForm
    handler_url_name = 'zone_handler'
    api_doc_section_name = 'Zone'

    def read(self, request, name):
        """GET request.  Return zone.

        Returns 404 if the zone is not found.
        """
        return super().read(request, name=name)

    def update(self, request, name):
        """PUT request.  Update zone.

        Returns 404 if the zone is not found.
        """
        return super().update(request, name=name)

    def delete(self, request, name):
        """DELETE request.  Delete zone.

        Returns 404 if the zone is not found.
        Returns 204 if the zone is successfully deleted.
        """
        return super().delete(request, name=name)


class ZonesHandler(ModelCollectionOperationsHandler):
    """Manage physical zones."""

    model_manager = Zone.objects
    fields = DISPLAYED_ZONE_FIELDS
    model_form = ZoneForm
    handler_url_name = 'zones_handler'
    api_doc_section_name = 'Zones'

    def create(self, request):
        """Create a new physical zone.

        :param name: Identifier-style name for the new zone.
        :type name: unicode
        :param description: Free-form description of the new zone.
        :type description: unicode
        """
        return super().create(request)

    def read(self, request):
        """List zones.

        Get a listing of all the physical zones.
        """
        return super().read(request)
