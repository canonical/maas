# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `StaticRoute`."""

from piston3.utils import rc

from maasserver.api.support import admin_method, OperationsHandler
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms.staticroute import StaticRouteForm
from maasserver.models import StaticRoute
from maasserver.permissions import NodePermission

DISPLAYED_STATIC_ROUTE_FIELDS = (
    "id",
    "source",
    "destination",
    "gateway_ip",
    "metric",
)


class StaticRoutesHandler(OperationsHandler):
    """Manage static routes."""

    api_doc_section_name = "Static routes"
    update = delete = None
    fields = DISPLAYED_STATIC_ROUTE_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ("staticroutes_handler", [])

    def read(self, request):
        """@description-title List static routes
        @description Lists all static routes.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing a list of
        static route objects.
        @success-example "success-json" [exkey=static-routes-read] placeholder
        text
        """
        return StaticRoute.objects.all()

    @admin_method
    def create(self, request):
        """@description-title Create a static route
        @description Creates a static route.

        @param (string) "source" [required=true] Source subnet name for the
        route.

        @param (string) "destination" [required=true] Destination subnet name
        for the route.

        @param (string) "gateway_ip" [required=true]  IP address of the
        gateway on the source subnet.

        @param (int) "metric" [required=false] Weight of the route on a
        deployed machine.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing information
        about the new static route object.
        @success-example "success-json" [exkey=static-routes-create]
        placeholder text
        """
        form = StaticRouteForm(data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)


class StaticRouteHandler(OperationsHandler):
    """Manage static route."""

    api_doc_section_name = "Static route"
    create = None
    model = StaticRoute
    fields = DISPLAYED_STATIC_ROUTE_FIELDS

    @classmethod
    def resource_uri(cls, staticroute=None):
        # See the comment in NodeHandler.resource_uri.
        staticroute_id = "id"
        if staticroute is not None:
            staticroute_id = staticroute.id
        return ("staticroute_handler", (staticroute_id,))

    def read(self, request, id):
        """@description-title Get a static route
        @description Gets a static route with the given ID.

        @param (int) "{id}" [required=true] A static-route ID.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing information
        about the requested static route.
        @success-example "success-json" [exkey=static-routes-read-by-id]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested static-route is not found.
        @error-example "not-found"
            No StaticRoute matches the given query.
        """
        return StaticRoute.objects.get_staticroute_or_404(
            id, request.user, NodePermission.view
        )

    def update(self, request, id):
        """@description-title Update a static route
        @description Updates a static route with the given ID.

        @param (int) "{id}" [required=true] A static-route ID.

        @param (string) "source" [required=false] Source subnet name for the
        route.

        @param (string) "destination" [required=false] Destination subnet name
        for the route.

        @param (string) "gateway_ip" [required=false]  IP address of the
        gateway on the source subnet.

        @param (int) "metric" [required=false] Weight of the route on a
        deployed machine.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing information
        about the updated static route object.
        @success-example "success-json" [exkey=static-routes-update]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested static-route is not found.
        @error-example "not-found"
            No StaticRoute matches the given query.
        """
        staticroute = StaticRoute.objects.get_staticroute_or_404(
            id, request.user, NodePermission.admin
        )
        form = StaticRouteForm(instance=staticroute, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, id):
        """@description-title Delete static route
        @description Deletes the static route with the given ID.

        @param (int) "{id}" [required=true] A static-route ID.

        @success (http-status-code) "204" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested static-route is not found.
        @error-example "not-found"
            No StaticRoute matches the given query.
        """
        staticroute = StaticRoute.objects.get_staticroute_or_404(
            id, request.user, NodePermission.admin
        )
        staticroute.delete()
        return rc.DELETED
