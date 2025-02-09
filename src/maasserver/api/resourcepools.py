# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `ResourcePool`."""

from piston3.utils import rc

from maasserver.api.support import (
    AnonymousOperationsHandler,
    ModelCollectionOperationsHandler,
    ModelOperationsHandler,
)
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms import ResourcePoolForm
from maasserver.models import ResourcePool
from maasserver.permissions import ResourcePoolPermission

DISPLAYED_RESOURCEPOOL_FIELDS = ("id", "name", "description")


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
    handler_url_name = "resourcepool_handler"
    api_doc_section_name = "Resource pool"
    permission_read = ResourcePoolPermission.view
    permission_edit = ResourcePoolPermission.edit
    permission_delete = ResourcePoolPermission.delete

    def read(self, request, id):
        """@description Returns a resource pool.
        @param (url-string) "{id}" [required=true] A resource pool id/name.
        @param-example "{id}" mypool

        @success (http-status-code) "server_success" 200
        @success (json) "content_success" A JSON object containing
            resource pool information
        @success-example "content_success"
            {
                "name": "default",
                "description": "Default pool",
                "id": 0,
                "resource_uri": "/MAAS/api/2.0/resourcepool/0/"
            }

        @error (http-status-code) "404" 404
        @error (content) "notfound" The resource pool name is not found.
        @error-example "notfound"
            No ResourcePool matches the given query.
        """
        return ResourcePool.objects.get_resource_pool_or_404(
            id, request.user, self.permission_read
        )

    def update(self, request, id):
        """@description Updates a resource pool's name or description.

        Note that any other given parameters are silently ignored.

        @param (url-string) "{id}" [required=true] The resource pool id/name to
            update.
        @param (string) "description" [required=false] A brief description of
            the resource pool.
        @param (string) "name" [required=false] The resource pool's new name.
        @param-example "{id}" myresourcepool
        @param-example "name" newname
        @param-example "description" An updated resource pool
            description.

        @success (http-status-code) "serversuccess" 200
        @success (json) "contentsuccess" A JSON object containing details
            about your new resource pool.
        @success-example "contentsuccess"
            {
                "name": "test-update-renamed",
                "description": "This is a new resource pool for updating.",
                "id": 80,
                "resource_uri": "/MAAS/api/2.0/resourcepool/80/"
            }

        @error (http-status-code) "404" 404
        @error (content) "notfound" Zone not found
        @error-example "notfound"
            No ResourcePool matches the given query.
        """
        pool = ResourcePool.objects.get_resource_pool_or_404(
            id, request.user, self.permission_edit
        )
        form = ResourcePoolForm(instance=pool, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, id):
        """@description Deletes a resource pool.

        @param (url-string) "{id}" [required=true] The resource pool name/id to
            delete.
        @param-example "{id}" myresourcepool

        @success (http-status-code) "serversuccess" 204
        @success (content) "contentsuccess" An empty string
        @success-example "contentsuccess"
            <no content>

        @error (http-status-code) "204" Always returns 204.
        @error (content) "notfound" An empty string
        @error-example "notfound"
            <no content>
        """
        pool = ResourcePool.objects.get_resource_pool_or_404(
            id, request.user, self.permission_delete
        )
        pool.delete()
        return rc.DELETED


class ResourcePoolsHandler(ModelCollectionOperationsHandler):
    """Manage resource pools."""

    model_manager = ResourcePool.objects
    fields = DISPLAYED_RESOURCEPOOL_FIELDS
    model_form = ResourcePoolForm
    handler_url_name = "resourcepools_handler"
    api_doc_section_name = "Resource pools"

    def create(self, request):
        """@description Creates a new resource pool.
        @param (string) "name" [required=true] The new resource pool's name.
        @param (string) "description" [required=false] A brief description of
            the new resource pool.
        @param-example "name" mynewresourcepool
        @param-example "description" mynewresourcepool is the name
            of my new resource pool.

        @success (http-status-code) "serversuccess" 200
        @success (json) "contentsuccess" A JSON object containing details
            about your new resource pool.
        @success-example "contentsuccess"
            {
                "name": "test-W83ncaWh",
                "description": "This is a new resource pool.",
                "id": 82,
                "resource_uri": "/MAAS/api/2.0/resourcepool/82/"
            }

        @error (http-status-code) "400" 400
        @error (content) "alreadyexists" The resource pool already exists
        @error-example "alreadyexists"
            {"name": ["Resource pool with this Name already exists."]}
        """
        return super().create(request)

    def read(self, request):
        """@description Get a listing of all resource pools.

        Note that there is always at least one resource pool: default.

        @success (http-status-code) "serversuccess" 200
        @success (json) "contentsuccess" A JSON object containing a
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
        return self.model_manager.get_resource_pools(request.user).order_by(
            self.order_field
        )
