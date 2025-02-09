# Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The notification handler for the WebSocket connection."""

from maasserver.models.notification import Notification
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)


class NotificationHandler(TimestampedModelHandler):
    class Meta:
        object_class = Notification
        allowed_methods = {"list", "get", "dismiss", "create"}
        exclude = list_exclude = {"context"}
        listen_channels = {"notification", "notificationdismissal"}

    def get_queryset(self, for_list=False):
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

    def on_listen(self, channel, action, pk):
        """Intercept `on_listen` because dismissals must be handled specially.

        The docstring for `on_listen` suggests that handlers should override
        `listen` instead of `on_listen`. However, `Handler.on_listen` makes an
        assumption about notifications from the database that does not hold
        here: dismissals are notified as "$notification_id:$user_id" strings,
        not as simply "$notification_id".
        """
        if channel == "notification":
            if action == "update":
                if not self.get_queryset().filter(id=pk).exists():
                    # A notification that was already dismissed was updated.
                    return None
            return super().on_listen(channel, action, pk)
        elif channel == "notificationdismissal":
            pk, user_id = map(int, pk.split(":"))
            if self.user.id == user_id:
                # Send a dismissal as a delete of the notification.
                return super().on_listen("notification", "delete", pk)
            else:
                return None  # Not relevant to this user.
        else:
            return None  # Channel not recognised.

    def listen(self, channel, action, pk):
        """Only deal with notifications that are relevant to the user."""
        notification = super().listen(channel, action, pk)
        if notification.is_relevant_to(self.user):
            return notification
        else:
            return None
