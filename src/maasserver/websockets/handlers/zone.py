# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The zone handler for the WebSocket connection."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "ZoneHandler",
    ]

from maasserver.models.zone import Zone
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
    )


class ZoneHandler(TimestampedModelHandler):

    class Meta:
        queryset = Zone.objects.all()
        pk = 'id'
        allowed_methods = ['list', 'get', 'set_active']
        listen_channels = [
            "zone",
            ]
