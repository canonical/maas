# Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.notification`."""

from itertools import product
from operator import itemgetter
import random
from unittest.mock import sentinel

from testscenarios import multiply_scenarios

from maasserver.models.notification import (
    NotificationDismissal,
    NotificationNotDismissable,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.base import dehydrate_datetime, Handler
from maasserver.websockets.handlers.notification import NotificationHandler


def dismissed_by_user(notification, user):
    return NotificationDismissal.objects.filter(
        notification=notification, user=user
    ).exists()


def assertNotificationEqual(testcase, response, reference_notification):
    testcase.assertEqual(response["id"], reference_notification.id)
    if reference_notification.ident is None:
        testcase.assertIsNone(response["ident"])
    else:
        testcase.assertEqual(response["ident"], reference_notification.ident)
    if reference_notification.user_id is None:
        testcase.assertIsNone(response["user"])
    else:
        testcase.assertEqual(response["user"], reference_notification.user_id)
    testcase.assertIs(response["users"], reference_notification.users)
    testcase.assertIs(response["admins"], reference_notification.admins)
    testcase.assertEqual(
        response["updated"],
        dehydrate_datetime(reference_notification.updated),
    )
    testcase.assertEqual(
        response["created"],
        dehydrate_datetime(reference_notification.created),
    )
    testcase.assertEqual(response["message"], reference_notification.render())
    testcase.assertEqual(response["category"], reference_notification.category)
    testcase.assertEqual(
        response["dismissable"], reference_notification.dismissable
    )


class TestNotificationHandler(MAASServerTestCase):
    """Tests for `NotificationHandler`."""

    def test_get(self):
        user = factory.make_User()
        handler = NotificationHandler(user, {}, None)
        notification = factory.make_Notification(user=user)
        data = handler.get({"id": notification.id})
        assertNotificationEqual(self, data, notification)

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
        this_user_notification = notifications[0]
        all_users_notification = notifications[2]
        response = sorted(handler.list({}), key=itemgetter("id"))

        self.assertEqual(len(response), 2)
        (n1, n2) = response
        assertNotificationEqual(self, n1, this_user_notification)
        assertNotificationEqual(self, n2, all_users_notification)

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
        this_admin_notification = notifications[0]
        all_admins_notification = notifications[4]
        response = sorted(handler.list({}), key=itemgetter("id"))
        self.assertEqual(len(response), 2)
        (n1, n2) = response
        assertNotificationEqual(self, n1, this_admin_notification)
        assertNotificationEqual(self, n2, all_admins_notification)

    def test_dismiss(self):
        user = factory.make_User()
        handler = NotificationHandler(user, {}, None)
        notification = factory.make_Notification(user=user)
        self.assertFalse(dismissed_by_user(notification, user))
        handler.dismiss({"id": str(notification.id)})
        self.assertTrue(dismissed_by_user(notification, user))

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
        for notification in notifications:
            self.assertFalse(dismissed_by_user(notification, user))
        handler.dismiss({"id": [str(ntfn.id) for ntfn in notifications]})
        for notification in notifications:
            self.assertTrue(dismissed_by_user(notification, user))


class TestNotificationHandlerListening(MAASServerTestCase):
    """Tests for `NotificationHandler` listening to database messages."""

    def test_on_listen_for_notification_up_calls(self):
        super_on_listen = self.patch(Handler, "on_listen")
        super_on_listen.return_value = sentinel.on_listen

        user = factory.make_User()
        handler = NotificationHandler(user, {}, None)

        self.assertIs(
            handler.on_listen("notification", sentinel.action, sentinel.pk),
            sentinel.on_listen,
        )
        super_on_listen.assert_called_once_with(
            "notification", sentinel.action, sentinel.pk
        )

    def test_on_listen_for_dismissal_up_calls_with_delete(self):
        super_on_listen = self.patch(Handler, "on_listen")
        super_on_listen.return_value = sentinel.on_listen

        user = factory.make_User()
        handler = NotificationHandler(user, {}, None)
        notification = factory.make_Notification(user=user)

        # A dismissal notification from the database.
        dismissal = "%d:%d" % (notification.id, user.id)

        self.assertIs(
            handler.on_listen(
                "notificationdismissal", sentinel.action, dismissal
            ),
            sentinel.on_listen,
        )
        super_on_listen.assert_called_once_with(
            "notification", "delete", notification.id
        )

    def test_on_listen_for_dismissal_for_other_user_does_nothing(self):
        super_on_listen = self.patch(Handler, "on_listen")
        super_on_listen.return_value = sentinel.on_listen

        user = factory.make_User()
        handler = NotificationHandler(user, {}, None)
        notification = factory.make_Notification(user=user)

        # A dismissal notification from the database FOR ANOTHER USER.
        dismissal = "%d:%d" % (notification.id, random.randrange(1, 99999))

        self.assertIsNone(
            handler.on_listen(
                "notificationdismissal", sentinel.action, dismissal
            )
        )
        super_on_listen.assert_not_called()

    def test_on_listen_for_edited_notification_does_nothing(self):
        super_on_listen = self.patch(Handler, "on_listen")
        super_on_listen.return_value = sentinel.on_listen

        user = factory.make_User()
        handler = NotificationHandler(user, {}, None)
        notification = factory.make_Notification(user=user)
        notification.dismiss(user)

        self.assertIsNone(
            handler.on_listen("notification", "update", notification.id),
        )
        super_on_listen.assert_not_called()


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

        handler = NotificationHandler(user, {}, None)
        response = handler.on_listen("notification", "create", notification.id)
        if notification.is_relevant_to(user):
            handler_name, action, data = response
            self.assertEqual(handler_name, "notification")
            self.assertEqual(action, "create")
            assertNotificationEqual(self, data, notification)
        else:
            self.assertIsNone(response)
