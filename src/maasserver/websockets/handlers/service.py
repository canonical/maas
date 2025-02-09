# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The Service handler for the WebSocket connection."""

from maasserver.models.service import Service
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)


class ServiceHandler(TimestampedModelHandler):
    class Meta:
        queryset = Service.objects.all()
        pk = "id"
        allowed_methods = ["list", "get", "set_active"]
        list_fields = ["id", "name", "status", "status_info"]
        listen_channels = ["service"]
