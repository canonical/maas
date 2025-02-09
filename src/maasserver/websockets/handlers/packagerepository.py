# Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The PackageRepository handler for the WebSocket connection."""

from django.core.exceptions import ValidationError
from django.http import HttpRequest

from maasserver.enum import ENDPOINT
from maasserver.forms.packagerepository import PackageRepositoryForm
from maasserver.models import PackageRepository
from maasserver.websockets.base import (
    HandlerPermissionError,
    HandlerValidationError,
)
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)


class PackageRepositoryHandler(TimestampedModelHandler):
    class Meta:
        queryset = PackageRepository.objects.all()
        pk = "id"
        allowed_methods = ["list", "get", "create", "update", "delete"]
        listen_channels = ["packagerepository"]
        form = PackageRepositoryForm

    def create(self, params):
        """Create the object from params iff admin."""
        if not self.user.is_superuser:
            raise HandlerPermissionError()

        request = HttpRequest()
        request.user = self.user
        # Create by using form.
        form = PackageRepositoryForm(request=request, data=params)
        if form.is_valid():
            try:
                obj = form.save(ENDPOINT.UI, request)
            except ValidationError as e:
                try:
                    raise HandlerValidationError(e.message_dict)
                except AttributeError:
                    raise HandlerValidationError({"__all__": e.message})  # noqa: B904
            return self.full_dehydrate(obj)
        else:
            raise HandlerValidationError(form.errors)

    def update(self, params):
        """Update the object from params iff admin."""
        if not self.user.is_superuser:
            raise HandlerPermissionError()

        obj = self.get_object(params)
        request = HttpRequest()
        request.user = self.user
        # Update by using form.
        form = PackageRepositoryForm(
            instance=obj, request=request, data=params
        )
        if form.is_valid():
            try:
                obj = form.save(ENDPOINT.UI, request)
            except ValidationError as e:
                raise HandlerValidationError(e.error_dict)  # noqa: B904
            return self.full_dehydrate(obj)
        else:
            raise HandlerValidationError(form.errors)

    def delete(self, params):
        """Delete the object from params iff admin."""
        if not self.user.is_superuser:
            raise HandlerPermissionError()
        return super().delete(params)
