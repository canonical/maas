# Copyright 2015-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `Notification`."""

__all__ = []

import random

from django.db.models.query import QuerySet
from maasserver.models.notification import Notification
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from testtools.matchers import (
    AfterPreprocessing,
    Equals,
    HasLength,
    Is,
    IsInstance,
    MatchesAll,
    MatchesStructure,
    Not,
)


class TestNotificationManager(MAASServerTestCase):
    """Tests for the `NotificationManager`."""

    def test_create_new_notification_for_user(self):
        user = factory.make_User()
        message = factory.make_name("message")
        notification = Notification.objects.create_for_user(message, user)
        self.assertThat(
            reload_object(notification), MatchesStructure(
                ident=Is(None), user=Equals(user), users=Is(False),
                admins=Is(False), message=Equals(message), context=Equals({}),
            ))

    def test_create_new_notification_for_user_with_ident(self):
        user = factory.make_User()
        ident = factory.make_name("ident")
        message = factory.make_name("message")
        notification = Notification.objects.create_for_user(
            message, user, ident=ident)
        self.assertThat(
            reload_object(notification), MatchesStructure(
                ident=Equals(ident), user=Equals(user), users=Is(False),
                admins=Is(False), message=Equals(message), context=Equals({}),
            ))

    def test_create_new_notification_for_user_with_reused_ident(self):
        # A new notification is created, and the ident is moved.
        user = factory.make_User()
        ident = factory.make_name("ident")
        message = factory.make_name("message")
        n1 = Notification.objects.create_for_user(message, user, ident=ident)
        n2 = Notification.objects.create_for_user(message, user, ident=ident)
        self.assertThat(n2, Not(Equals(n1)))
        self.assertThat(
            reload_object(n1), MatchesStructure(
                ident=Is(None), user=Equals(user), users=Is(False),
                admins=Is(False), message=Equals(message), context=Equals({}),
            ))
        self.assertThat(
            reload_object(n2), MatchesStructure(
                ident=Equals(ident), user=Equals(user), users=Is(False),
                admins=Is(False), message=Equals(message), context=Equals({}),
            ))
        self.assertThat(
            Notification.objects.filter(ident=ident),
            HasLength(1))

    def test_create_new_notification_for_users(self):
        message = factory.make_name("message")
        notification = Notification.objects.create_for_users(message)
        self.assertThat(
            reload_object(notification), MatchesStructure(
                ident=Is(None), user=Is(None), users=Is(True),
                admins=Is(True), message=Equals(message), context=Equals({}),
            ))

    def test_create_new_notification_for_users_with_ident(self):
        message = factory.make_name("message")
        ident = factory.make_name("ident")
        notification = Notification.objects.create_for_users(
            message, ident=ident)
        self.assertThat(
            reload_object(notification), MatchesStructure(
                ident=Equals(ident), user=Is(None), users=Is(True),
                admins=Is(True), message=Equals(message), context=Equals({}),
            ))

    def test_create_new_notification_for_users_with_reused_ident(self):
        # A new notification is created, and the ident is moved.
        ident = factory.make_name("ident")
        message = factory.make_name("message")
        n1 = Notification.objects.create_for_users(message, ident=ident)
        n2 = Notification.objects.create_for_users(message, ident=ident)
        self.assertThat(n2, Not(Equals(n1)))
        self.assertThat(
            reload_object(n1), MatchesStructure(
                ident=Is(None), user=Is(None), users=Is(True),
                admins=Is(True), message=Equals(message), context=Equals({}),
            ))
        self.assertThat(
            reload_object(n2), MatchesStructure(
                ident=Equals(ident), user=Is(None), users=Is(True),
                admins=Is(True), message=Equals(message), context=Equals({}),
            ))
        self.assertThat(
            Notification.objects.filter(ident=ident),
            HasLength(1))

    def test_create_new_notification_for_admins(self):
        message = factory.make_name("message")
        notification = Notification.objects.create_for_admins(message)
        self.assertThat(
            reload_object(notification), MatchesStructure(
                ident=Is(None), user=Is(None), users=Is(False),
                admins=Is(True), message=Equals(message), context=Equals({}),
            ))

    def test_create_new_notification_for_admins_with_ident(self):
        message = factory.make_name("message")
        ident = factory.make_name("ident")
        notification = Notification.objects.create_for_admins(
            message, ident=ident)
        self.assertThat(
            reload_object(notification), MatchesStructure(
                ident=Equals(ident), user=Is(None), users=Is(False),
                admins=Is(True), message=Equals(message), context=Equals({}),
            ))

    def test_create_new_notification_for_admins_with_reused_ident(self):
        # A new notification is created, and the ident is moved.
        ident = factory.make_name("ident")
        message = factory.make_name("message")
        n1 = Notification.objects.create_for_admins(message, ident=ident)
        n2 = Notification.objects.create_for_admins(message, ident=ident)
        self.assertThat(n2, Not(Equals(n1)))
        self.assertThat(
            reload_object(n1), MatchesStructure(
                ident=Is(None), user=Is(None), users=Is(False),
                admins=Is(True), message=Equals(message), context=Equals({}),
            ))
        self.assertThat(
            reload_object(n2), MatchesStructure(
                ident=Equals(ident), user=Is(None), users=Is(False),
                admins=Is(True), message=Equals(message), context=Equals({}),
            ))
        self.assertThat(
            Notification.objects.filter(ident=ident),
            HasLength(1))


class TestFindingAndDismissingNotifications(MAASServerTestCase):
    """Tests for finding and dismissing notifications."""

    def notify(self, user):
        message = factory.make_name("message")
        return (
            Notification.objects.create_for_user(message, user),
            Notification.objects.create_for_users(message),
            Notification.objects.create_for_admins(message),
        )

    def assertNotifications(self, user, notifications):
        self.assertThat(
            Notification.objects.find_for_user(user),
            MatchesAll(
                IsInstance(QuerySet),  # Not RawQuerySet.
                AfterPreprocessing(list, Equals(notifications)),
            ))

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


class TestNotification(MAASServerTestCase):
    """Tests for the `Notification`."""

    def test_render_combines_message_with_context(self):
        thing_a = factory.make_name("a")
        thing_b = random.randrange(1000)
        message = "There are {b:d} of {a} in my suitcase."
        context = {"a": thing_a, "b": thing_b}
        notification = Notification(message=message, context=context)
        self.assertThat(
            notification.render(), Equals(
                "There are " + str(thing_b) + " of " +
                thing_a + " in my suitcase."))

    def test_save_checks_that_rendering_works(self):
        message = "Dude, where's my {thing}?"
        notification = Notification(message=message)
        error = self.assertRaises(KeyError, notification.save)
        self.assertThat(str(error), Equals(repr("thing")))
        self.assertThat(notification.id, Is(None))
        self.assertThat(Notification.objects.all(), HasLength(0))

    def test_is_relevant_to_user(self):
        user = factory.make_User()
        user2 = factory.make_User()
        admin = factory.make_admin()

        Yes, No = Is(True), Is(False)

        notification_to_user = Notification(user=user)
        self.assertThat(notification_to_user.is_relevant_to(None), No)
        self.assertThat(notification_to_user.is_relevant_to(user), Yes)
        self.assertThat(notification_to_user.is_relevant_to(user2), No)
        self.assertThat(notification_to_user.is_relevant_to(admin), No)

        notification_to_users = Notification(users=True)
        self.assertThat(notification_to_users.is_relevant_to(None), No)
        self.assertThat(notification_to_users.is_relevant_to(user), Yes)
        self.assertThat(notification_to_users.is_relevant_to(user2), Yes)
        self.assertThat(notification_to_users.is_relevant_to(admin), No)

        notification_to_admins = Notification(admins=True)
        self.assertThat(notification_to_admins.is_relevant_to(None), No)
        self.assertThat(notification_to_admins.is_relevant_to(user), No)
        self.assertThat(notification_to_admins.is_relevant_to(user2), No)
        self.assertThat(notification_to_admins.is_relevant_to(admin), Yes)

        notification_to_all = Notification(users=True, admins=True)
        self.assertThat(notification_to_all.is_relevant_to(None), No)
        self.assertThat(notification_to_all.is_relevant_to(user), Yes)
        self.assertThat(notification_to_all.is_relevant_to(user2), Yes)
        self.assertThat(notification_to_all.is_relevant_to(admin), Yes)


class TestNotificationRepresentation(MAASServerTestCase):
    """Tests for the `Notification` representation."""

    def test_for_user(self):
        notification = Notification(
            user=factory.make_User("foobar"),
            message="The cat in the {place}",
            context=dict(place="bear trap"))
        self.assertThat(
            notification, AfterPreprocessing(repr, Equals(
                "<Notification user='foobar' users=False admins=False "
                "'The cat in the bear trap'>")))

    def test_for_users(self):
        notification = Notification(
            users=True, message="The cat in the {place}",
            context=dict(place="blender"))
        self.assertThat(
            notification, AfterPreprocessing(repr, Equals(
                "<Notification user=None users=True admins=False "
                "'The cat in the blender'>")))

    def test_for_admins(self):
        notification = Notification(
            admins=True, message="The cat in the {place}",
            context=dict(place="lava pit"))
        self.assertThat(
            notification, AfterPreprocessing(repr, Equals(
                "<Notification user=None users=False admins=True "
                "'The cat in the lava pit'>")))
