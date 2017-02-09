# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The IPRange handler for the WebSocket connection."""

__all__ = [
    "IPRangeHandler",
    ]

from maasserver.forms.iprange import IPRangeForm
from maasserver.models import IPRange
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)
from provisioningserver.logger import get_maas_logger


maaslog = get_maas_logger("websockets.iprange")


class IPRangeHandler(TimestampedModelHandler):

    class Meta:
        queryset = IPRange.objects.all().select_related('user')
        pk = 'id'
        form = IPRangeForm
        allowed_methods = [
            'list',
            'get',
            'create',
            'update',
            'delete',
        ]
        listen_channels = [
            "iprange",
        ]

    def dehydrate(self, obj, data, for_list=False):
        """Add extra fields to `data`."""
        if obj.user is None:
            data["user_username"] = ""
        else:
            data["user_username"] = obj.user.username
        return data
