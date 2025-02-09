# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The SSLKey handler for the WebSocket connection."""

from django.core.exceptions import ValidationError
from django.http import HttpRequest

from maasserver.enum import ENDPOINT
from maasserver.forms import SSLKeyForm
from maasserver.models.sslkey import SSLKey
from maasserver.websockets.base import HandlerValidationError
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)


class SSLKeyHandler(TimestampedModelHandler):
    class Meta:
        queryset = SSLKey.objects.all()
        allowed_methods = ["list", "get", "create", "delete"]
        listen_channels = ["sslkey"]

    def get_queryset(self, for_list=False):
        """Return `QuerySet` for SSL keys owned by `user`."""
        return self._meta.queryset.filter(user=self.user)

    def get_object(self, params, permission=None):
        """Only allow getting keys owned by the user."""
        return super().get_own_object(params, permission=permission)

    def dehydrate(self, obj, data, for_list=False):
        """Add display to the SSL key."""
        data["display"] = obj.display_html()
        return data

    def create(self, params):
        """Create a SSLKey."""
        form = SSLKeyForm(user=self.user, data=params)
        if form.is_valid():
            try:
                request = HttpRequest()
                request.user = self.user
                request.data = params
                obj = form.save(ENDPOINT.UI, request)
            except ValidationError as e:
                try:
                    raise HandlerValidationError(e.message_dict)
                except AttributeError:
                    raise HandlerValidationError({"__all__": e.message})  # noqa: B904
            return self.full_dehydrate(obj)
        else:
            raise HandlerValidationError(form.errors)
