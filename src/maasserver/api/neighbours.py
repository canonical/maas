# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Neighbour`."""

__all__ = [
    'NeighbourHandler',
    'NeighboursHandler',
    ]

from maasserver.api.support import OperationsHandler
from maasserver.exceptions import MAASAPIForbidden
from maasserver.models import Neighbour
from piston3.utils import rc


DISPLAYED_NEIGHBOUR_FIELDS = (
    'id',
    'ip',
    'mac_address',
    'count',
    'time',
    'vid',
    'observer_interface_name',
    'observer_interface_id',
    'observer_system_id',
    'created',
    'updated',
)


class NeighbourHandler(OperationsHandler):
    """Read or delete an observed neighbour."""
    api_doc_section_name = "Neighbour"
    update = create = None
    fields = DISPLAYED_NEIGHBOUR_FIELDS
    model = Neighbour

    @classmethod
    def resource_uri(cls, neighbour=None):
        # See the comment in NodeHandler.resource_uri.
        neighbour_id = "neighbour_id"
        if neighbour is not None:
            neighbour_id = neighbour.id
        return ('neighbour_handler', (neighbour_id,))

    def read(self, request, **kwargs):
        neighbour_id = kwargs.get('neighbour_id', None)
        neighbour = Neighbour.objects.get_neighbour_or_404(neighbour_id)
        return neighbour

    def delete(self, request, neighbour_id):
        """Delete neighbour.

        Returns 403 if the neighbour could not be deleted.
        Returns 404 if the neighbour could not be found.
        """
        neighbour = Neighbour.objects.get_neighbour_or_404(neighbour_id)
        if not request.user.is_superuser:
            raise MAASAPIForbidden(
                "Unable to delete neighbour: permission denied.")
        neighbour.delete()
        return rc.DELETED


class NeighboursHandler(OperationsHandler):
    """Query observed neighbours."""
    api_doc_section_name = "Neighbours"
    create = update = delete = None

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('neighbours_handler', [])

    def read(self, request, **kwargs):
        return Neighbour.objects.get_by_updated_with_related_nodes()
