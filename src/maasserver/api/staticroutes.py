# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `StaticRoute`."""

from maasserver.api.support import (
    admin_method,
    OperationsHandler,
)
from maasserver.enum import NODE_PERMISSION
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms_staticroute import StaticRouteForm
from maasserver.models import StaticRoute
from piston3.utils import rc


DISPLAYED_STATIC_ROUTE_FIELDS = (
    'id',
    'source',
    'destination',
    'gateway_ip',
    'metric',
)


class StaticRoutesHandler(OperationsHandler):
    """Manage static routes."""
    api_doc_section_name = "Static routes"
    update = delete = None
    fields = DISPLAYED_STATIC_ROUTE_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ('staticroutes_handler', [])

    def read(self, request):
        """List all static routes."""
        return StaticRoute.objects.all()

    @admin_method
    def create(self, request):
        """Create a static route.

        :param source: Source subnet for the route.
        :param destination: Destination subnet for the route.
        :param gateway_ip: IP address of the gateway on the source subnet.
        :param metric: Weight of the route on a deployed machine.
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
        return ('staticroute_handler', (staticroute_id,))

    def read(self, request, id):
        """Read static route.

        Returns 404 if the static route is not found.
        """
        return StaticRoute.objects.get_staticroute_or_404(
            id, request.user, NODE_PERMISSION.VIEW)

    def update(self, request, id):
        """Update static route.

        :param source: Source subnet for the route.
        :param destination: Destination subnet for the route.
        :param gateway_ip: IP address of the gateway on the source subnet.
        :param metric: Weight of the route on a deployed machine.

        Returns 404 if the static route is not found.
        """
        staticroute = StaticRoute.objects.get_staticroute_or_404(
            id, request.user, NODE_PERMISSION.ADMIN)
        form = StaticRouteForm(instance=staticroute, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, id):
        """Delete static route.

        Returns 404 if the static route is not found.
        """
        staticroute = StaticRoute.objects.get_staticroute_or_404(
            id, request.user, NODE_PERMISSION.ADMIN)
        staticroute.delete()
        return rc.DELETED
