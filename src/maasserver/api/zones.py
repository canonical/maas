# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Zone`."""

from maasserver.api.support import (
    admin_method,
    AnonymousOperationsHandler,
    ModelCollectionOperationsHandler,
    ModelOperationsHandler,
)
from maasserver.forms import ZoneForm
from maasserver.models import Zone

DISPLAYED_ZONE_FIELDS = ("id", "name", "description")


class AnonZoneHandler(AnonymousOperationsHandler):
    """Anonymous access to zone."""

    read = create = update = delete = None
    model = Zone
    fields = DISPLAYED_ZONE_FIELDS


class ZoneHandler(ModelOperationsHandler):
    """
    Manage a physical zone.

    Any node is in a physical zone, or "zone" for short.  The meaning of a
    physical zone is up to you: it could identify e.g. a server rack, a
    network, or a data centre.  Users can then allocate nodes from specific
    physical zones, to suit their redundancy or performance requirements.

    This functionality is only available to administrators.  Other users can
    view physical zones, but not modify them.
    """

    model = Zone
    id_field = "name"
    fields = DISPLAYED_ZONE_FIELDS
    model_form = ZoneForm
    handler_url_name = "zone_handler"
    api_doc_section_name = "Zone"

    def read(self, request, name):
        """@description Returns a named zone.
        @param (url-string) "{name}" [required=true] A zone name
        @param-example "{name}" myzone

        @success (http-status-code) "server_success" 200
        @success (json) "content_success" A JSON object containing zone
            information
        @success-example "content_success"
            {
                "name": "default",
                "description": "",
                "id": 1,
                "resource_uri": "/MAAS/api/2.0/zones/default/"
            }

        @error (http-status-code) "404" 404
        @error (content) "notfound" The zone name is not found.
        @error-example "notfound"
            No Zone matches the given query.
        """
        return super().read(request, name=name)

    def update(self, request, name):
        """@description Updates a zone's name or description.

        Note that only 'name' and 'description' parameters are honored. Others,
        such as 'resource-uri' or 'id' will be ignored.

        @param (url-string) "{name}" [required=true] The zone to update.
        @param (string) "description" [required=false] A brief description of
            the new zone.
        @param (string) "name" [required=false] The zone's new name.
        @param-example "{name}" myzone
        @param-example "name" newname
        @param-example "description" An updated zone description.

        @success (http-status-code) "serversuccess" 200
        @success (json) "contentsuccess" A JSON object containing details
            about your new zone.
        @success-example "contentsuccess"
            {
                "name": "test-update-renamed",
                "description": "This is a new zone for updating.",
                "id": 151,
                "resource_uri": "/MAAS/api/2.0/zones/test-update-renamed/"
            }

        @error (http-status-code) "404" 404
        @error (content) "notfound" Zone not found
        @error-example "notfound"
            No Zone matches the given query.
        """
        return super().update(request, name=name)

    def delete(self, request, name):
        """@description Deletes a zone.

        @param (url-string) "{name}" [required=true] The zone to delete.
        @param-example "{name}" myzone

        @success (http-status-code) "serversuccess" 204
        @success (content) "contentsuccess" An empty string
        @success-example "contentsuccess"
            <no content>

        @error (http-status-code) "204" Always returns 204.
        @error (content) "notfound" An empty string
        @error-example "notfound"
            <no content>
        """
        return super().delete(request, name=name)


class ZonesHandler(ModelCollectionOperationsHandler):
    """Manage physical zones."""

    model_manager = Zone.objects
    fields = DISPLAYED_ZONE_FIELDS
    model_form = ZoneForm
    handler_url_name = "zones_handler"
    api_doc_section_name = "Zones"

    @admin_method
    def create(self, request):
        """@description Creates a new zone.
        @param (string) "name" [required=true] The new zone's name.
        @param (string) "description" [required=false] A brief description of
            the new zone.
        @param-example "name" mynewzone
        @param-example "description" mynewzone is the name of my
            new zone.

        @success (http-status-code) "serversuccess" 204
        @success (json) "contentsuccess" A JSON object containing details
            about your new zone.
        @success-example "contentsuccess"
            {
                "name": "test-hYnxCnjS",
                "description": "This is a new zone.",
                "id": 153,
                "resource_uri": "/MAAS/api/2.0/zones/test-hYnxCnjS/"
            }

        @error (http-status-code) "400" 400
        @error (content) "alreadyexists" The zone already exists
        @error-example "alreadyexists"
            {"name": ["Physical zone with this Name already exists."]}
        """
        return super().create(request)

    def read(self, request):
        """@description Get a listing of all zones. Note that there is always
        at least one zone: default.

        @success (http-status-code) "serversuccess" 200
        @success (json) "contentsuccess" A JSON object containing a list
        of zones.
        @success-example "contentsuccess"
            [
                {
                    "name": "default",
                    "description": "",
                    "id": 1,
                    "resource_uri": "/MAAS/api/2.0/zones/default/"
                },
                ...
            ]
        """
        return super().read(request)
