# Copyright 2017-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The Script handler for the WebSocket connection."""


from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)
from metadataserver.models import Script


class ScriptHandler(TimestampedModelHandler):
    class Meta:
        queryset = Script.objects.all()
        pk = "id"
        allowed_methods = ["list"]
        listen_channels = ["script"]
