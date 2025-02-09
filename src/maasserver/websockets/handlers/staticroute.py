# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The StaticRoute handler for the WebSocket connection."""

from maasserver.forms.staticroute import StaticRouteForm
from maasserver.models import StaticRoute
from maasserver.websockets.base import HandlerPermissionError
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
            raise HandlerPermissionError()
        return super().create(params)

    def update(self, params):
        """Update this static route."""
        if not self.user.is_superuser:
            raise HandlerPermissionError()
        return super().update(params)

    def delete(self, params):
        """Delete this static route."""
        if not self.user.is_superuser:
            raise HandlerPermissionError()
        return super().delete(params)
