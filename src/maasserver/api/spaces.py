# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Space`."""

from django.db.models.query import QuerySet
from piston3.utils import rc

from maasserver.api.support import admin_method, OperationsHandler
from maasserver.exceptions import MAASAPIBadRequest, MAASAPIValidationError
from maasserver.forms.space import SpaceForm
from maasserver.models import Space, Subnet, VLAN
from maasserver.permissions import NodePermission

DISPLAYED_SPACE_FIELDS = ("resource_uri", "id", "name", "vlans", "subnets")


def _has_undefined_space():
    """Returns True if the undefined space contains at least one VLAN."""
    return VLAN.objects.filter(space__isnull=True).exists()


# Placeholder Space-like object for backward compatibility.
UNDEFINED_SPACE = Space(
    id=-1,
    name=Space.UNDEFINED,
    description="Backward compatibility object to ensure objects not "
    "associated with a space can be found.",
)

UNDEFINED_SPACE.save = None


class SpacesQuerySet(QuerySet):
    def __iter__(self):
        """Custom iterator which also includes a dummy "undefined" space."""
        yield from super().__iter__()
        # This space will be related to any VLANs and subnets not associated
        # with a space. (For backward compatibility with Juju 2.0.)
        if _has_undefined_space():
            yield UNDEFINED_SPACE


class SpacesHandler(OperationsHandler):
    """Manage spaces."""

    api_doc_section_name = "Spaces"
    update = delete = None
    fields = DISPLAYED_SPACE_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ("spaces_handler", [])

    def read(self, request):
        """@description-title List all spaces
        @description Generates a list of all spaces.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing a list of space
        objects.
        @success-example "success-json" [exkey=read-spaces] placeholder text
        """
        spaces_query = Space.objects.all()
        # The .all() method will return a QuerySet, but we need to coerce it to
        # a SpacesQuerySet to get our custom iterator. This must be an instance
        # of a QuerySet, or the API framework will return it as-is.
        spaces_query.__class__ = SpacesQuerySet
        return spaces_query

    @admin_method
    def create(self, request):
        """@description-title Create a space
        @description Create a new space.

        @param (string) "name" [required=true] The name of the new space.
        @param (string) "description" [required=false] A description of the new
        space.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing information
        about the new space.
        @success-example "success-json" [exkey=create] placeholder text

        @error (http-status-code) "400" 400
        @error (content) "already-exists" Space with this name already exists.
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
            if space.id == -1:
                space_id = Space.UNDEFINED
            else:
                space_id = space.id
        return ("space_handler", (space_id,))

    @classmethod
    def name(cls, space):
        """Return the name of the space."""
        if space is None:
            return None
        return space.get_name()

    @classmethod
    def subnets(cls, space):
        # Backward compatibility for Juju 2.0.
        if space.id == -1:
            return Subnet.objects.filter(vlan__space__isnull=True)
        return Subnet.objects.filter(vlan__space=space)

    @classmethod
    def vlans(cls, space):
        # Backward compatibility for Juju 2.0.
        if space.id == -1:
            return VLAN.objects.filter(space__isnull=True)
        return space.vlan_set.all()

    def read(self, request, id):
        """@description-title Reads a space
        @description Gets a space with the given ID.

        @param (int) "{id}" [required=true] The space's ID.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing information
        about the requested space.
        @success-example "success-json" [exkey=read-a-space] placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested space is not found.
        @error-example "not-found"
            No Space matches the given query.
        """
        # Backward compatibility for Juju 2.0. This is a special case to check
        # if the user requested to read the undefined space.
        if id == "-1" or id == Space.UNDEFINED and _has_undefined_space():
            return UNDEFINED_SPACE
        return Space.objects.get_space_or_404(
            id, request.user, NodePermission.view
        )

    def update(self, request, id):
        """@description-title Update space
        @description Updates a space with the given ID.

        @param (int) "{id}" [required=true] The space's ID.
        @param (string) "name" [required=true] The name of the new space.
        @param (string) "description" [required=false] A description of the new
        space.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing information
        about the updated space.
        @success-example "success-json" [exkey=update-a-space] placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested space is not found.
        @error-example "not-found"
            No Space matches the given query.
        """
        if id == "-1" or id == Space.UNDEFINED:
            raise MAASAPIBadRequest(
                "Space cannot be modified: %s" % Space.UNDEFINED
            )
        space = Space.objects.get_space_or_404(
            id, request.user, NodePermission.admin
        )
        form = SpaceForm(instance=space, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, id):
        """@description-title Delete a space
        @description Deletes a space with the given ID.

        @param (int) "{id}" [required=true] The space's ID.

        @success (http-status-code) "204" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested space is not found.
        @error-example "not-found"
            No Space matches the given query.
        """
        if id == "-1" or id == Space.UNDEFINED:
            raise MAASAPIBadRequest(
                "Space cannot be deleted: %s" % Space.UNDEFINED
            )
        space = Space.objects.get_space_or_404(
            id, request.user, NodePermission.admin
        )
        space.delete()
        return rc.DELETED
