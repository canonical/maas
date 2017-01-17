# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Space`."""

from maasserver.api.support import (
    admin_method,
    OperationsHandler,
)
from maasserver.enum import NODE_PERMISSION
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms_space import SpaceForm
from maasserver.models import (
    Space,
    Subnet,
)
from piston3.utils import rc


DISPLAYED_SPACE_FIELDS = (
    'resource_uri',
    'id',
    'name',
    'vlans',
    'subnets',
)


class SpacesHandler(OperationsHandler):
    """Manage spaces."""
    api_doc_section_name = "Spaces"
    update = delete = None
    fields = DISPLAYED_SPACE_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ('spaces_handler', [])

    def read(self, request):
        """List all spaces."""
        return Space.objects.all()

    @admin_method
    def create(self, request):
        """Create a space.

        :param name: Name of the space.
        :param description: Description of the space.
        """
        form = SpaceForm(data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)


class SpaceHandler(OperationsHandler):
    """Manage space."""
    api_doc_section_name = "Space"
    create = None
    model = Space
    fields = DISPLAYED_SPACE_FIELDS

    @classmethod
    def resource_uri(cls, space=None):
        # See the comment in NodeHandler.resource_uri.
        space_id = "id"
        if space is not None:
            space_id = space.id
        return ('space_handler', (space_id,))

    @classmethod
    def name(cls, space):
        """Return the name of the space."""
        if space is None:
            return None
        return space.get_name()

    @classmethod
    def subnets(cls, space):
        return Subnet.objects.filter(vlan__space=space)

    @classmethod
    def vlans(cls, space):
        return space.vlan_set.all()

    def read(self, request, id):
        """Read space.

        Returns 404 if the space is not found.
        """
        return Space.objects.get_space_or_404(
            id, request.user, NODE_PERMISSION.VIEW)

    def update(self, request, id):
        """Update space.

        :param name: Name of the space.
        :param description: Description of the space.

        Returns 404 if the space is not found.
        """
        space = Space.objects.get_space_or_404(
            id, request.user, NODE_PERMISSION.ADMIN)
        form = SpaceForm(instance=space, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, id):
        """Delete space.

        Returns 404 if the space is not found.
        """
        space = Space.objects.get_space_or_404(
            id, request.user, NODE_PERMISSION.ADMIN)
        space.delete()
        return rc.DELETED
