# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The PackageRepository handler for the WebSocket connection."""

__all__ = [
    "PackageRepositoryHandler",
    ]

from maasserver.forms_packagerepository import PackageRepositoryForm
from maasserver.models import PackageRepository
from maasserver.utils.orm import reload_object
from maasserver.websockets.base import HandlerPermissionError
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)


class PackageRepositoryHandler(TimestampedModelHandler):

    class Meta:
        queryset = PackageRepository.objects.all()
        pk = 'id'
        allowed_methods = [
            'list',
            'get',
            'create',
            'update',
            'delete',
        ]
        listen_channels = ['packagerepository']
        form = PackageRepositoryForm

    def create(self, params):
        """Create the object from params iff admin."""
        if not reload_object(self.user).is_superuser:
            raise HandlerPermissionError()
        return super().create(params)

    def update(self, params):
        """Update the object from params iff admin."""
        if not reload_object(self.user).is_superuser:
            raise HandlerPermissionError()
        return super().update(params)

    def delete(self, params):
        """Delete the object from params iff admin."""
        if not reload_object(self.user).is_superuser:
            raise HandlerPermissionError()
        return super().delete(params)
