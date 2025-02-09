# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The nodes handler for the WebSocket connection."""

from maasserver.websockets.base import dehydrate_datetime, Handler


class TimestampedModelHandler(Handler):
    class Meta:
        abstract = True

    def __new__(cls, *args, **kwargs):
        cls = super().__new__(cls)
        if cls._meta.non_changeable is None:
            cls._meta.non_changeable = []
        for field in ["created", "updated"]:
            if field not in cls._meta.non_changeable:
                cls._meta.non_changeable.append(field)
        return cls

    def dehydrate_created(self, datetime):
        return dehydrate_datetime(datetime)

    def dehydrate_updated(self, datetime):
        return dehydrate_datetime(datetime)
