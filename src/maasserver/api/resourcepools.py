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
        """@description Returns a resource pool.
        @param (URI-string) "{id}" Required. A resource pool id/name.
        @param-example "{id}" mypool

        @success (HTTP-header) "server_success" 200 - A pseudo-JSON object
            containing the MAAS server's response
        @success-example "server_success"
            {
                ...
                'status': '200',
                ...
            }
        @success (Content) "content_success" A JSON object containing
            resource pool information
        @success-example "content_success"
            {
                "name": "default",
                "description": "Default pool",
                "id": 0,
                "resource_uri": "/MAAS/api/2.0/resourcepool/0/"
            }

        @error (HTTP-header) "404" 404 if the resource pool name is not found.
        @error-example "404"
            {
                ...
                'status': '404',
                ...
            }

        @error (Content) "notfound" The resource pool name is not found.
        @error-example "notfound"
            Not Found
        """
        return ResourcePool.objects.get_resource_pool_or_404(
            id, request.user, NODE_PERMISSION.VIEW)

    def update(self, request, id):
        """@description Updates a resource pool's name or description.

        Note that any other given parameters are silently ignored.

        @param (URI-string) "{id}" Required. The resource pool id/name to
            update.
        @param (string) "description" Optional. A brief description of the
            resource pool.
        @param (string) "name" Optional. The resource pool's new name.
        @param-example "{id}" myresourcepool
        @param-example "name" newname
        @param-example "description" An updated resource pool
            description.

        @success (HTTP-header) "serversuccess" 200 A pseudo-JSON object
            containing the MAAS server's response
        @success-example "serversuccess"
            {
                ...
                'status': '200',
                ...
            }
        @success (Content) "contentsuccess" A JSON object containing details
            about your new resource pool.
        @success-example "contentsuccess"
            {
                "name": "test-update-renamed",
                "description": "This is a new resource pool for updating.",
                "id": 80,
                "resource_uri": "/MAAS/api/2.0/resourcepool/80/"
            }

        @error (HTTP-header) "404" Zone not found
        @error-example "404"
            {
                ...
                'status': '404',
                ...
            }
        @error (Content) "notfound" Zone not found
        @error-example "notfound"
            Not Found
        """

        pool = ResourcePool.objects.get_resource_pool_or_404(
            id, request.user, NODE_PERMISSION.ADMIN)
        form = ResourcePoolForm(instance=pool, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, id):
        """@description Deletes a resource pool.

        @param (URI-string) "{id}" Required. The resource pool name/id to
            delete.
        @param-example "{id}" myresourcepool

        @success (HTTP-header) "serversuccess" 204 A pseudo-JSON object
            containing the MAAS server's response
        @success-example "serversuccess"
            {
                ...
                'status': '204',
                ...
            }
        @success (Content) "contentsuccess" An empty string
        @success-example "contentsuccess"
            <no content>

        @error (HTTP-header) "204" Always returns 204.
        @error-example "204"
            {
                ...
                'status': '204',
                ...
            }
        @error (Content) "notfound" An empty string
        @error-example "notfound"
            <no content>
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
        """@description Creates a new resource pool.
        @param (string) "name" Required. The new resource pool's name.
        @param (string) "description" Optional. A brief description of the
            new resource pool.
        @param-example "name" mynewresourcepool
        @param-example "description" mynewresourcepool is the name
            of my new resource pool.

        @success (HTTP-header) "serversuccess" 200 A pseudo-JSON object
            containing the MAAS server's response.
        @success-example "serversuccess"
            {
                ...
                'status': '200',
                ...
            }
        @success (Content) "contentsuccess" A JSON object containing details
            about your new resource pool.
        @success-example "contentsuccess"
            {
                "name": "test-W83ncaWh",
                "description": "This is a new resource pool.",
                "id": 82,
                "resource_uri": "/MAAS/api/2.0/resourcepool/82/"
            }

        @error (HTTP-header) "400" The resource pool already exists
        @error-example "400"
            {
                ...
                'status': '400',
                ...
            }
        @error (Content) "alreadyexists" The resource pool already exists
        @error-example "alreadyexists"
            {"name": ["Resource pool with this Name already exists."]}
        """
        return super().create(request)

    def read(self, request):
        """@description Get a listing of all resource pools.

        Note that there is always at least one resource pool: default.

        @success (HTTP-header) "serversuccess" 200 A pseudo-JSON object
            containing the MAAS server's response.
        @success-example "serversuccess"
            {
                ...
                'status': '200',
                ...
            }
        @success (Content) "contentsuccess" A JSON object containing a
            list of resource pools.
        @success-example "contentsuccess"
            [
                {
                    "name": "default",
                    "description": "Default pool",
                    "id": 0,
                    "resource_uri": "/MAAS/api/2.0/resourcepool/0/"
                }
            ]
        """
        return super().read(request)
