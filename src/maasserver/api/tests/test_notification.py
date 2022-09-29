# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Notification API."""


import http.client
import json
import random

from django.urls import reverse
from testtools.matchers import (
    AfterPreprocessing,
    ContainsDict,
    Equals,
    Is,
    IsInstance,
    MatchesDict,
    MatchesSetwise,
)

from maasserver.models.notification import Notification, NotificationDismissal
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.matchers import HasStatusCode
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.converters import json_load_bytes
from maasserver.utils.orm import reload_object


def get_notifications_uri():
    """Return a Notification's URI on the API."""
    return reverse("notifications_handler", args=[])


def get_notification_uri(notification):
    """Return a Notification URI on the API."""
    return reverse("notification_handler", args=[notification.id])


class TestURIs(MAASServerTestCase):
    def test_notifications_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/notifications/", get_notifications_uri()
        )

    def test_notification_handler_path(self):
        notification = factory.make_Notification()
        self.assertEqual(
            "/MAAS/api/2.0/notifications/%s/" % notification.id,
            get_notification_uri(notification),
        )


def MatchesNotification(notification):
    """Match the expected JSON rendering of `notification`."""
    return MatchesDict(
        {
            "id": Equals(notification.id),
            "ident": Equals(notification.ident),
            "user": (
                Is(None)
                if notification.user_id is None
                else ContainsDict(
                    {"username": Equals(notification.user.username)}
                )
            ),
            "users": Is(notification.users),
            "admins": Is(notification.admins),
            "message": Equals(notification.message),
            "context": Equals(notification.context),
            "category": Equals(notification.category),
            "dismissable": Equals(notification.dismissable),
            "resource_uri": Equals(get_notification_uri(notification)),
        }
    )


def HasBeenDismissedBy(user):
    """Match a notification that has been dismissed by the given user."""

    def dismissal_exists(notification):
        return NotificationDismissal.objects.filter(
            notification=notification, user=user
        ).exists()

    return AfterPreprocessing(dismissal_exists, Is(True))


class TestNotificationsAPI(APITestCase.ForUserAndAdmin):
    def test_read(self):
        notifications = [
            factory.make_Notification(
                user=self.user, users=False, admins=False
            ),
            factory.make_Notification(user=None, users=True, admins=False),
            factory.make_Notification(user=None, users=False, admins=True),
        ]
        uri = get_notifications_uri()
        response = self.client.get(uri)
        self.assertThat(response, HasStatusCode(http.client.OK))
        self.assertThat(
            json_load_bytes(response.content),
            MatchesSetwise(
                *(
                    MatchesNotification(notification)
                    for notification in notifications
                    if notification.is_relevant_to(self.user)
                )
            ),
        )

    def test_create_with_minimal_fields(self):
        message = factory.make_name("message")
        uri = get_notifications_uri()
        response = self.client.post(uri, {"message": message})
        if self.user.is_superuser:
            self.assertThat(response, HasStatusCode(http.client.OK))
            response = json_load_bytes(response.content)
            self.assertThat(response, ContainsDict({"id": IsInstance(int)}))
            notification = Notification.objects.get(id=response["id"])
            self.assertThat(response, MatchesNotification(notification))
        else:
            self.assertThat(response, HasStatusCode(http.client.FORBIDDEN))

    def test_create_with_all_fields(self):
        context = {factory.make_name("key"): factory.make_name("value")}
        data = {
            "ident": factory.make_name("ident"),
            "user": str(self.user.id),
            "users": random.choice(["true", "false"]),
            "admins": random.choice(["true", "false"]),
            "message": factory.make_name("message"),
            "context": json.dumps(context),
            "category": random.choice(("info", "success", "warning", "error")),
            "dismissable": random.choice(["true", "false"]),
        }
        uri = get_notifications_uri()
        response = self.client.post(uri, data)
        if self.user.is_superuser:
            self.assertThat(response, HasStatusCode(http.client.OK))
            self.assertThat(
                json_load_bytes(response.content),
                ContainsDict(
                    {
                        "id": IsInstance(int),
                        "ident": Equals(data["ident"]),
                        "user": ContainsDict(
                            {"username": Equals(self.user.username)}
                        ),
                        "users": Is(data["users"] == "true"),
                        "admins": Is(data["admins"] == "true"),
                        "message": Equals(data["message"]),
                        "context": Equals(context),
                        "category": Equals(data["category"]),
                        "dismissable": Is(data["dismissable"] == "true"),
                    }
                ),
            )
        else:
            self.assertThat(response, HasStatusCode(http.client.FORBIDDEN))


class TestNotificationsAPI_Anonymous(APITestCase.ForAnonymous):
    def test_read(self):
        uri = get_notifications_uri()
        response = self.client.get(uri)
        self.assertThat(response, HasStatusCode(http.client.UNAUTHORIZED))

    def test_create(self):
        uri = get_notifications_uri()
        response = self.client.post(uri, {"message": factory.make_name()})
        self.assertThat(response, HasStatusCode(http.client.UNAUTHORIZED))


class TestNotificationAPI(APITestCase.ForUserAndAdmin):
    def test_read_notification_for_self(self):
        notification = factory.make_Notification(user=self.user)
        uri = get_notification_uri(notification)
        response = self.client.get(uri)
        self.assertThat(response, HasStatusCode(http.client.OK))
        self.assertThat(
            json_load_bytes(response.content),
            MatchesNotification(notification),
        )

    def test_read_notification_for_other(self):
        other = factory.make_User()
        notification = factory.make_Notification(user=other)
        uri = get_notification_uri(notification)
        response = self.client.get(uri)
        if self.user.is_superuser:
            self.assertThat(response, HasStatusCode(http.client.OK))
            self.assertThat(
                json_load_bytes(response.content),
                MatchesNotification(notification),
            )
        else:
            self.assertThat(response, HasStatusCode(http.client.FORBIDDEN))

    def test_read_notification_for_users(self):
        notification = factory.make_Notification(users=True)
        uri = get_notification_uri(notification)
        response = self.client.get(uri)
        self.assertThat(response, HasStatusCode(http.client.OK))
        self.assertThat(
            json_load_bytes(response.content),
            MatchesNotification(notification),
        )

    def test_read_notification_for_admins(self):
        notification = factory.make_Notification(admins=True)
        uri = get_notification_uri(notification)
        response = self.client.get(uri)
        if self.user.is_superuser:
            self.assertThat(response, HasStatusCode(http.client.OK))
            self.assertThat(
                json_load_bytes(response.content),
                MatchesNotification(notification),
            )
        else:
            self.assertThat(response, HasStatusCode(http.client.FORBIDDEN))

    def test_update_is_for_admins_only(self):
        notification = factory.make_Notification()
        message_new = factory.make_name("message")
        uri = get_notification_uri(notification)
        response = self.client.put(uri, {"message": message_new})
        if self.user.is_superuser:
            self.assertThat(response, HasStatusCode(http.client.OK))
            notification = reload_object(notification)
            self.assertEqual(message_new, notification.message)
            self.assertThat(
                json_load_bytes(response.content),
                MatchesNotification(notification),
            )
        else:
            self.assertThat(response, HasStatusCode(http.client.FORBIDDEN))

    def test_delete_is_for_admins_only(self):
        notification = factory.make_Notification()
        uri = get_notification_uri(notification)
        response = self.client.delete(uri)
        if self.user.is_superuser:
            self.assertThat(response, HasStatusCode(http.client.NO_CONTENT))
            self.assertIsNone(reload_object(notification))
        else:
            self.assertThat(response, HasStatusCode(http.client.FORBIDDEN))

    def test_dismiss_notification_for_self(self):
        notification = factory.make_Notification(user=self.user)
        uri = get_notification_uri(notification)
        response = self.client.post(uri, {"op": "dismiss"})
        self.assertThat(response, HasStatusCode(http.client.OK))
        self.assertThat(notification, HasBeenDismissedBy(self.user))

    def test_dismiss_notification_for_other(self):
        other = factory.make_User()
        notification = factory.make_Notification(user=other)
        uri = get_notification_uri(notification)
        response = self.client.post(uri, {"op": "dismiss"})
        self.assertThat(response, HasStatusCode(http.client.FORBIDDEN))

    def test_dismiss_notification_for_users(self):
        notification = factory.make_Notification(users=True)
        uri = get_notification_uri(notification)
        response = self.client.post(uri, {"op": "dismiss"})
        if notification.is_relevant_to(self.user):
            self.assertThat(response, HasStatusCode(http.client.OK))
            self.assertThat(notification, HasBeenDismissedBy(self.user))
        else:
            self.assertThat(response, HasStatusCode(http.client.FORBIDDEN))

    def test_dismiss_notification_for_admins(self):
        notification = factory.make_Notification(admins=True)
        uri = get_notification_uri(notification)
        response = self.client.post(uri, {"op": "dismiss"})
        if notification.is_relevant_to(self.user):
            self.assertThat(response, HasStatusCode(http.client.OK))
            self.assertThat(notification, HasBeenDismissedBy(self.user))
        else:
            self.assertThat(response, HasStatusCode(http.client.FORBIDDEN))


class TestNotificationAPI_Anonymous(APITestCase.ForAnonymous):
    def test_read_notification_for_other(self):
        other = factory.make_User()
        notification = factory.make_Notification(user=other)
        uri = get_notification_uri(notification)
        response = self.client.get(uri)
        self.assertThat(response, HasStatusCode(http.client.UNAUTHORIZED))

    def test_read_notification_for_users(self):
        notification = factory.make_Notification(users=True)
        uri = get_notification_uri(notification)
        response = self.client.get(uri)
        self.assertThat(response, HasStatusCode(http.client.UNAUTHORIZED))

    def test_read_notification_for_admins(self):
        notification = factory.make_Notification(admins=True)
        uri = get_notification_uri(notification)
        response = self.client.get(uri)
        self.assertThat(response, HasStatusCode(http.client.UNAUTHORIZED))

    def test_update_is_for_admins_only(self):
        notification = factory.make_Notification()
        message_new = factory.make_name("message")
        uri = get_notification_uri(notification)
        response = self.client.put(uri, {"message": message_new})
        self.assertThat(response, HasStatusCode(http.client.UNAUTHORIZED))

    def test_delete_is_for_admins_only(self):
        notification = factory.make_Notification()
        uri = get_notification_uri(notification)
        response = self.client.delete(uri)
        self.assertThat(response, HasStatusCode(http.client.UNAUTHORIZED))
