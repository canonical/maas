# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The IPRange handler for the WebSocket connection."""

__all__ = [
    "IPRangeHandler",
    ]

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
        allowed_methods = [
            'list',
            'get',
            'delete',
        ]
        listen_channels = [
            "iprange",
        ]

    def dehydrate(self, obj, data, for_list=False):
        if obj.user is None:
            data['user'] = ""
        else:
            data['user'] = obj.user.username
        return data
