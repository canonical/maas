# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The StaticRoute handler for the WebSocket connection."""


from django.core.exceptions import PermissionDenied

from maasserver.forms.staticroute import StaticRouteForm
from maasserver.models import StaticRoute
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)


class StaticRouteHandler(TimestampedModelHandler):
    class Meta:
        queryset = StaticRoute.objects.all()
        pk = "id"
        form = StaticRouteForm
        form_requires_request = False
        allowed_methods = ["list", "get", "create", "update", "delete"]
        listen_channels = ["staticroute"]

    def create(self, params):
        """Create a static route."""
        if not self.user.is_superuser:
            raise PermissionDenied()
        return super().create(params)

    def update(self, params):
        """Update this static route."""
        if not self.user.is_superuser:
            raise PermissionDenied()
        return super().update(params)

    def delete(self, params):
        """Delete this static route."""
        if not self.user.is_superuser:
            raise PermissionDenied()
        return super().delete(params)
