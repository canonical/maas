# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The notification handler for the WebSocket connection."""

__all__ = [
    "NotificationHandler",
]

from maasserver.models.notification import Notification
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)


class NotificationHandler(TimestampedModelHandler):

    class Meta:
        object_class = Notification
        allowed_methods = {'list', 'get', 'dismiss'}
        exclude = list_exclude = {"context"}

    def get_queryset(self):
        """Return `Notifications` for the current user."""
        return Notification.objects.find_for_user(self.user)

    def dehydrate(self, obj, data, for_list=False):
        data["message"] = obj.render()
        return data

    def dismiss(self, params):
        """Dismiss the given notification(s).

        :param id: One or more notification IDs to dismiss for the currently
            logged-in user.
        """
        data = self.preprocess_form("dismiss", params)
        ids = map(int, data.getlist("id"))
        notifications = self.get_queryset().filter(id__in=ids)
        for notification in notifications:
            notification.dismiss(self.user)
