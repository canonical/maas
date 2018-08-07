# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `ResourcePool`."""

__all__ = [
    'ResourcePoolHandler',
    'ResourcePoolsHandler',
]

from maasserver.api.support import (
    AnonymousOperationsHandler,
    ModelCollectionOperationsHandler,
    ModelOperationsHandler,
)
from maasserver.enum import NODE_PERMISSION
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms import ResourcePoolForm
from maasserver.models import ResourcePool
from piston3.utils import rc


DISPLAYED_RESOURCEPOOL_FIELDS = (
    'id',
    'name',
    'description',
)


class AnonResourcePoolHandler(AnonymousOperationsHandler):
    """Anonymous access to a resource pool."""
    read = create = update = delete = None
    model = ResourcePool
    fields = DISPLAYED_RESOURCEPOOL_FIELDS


class ResourcePoolHandler(ModelOperationsHandler):
    """Manage a resource pool."""

    model = ResourcePool
    fields = DISPLAYED_RESOURCEPOOL_FIELDS
    model_form = ResourcePoolForm
    handler_url_name = 'resourcepool_handler'
    api_doc_section_name = 'Resource pool'

    def read(self, request, id):
        """GET request.  Return resource pool.

        Returns 404 if the resource pool is not found.
        """
        return ResourcePool.objects.get_resource_pool_or_404(
            id, request.user, NODE_PERMISSION.VIEW)

    def update(self, request, id):
        """PUT request.  Update resource pool.

        Please see the documentation for the 'create' operation for detailed
        descriptions of each parameter.

        Optional parameters
        -------------------

        name
            Name of the resource pool.

        description
            Description of the resource pool.

        Returns 404 if the resource pool is not found.
        """

        pool = ResourcePool.objects.get_resource_pool_or_404(
            id, request.user, NODE_PERMISSION.ADMIN)
        form = ResourcePoolForm(instance=pool, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, id):
        """DELETE request.  Delete resource pool.

        Returns 404 if the resource pool is not found.
        Returns 204 if the resource pool is successfully deleted.
        """
        pool = ResourcePool.objects.get_resource_pool_or_404(
            id, request.user, NODE_PERMISSION.ADMIN)
        pool.delete()
        return rc.DELETED


class ResourcePoolsHandler(ModelCollectionOperationsHandler):
    """Manage resource pools."""

    model_manager = ResourcePool.objects
    fields = DISPLAYED_RESOURCEPOOL_FIELDS
    model_form = ResourcePoolForm
    handler_url_name = 'resourcepools_handler'
    api_doc_section_name = 'Resource pools'

    def create(self, request):
        """Create a new resource pool.

        :param name: Identifier-style name for the new resource pool.
        :type name: unicode
        :param description: Free-form description of the new resource pool.
        :type description: unicode
        """
        return super().create(request)

    def read(self, request):
        """List resource pools.

        Get a listing of all the resource pools.
        """
        return super().read(request)
