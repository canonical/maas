# Copyright 2015-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `Notification`."""


import itertools
import random

from django.core.exceptions import ValidationError
from django.db.models.query import QuerySet

from maasserver.models.notification import (
    Notification,
    NotificationNotDismissable,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestNotificationManagerCreateMethods(MAASServerTestCase):
    """Tests for the `NotificationManager`'s create methods."""

    create_methods = tuple(
        (category, target, f"create_{category.lower()}_for_{target}")
        for category, target in itertools.product(
            ("error", "warning", "success", "info"),
            ("user", "users", "admins"),
        )
    )

    scenarios = tuple(
        (
            method_name,
            {
                "category": category,
                "method_name": method_name,
                "target_name": target_name,
                "targets_user": target_name == "user",
                "targets_users": target_name == "users",
                "targets_admins": target_name in {"users", "admins"},
            },
        )
        for category, target_name, method_name in create_methods
    )

    def makeNotification(self, *, ident=None, context=None):
        method = getattr(Notification.objects, self.method_name)
        message = factory.make_name("message")

        if self.targets_user:
            user = factory.make_User()
            notification = method(message, user, context=context, ident=ident)
        else:
            user = None
            notification = method(message, context=context, ident=ident)

        return notification

    def assertNotification(self, notification, *, ident):
        self.assertIs(notification.users, self.targets_users)
        self.assertIs(notification.admins, self.targets_admins)
        if self.targets_user:
            self.assertIsNotNone(notification.user)
        else:
            self.assertIsNone(notification.user)
        if ident is None:
            self.assertIsNone(notification.ident)
        else:
            self.assertEqual(notification.ident, ident)
        self.assertEqual(notification.category, self.category)

    def test_create_new_notification_without_context(self):
        notification = self.makeNotification()
        self.assertNotification(notification, ident=None)
        self.assertEqual({}, notification.context)

    def test_create_new_notification_with_context(self):
        context = {factory.make_name("key"): factory.make_name("value")}
        notification = self.makeNotification(context=context)
        self.assertNotification(notification, ident=None)
        self.assertEqual(context, notification.context)

    def test_create_new_notification_with_ident(self):
        ident = factory.make_name("ident")
        notification = self.makeNotification(ident=ident)
        self.assertNotification(notification, ident=ident)

    def test_create_new_notification_with_reused_ident(self):
        # A new notification is created, and the ident is moved.
        ident = factory.make_name("ident")
        n1 = self.makeNotification(ident=ident)
        n2 = self.makeNotification(ident=ident)
        n1.refresh_from_db()  # Get current value of `ident`.
        self.assertNotEqual(n1, n2)
        self.assertNotification(n1, ident=None)
        self.assertNotification(n2, ident=ident)
        self.assertEqual(Notification.objects.filter(ident=ident).count(), 1)


class TestFindingAndDismissingNotifications(MAASServerTestCase):
    """Tests for finding and dismissing notifications."""

    def notify(self, user):
        message = factory.make_name("message")
        return (
            Notification.objects.create_error_for_user(message, user),
            Notification.objects.create_error_for_users(message),
            Notification.objects.create_error_for_admins(message),
        )

    def assertNotifications(self, user, notifications):
        notification = Notification.objects.find_for_user(user)
        self.assertIsInstance(notification, QuerySet)  # Not RawQuerySet
        self.assertItemsEqual(notifications, notification)

    def test_find_and_dismiss_notifications_for_user(self):
        user = factory.make_User()
        n_for_user, n_for_users, n_for_admins = self.notify(user)
        self.assertNotifications(user, [n_for_user, n_for_users])
        n_for_user.dismiss(user)
        self.assertNotifications(user, [n_for_users])
        n_for_users.dismiss(user)
        self.assertNotifications(user, [])

    def test_find_and_dismiss_notifications_for_users(self):
        user = factory.make_User("user")
        user2 = factory.make_User("user2")
        n_for_user, n_for_users, n_for_admins = self.notify(user)
        self.assertNotifications(user, [n_for_user, n_for_users])
        self.assertNotifications(user2, [n_for_users])
        n_for_users.dismiss(user2)
        self.assertNotifications(user, [n_for_user, n_for_users])
        self.assertNotifications(user2, [])

    def test_find_and_dismiss_notifications_for_admins(self):
        user = factory.make_User("user")
        admin = factory.make_admin("admin")
        n_for_user, n_for_users, n_for_admins = self.notify(user)
        self.assertNotifications(user, [n_for_user, n_for_users])
        self.assertNotifications(admin, [n_for_users, n_for_admins])
        n_for_users.dismiss(admin)
        self.assertNotifications(user, [n_for_user, n_for_users])
        self.assertNotifications(admin, [n_for_admins])
        n_for_admins.dismiss(admin)
        self.assertNotifications(user, [n_for_user, n_for_users])
        self.assertNotifications(admin, [])

    def test_not_dismissable(self):
        notification = Notification(
            message="Some notification", dismissable=False
        )
        self.assertRaises(
            NotificationNotDismissable,
            notification.dismiss,
            factory.make_User(),
        )


class TestNotification(MAASServerTestCase):
    """Tests for the `Notification`."""

    def test_render_combines_message_with_context(self):
        thing_a = factory.make_name("a")
        thing_b = random.randrange(1000)
        message = "There are {b:d} of {a} in my suitcase."
        context = {"a": thing_a, "b": thing_b}
        notification = Notification(message=message, context=context)
        self.assertEqual(
            notification.render(),
            "There are "
            + str(thing_b)
            + " of "
            + thing_a
            + " in my suitcase.",
        )

    def test_render_allows_markup_in_message_but_escapes_context(self):
        message = "<foo>{bar}</foo>"
        context = {"bar": "<BAR>"}
        notification = Notification(message=message, context=context)
        self.assertEqual("<foo>&lt;BAR&gt;</foo>", notification.render())

    def test_save_checks_that_rendering_works(self):
        message = "Dude, where's my {thing}?"
        notification = Notification(message=message)
        error = self.assertRaises(ValidationError, notification.save)
        self.assertEqual(
            {"__all__": ["Notification cannot be rendered."]},
            error.message_dict,
        )
        self.assertIsNone(notification.id)
        self.assertFalse(Notification.objects.all().exists())

    def test_is_relevant_to_user(self):
        make_Notification = factory.make_Notification

        user = factory.make_User()
        user2 = factory.make_User()
        admin = factory.make_admin()

        def assertRelevance(notification, user, should_be_relevant: bool):
            # Ensure that is_relevant_to and find_for_user agree, i.e. if
            # is_relevant_to returns True, the notification is in the set
            # returned by find_for_user. Likewise, if is_relevant_to returns
            # False, the notification is not in the find_for_user set.
            self.assertEqual(
                notification.is_relevant_to(user), should_be_relevant
            )
            self.assertEqual(
                Notification.objects.find_for_user(user)
                .filter(id=notification.id)
                .exists(),
                should_be_relevant,
            )

        notification_to_user = make_Notification(user=user)
        assertRelevance(notification_to_user, None, False)
        assertRelevance(notification_to_user, user, True)
        assertRelevance(notification_to_user, user2, False)
        assertRelevance(notification_to_user, admin, False)

        notification_to_users = make_Notification(users=True)
        assertRelevance(notification_to_users, None, False)
        assertRelevance(notification_to_users, user, True)
        assertRelevance(notification_to_users, user2, True)
        assertRelevance(notification_to_users, admin, False)

        notification_to_admins = make_Notification(admins=True)
        assertRelevance(notification_to_admins, None, False)
        assertRelevance(notification_to_admins, user, False)
        assertRelevance(notification_to_admins, user2, False)
        assertRelevance(notification_to_admins, admin, True)

        notification_to_all = make_Notification(users=True, admins=True)
        assertRelevance(notification_to_all, None, False)
        assertRelevance(notification_to_all, user, True)
        assertRelevance(notification_to_all, user2, True)
        assertRelevance(notification_to_all, admin, True)


class TestNotificationRepresentation(MAASServerTestCase):
    """Tests for the `Notification` representation."""

    scenarios = tuple(
        (category, dict(category=category))
        for category in ("error", "warning", "success", "info")
    )

    def test_for_user(self):
        notification = Notification(
            user=factory.make_User("foobar"),
            message="The cat in the {place}",
            context=dict(place="bear trap"),
            category=self.category,
        )
        self.assertEqual(
            repr(notification),
            (
                f"<Notification {self.category.upper()} user='foobar' users=False admins=False "
                "'The cat in the bear trap'>"
            ),
        )

    def test_for_users(self):
        notification = Notification(
            users=True,
            message="The cat in the {place}",
            context=dict(place="blender"),
            category=self.category,
        )
        self.assertEqual(
            repr(notification),
            f"<Notification {self.category.upper()} user=None users=True admins=False 'The cat in the blender'>",
        )

    def test_for_admins(self):
        notification = Notification(
            admins=True,
            message="The cat in the {place}",
            context=dict(place="lava pit"),
            category=self.category,
        )
        self.assertEqual(
            repr(notification),
            f"<Notification {self.category.upper()} user=None users=False admins=True 'The cat in the lava pit'>",
        )
