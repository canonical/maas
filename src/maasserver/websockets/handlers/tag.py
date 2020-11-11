# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The tag handler for the WebSocket connection."""


from maasserver.models.tag import Tag
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)


class TagHandler(TimestampedModelHandler):
    class Meta:
        queryset = Tag.objects.all()
        pk = "id"
        allowed_methods = ["list", "get"]
        listen_channels = ["tag"]
