# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.notification`."""

__all__ = []

from maasserver.models.notification import NotificationDismissal
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.base import dehydrate_datetime
from maasserver.websockets.handlers.notification import NotificationHandler
from testtools.matchers import (
    AfterPreprocessing,
    AllMatch,
    Equals,
    Is,
    MatchesDict,
    MatchesListwise,
    Not,
)


def MatchesRenderedNotification(ntfn):
    """Return a matcher for a rendered notification."""
    return MatchesDict({
        "id": Equals(ntfn.id),
        "ident": Is(None) if ntfn.ident is None else Equals(ntfn.ident),
        "user": Is(None) if ntfn.user_id is None else Equals(ntfn.user_id),
        "users": Is(ntfn.users),
        "admins": Is(ntfn.admins),
        "updated": Equals(dehydrate_datetime(ntfn.updated)),
        "created": Equals(dehydrate_datetime(ntfn.created)),
        "message": Equals(ntfn.render()),
    })


def HasBeenDismissedBy(user):
    """Has `user` dismissed the notification we're matching against?"""

    def dismissed_by_user(notification):
        return NotificationDismissal.objects.filter(
            notification=notification, user=user).exists()

    return AfterPreprocessing(dismissed_by_user, Is(True))


class TestNotificationHandler(MAASServerTestCase):
    """Tests for `NotificationHandler`."""

    def test_get(self):
        user = factory.make_User()
        handler = NotificationHandler(user, {})
        notification = factory.make_Notification(user=user)
        self.assertThat(
            handler.get({"id": notification.id}),
            MatchesRenderedNotification(notification))

    def test_list(self):
        user = factory.make_User()
        user2 = factory.make_User()
        handler = NotificationHandler(user, {})
        notifications = [
            factory.make_Notification(user=user),  # Will match.
            factory.make_Notification(user=user2),
            factory.make_Notification(users=True),  # Will match.
            factory.make_Notification(users=False),
            factory.make_Notification(admins=True),
            factory.make_Notification(admins=False),
        ]
        expected = [
            MatchesRenderedNotification(notifications[0]),
            MatchesRenderedNotification(notifications[2]),
        ]
        self.assertThat(
            handler.list({}), MatchesListwise(expected))

    def test_list_for_admin(self):
        admin = factory.make_admin()
        admin2 = factory.make_admin()
        handler = NotificationHandler(admin, {})
        notifications = [
            factory.make_Notification(user=admin),  # Will match.
            factory.make_Notification(user=admin2),
            factory.make_Notification(users=True),  # Will match.
            factory.make_Notification(users=False),
            factory.make_Notification(admins=True),  # Will match.
            factory.make_Notification(admins=False),
        ]
        expected = [
            MatchesRenderedNotification(notifications[0]),
            MatchesRenderedNotification(notifications[2]),
            MatchesRenderedNotification(notifications[4]),
        ]
        self.assertThat(
            handler.list({}), MatchesListwise(expected))

    def test_dismiss(self):
        user = factory.make_User()
        handler = NotificationHandler(user, {})
        notification = factory.make_Notification(user=user)
        self.assertThat(notification, Not(HasBeenDismissedBy(user)))
        handler.dismiss({"id": str(notification.id)})
        self.assertThat(notification, HasBeenDismissedBy(user))

    def test_dismiss_multiple(self):
        user = factory.make_User()
        handler = NotificationHandler(user, {})
        notifications = [
            factory.make_Notification(user=user),
            factory.make_Notification(users=True),
        ]
        self.assertThat(notifications, AllMatch(Not(HasBeenDismissedBy(user))))
        handler.dismiss({"id": [str(ntfn.id) for ntfn in notifications]})
        self.assertThat(notifications, AllMatch(HasBeenDismissedBy(user)))
