# Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.notification`."""


from itertools import product
import random
from unittest.mock import sentinel

from testscenarios import multiply_scenarios
from testtools.matchers import (
    AfterPreprocessing,
    AllMatch,
    Equals,
    Is,
    IsInstance,
    MatchesAll,
    MatchesDict,
    MatchesListwise,
    Not,
)

from maasserver.models.notification import (
    NotificationDismissal,
    NotificationNotDismissable,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.base import dehydrate_datetime, Handler
from maasserver.websockets.handlers.notification import NotificationHandler
from maastesting.matchers import MockCalledOnceWith, MockNotCalled


def MatchesRenderedNotification(ntfn):
    """Return a matcher for a rendered notification."""
    return MatchesDict(
        {
            "id": Equals(ntfn.id),
            "ident": Is(None) if ntfn.ident is None else Equals(ntfn.ident),
            "user": Is(None) if ntfn.user_id is None else Equals(ntfn.user_id),
            "users": Is(ntfn.users),
            "admins": Is(ntfn.admins),
            "updated": Equals(dehydrate_datetime(ntfn.updated)),
            "created": Equals(dehydrate_datetime(ntfn.created)),
            "message": Equals(ntfn.render()),
            "category": Equals(ntfn.category),
            "dismissable": Equals(ntfn.dismissable),
        }
    )


def HasBeenDismissedBy(user):
    """Has `user` dismissed the notification we're matching against?"""

    def dismissed_by_user(notification):
        return NotificationDismissal.objects.filter(
            notification=notification, user=user
        ).exists()

    return AfterPreprocessing(dismissed_by_user, Is(True))


class TestNotificationHandler(MAASServerTestCase):
    """Tests for `NotificationHandler`."""

    def test_get(self):
        user = factory.make_User()
        handler = NotificationHandler(user, {}, None)
        notification = factory.make_Notification(user=user)
        self.assertThat(
            handler.get({"id": notification.id}),
            MatchesRenderedNotification(notification),
        )

    def test_list(self):
        user = factory.make_User()
        user2 = factory.make_User()
        handler = NotificationHandler(user, {}, None)
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
        self.assertThat(handler.list({}), MatchesListwise(expected))

    def test_list_for_admin(self):
        admin = factory.make_admin()
        admin2 = factory.make_admin()
        handler = NotificationHandler(admin, {}, None)
        notifications = [
            factory.make_Notification(user=admin),  # Will match.
            factory.make_Notification(user=admin2),
            factory.make_Notification(users=True),
            factory.make_Notification(users=False),
            factory.make_Notification(admins=True),  # Will match.
            factory.make_Notification(admins=False),
        ]
        expected = [
            MatchesRenderedNotification(notifications[0]),
            MatchesRenderedNotification(notifications[4]),
        ]
        self.assertThat(handler.list({}), MatchesListwise(expected))

    def test_dismiss(self):
        user = factory.make_User()
        handler = NotificationHandler(user, {}, None)
        notification = factory.make_Notification(user=user)
        self.assertThat(notification, Not(HasBeenDismissedBy(user)))
        handler.dismiss({"id": str(notification.id)})
        self.assertThat(notification, HasBeenDismissedBy(user))

    def test_not_dismissable(self):
        user = factory.make_User()
        handler = NotificationHandler(user, {}, None)
        notification = factory.make_Notification(user=user, dismissable=False)
        self.assertRaises(
            NotificationNotDismissable,
            handler.dismiss,
            {"id": str(notification.id)},
        )

    def test_dismiss_multiple(self):
        user = factory.make_User()
        handler = NotificationHandler(user, {}, None)
        notifications = [
            factory.make_Notification(user=user),
            factory.make_Notification(users=True),
        ]
        self.assertThat(notifications, AllMatch(Not(HasBeenDismissedBy(user))))
        handler.dismiss({"id": [str(ntfn.id) for ntfn in notifications]})
        self.assertThat(notifications, AllMatch(HasBeenDismissedBy(user)))


class TestNotificationHandlerListening(MAASServerTestCase):
    """Tests for `NotificationHandler` listening to database messages."""

    def test_on_listen_for_notification_up_calls(self):
        super_on_listen = self.patch(Handler, "on_listen")
        super_on_listen.return_value = sentinel.on_listen

        user = factory.make_User()
        handler = NotificationHandler(user, {}, None)

        self.assertThat(
            handler.on_listen("notification", sentinel.action, sentinel.pk),
            Is(sentinel.on_listen),
        )
        self.assertThat(
            super_on_listen,
            MockCalledOnceWith("notification", sentinel.action, sentinel.pk),
        )

    def test_on_listen_for_dismissal_up_calls_with_delete(self):
        super_on_listen = self.patch(Handler, "on_listen")
        super_on_listen.return_value = sentinel.on_listen

        user = factory.make_User()
        handler = NotificationHandler(user, {}, None)
        notification = factory.make_Notification(user=user)

        # A dismissal notification from the database.
        dismissal = "%d:%d" % (notification.id, user.id)

        self.assertThat(
            handler.on_listen(
                "notificationdismissal", sentinel.action, dismissal
            ),
            Is(sentinel.on_listen),
        )
        self.assertThat(
            super_on_listen,
            MockCalledOnceWith("notification", "delete", notification.id),
        )

    def test_on_listen_for_dismissal_for_other_user_does_nothing(self):
        super_on_listen = self.patch(Handler, "on_listen")
        super_on_listen.return_value = sentinel.on_listen

        user = factory.make_User()
        handler = NotificationHandler(user, {}, None)
        notification = factory.make_Notification(user=user)

        # A dismissal notification from the database FOR ANOTHER USER.
        dismissal = "%d:%d" % (notification.id, random.randrange(1, 99999))

        self.assertThat(
            handler.on_listen(
                "notificationdismissal", sentinel.action, dismissal
            ),
            Is(None),
        )
        self.assertThat(super_on_listen, MockNotCalled())

    def test_on_listen_for_edited_notification_does_nothing(self):
        super_on_listen = self.patch(Handler, "on_listen")
        super_on_listen.return_value = sentinel.on_listen

        user = factory.make_User()
        handler = NotificationHandler(user, {}, None)
        notification = factory.make_Notification(user=user)
        notification.dismiss(user)

        self.assertThat(
            handler.on_listen("notification", "update", notification.id),
            Is(None),
        )
        self.assertThat(super_on_listen, MockNotCalled())


class TestNotificationHandlerListeningScenarios(MAASServerTestCase):
    """Tests for `NotificationHandler` listening to database messages."""

    scenarios_users = (
        ("user", dict(make_user=factory.make_User)),
        ("admin", dict(make_user=factory.make_admin)),
    )

    scenarios_notifications = (
        (
            "to-user=%s;to-users=%s;to-admins=%s" % scenario,
            dict(zip(("to_user", "to_users", "to_admins"), scenario)),
        )
        for scenario in product(
            (False, True, "Other"),  # To specific user.
            (False, True),  # To all users.
            (False, True),  # To all admins.
        )
    )

    scenarios = multiply_scenarios(scenarios_users, scenarios_notifications)

    def test_on_listen(self):
        user = self.make_user()

        if self.to_user is False:
            to_user = None
        elif self.to_user is True:
            to_user = user
        else:
            to_user = factory.make_User()

        notification = factory.make_Notification(
            user=to_user, users=self.to_users, admins=self.to_admins
        )

        if notification.is_relevant_to(user):
            expected = MatchesAll(
                IsInstance(tuple),
                MatchesListwise(
                    (
                        Equals("notification"),
                        Equals("create"),
                        MatchesRenderedNotification(notification),
                    )
                ),
                first_only=True,
            )
        else:
            expected = Is(None)

        handler = NotificationHandler(user, {}, None)
        self.assertThat(
            handler.on_listen("notification", "create", notification.id),
            expected,
        )
