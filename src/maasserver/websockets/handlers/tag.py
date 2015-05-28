# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The tag handler for the WebSocket connection."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "TagHandler",
    ]

from maasserver.models.tag import Tag
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)


class TagHandler(TimestampedModelHandler):

    class Meta:
        queryset = Tag.objects.all()
        pk = 'id'
        allowed_methods = ['list', 'get']
        listen_channels = [
            "tag",
            ]
