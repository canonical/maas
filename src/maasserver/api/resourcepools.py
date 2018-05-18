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
from maasserver.forms import ResourcePoolForm
from maasserver.models import ResourcePool


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
        return super().read(request, id=id)

    def update(self, request, id):
        """PUT request.  Update resource pool.

        Returns 404 if the resource pool is not found.
        """
        return super().update(request, id=id)

    def delete(self, request, id):
        """DELETE request.  Delete resource pool.

        Returns 404 if the resource pool is not found.
        Returns 204 if the resource pool is successfully deleted.
        """
        return super().delete(request, id=id)


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
