# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Notification API."""


import http.client
import json
import random

from django.urls import reverse

from maasserver.models.notification import Notification, NotificationDismissal
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
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


class AssertNotificationsMixin:
    def assert_notification_matches(self, notification, parsed_notification):
        """Assert the expected JSON rendering of `notification`."""
        self.assertEqual(parsed_notification.get("id"), notification.id)
        self.assertEqual(parsed_notification.get("ident"), notification.ident)
        if notification.user_id is None:
            self.assertIsNone(parsed_notification.get("user", object()))
        else:
            self.assertEqual(
                parsed_notification.get("user").get("username"),
                notification.user.username,
            )
            self.assertEqual(
                parsed_notification.get("users"), notification.users
            )
            self.assertEqual(
                parsed_notification.get("admins"), notification.admins
            )
            self.assertEqual(
                parsed_notification.get("message"), notification.message
            )
            self.assertEqual(
                parsed_notification.get("context"), notification.context
            )
            self.assertEqual(
                parsed_notification.get("category"), notification.category
            )
            self.assertEqual(
                parsed_notification.get("dismissable"),
                notification.dismissable,
            )
            self.assertEqual(
                parsed_notification.get("resource_uri"),
                get_notification_uri(notification),
            )


class TestNotificationsAPI(
    AssertNotificationsMixin, APITestCase.ForUserAndAdmin
):
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
        self.assertEqual(response.status_code, http.client.OK)
        parsed_notifications = response.json()
        for notification, parsed_notification in zip(
            notifications, parsed_notifications
        ):
            if notification.is_relevant_to(self.user):
                self.assert_notification_matches(
                    notification, parsed_notification
                )

    def test_create_with_minimal_fields(self):
        message = factory.make_name("message")
        uri = get_notifications_uri()
        response = self.client.post(uri, {"message": message})
        if self.user.is_superuser:
            self.assertEqual(response.status_code, http.client.OK)
            response = response.json()
            self.assertIsInstance(response.get("id"), int)
            notification = Notification.objects.get(id=response["id"])
            self.assert_notification_matches(notification, response)
        else:
            self.assertEqual(response.status_code, http.client.FORBIDDEN)

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
            self.assertEqual(response.status_code, http.client.OK)
            notification = response.json()
            self.assertIsInstance(notification.get("id"), int)
            self.assertEqual(notification.get("ident"), data["ident"])
            self.assertEqual(
                notification.get("user").get("username"), self.user.username
            )
            self.assertEqual(
                notification.get("users"), data["users"] == "true"
            )
            self.assertEqual(
                notification.get("admins"), data["admins"] == "true"
            )
            self.assertEqual(notification.get("message"), data["message"])
            self.assertEqual(notification.get("context"), context)
            self.assertEqual(notification.get("category"), data["category"])
            self.assertEqual(
                notification.get("dismissable"), data["dismissable"] == "true"
            )
        else:
            self.assertEqual(response.status_code, http.client.FORBIDDEN)


class TestNotificationsAPI_Anonymous(APITestCase.ForAnonymous):
    def test_read(self):
        uri = get_notifications_uri()
        response = self.client.get(uri)
        self.assertEqual(response.status_code, http.client.UNAUTHORIZED)

    def test_create(self):
        uri = get_notifications_uri()
        response = self.client.post(uri, {"message": factory.make_name()})
        self.assertEqual(response.status_code, http.client.UNAUTHORIZED)


class TestNotificationAPI(
    AssertNotificationsMixin, APITestCase.ForUserAndAdmin
):
    def test_read_notification_for_self(self):
        notification = factory.make_Notification(user=self.user)
        uri = get_notification_uri(notification)
        response = self.client.get(uri)
        self.assertEqual(response.status_code, http.client.OK)
        self.assert_notification_matches(notification, response.json())

    def test_read_notification_for_other(self):
        other = factory.make_User()
        notification = factory.make_Notification(user=other)
        uri = get_notification_uri(notification)
        response = self.client.get(uri)
        if self.user.is_superuser:
            self.assertEqual(response.status_code, http.client.OK)
            self.assert_notification_matches(notification, response.json())
        else:
            self.assertEqual(response.status_code, http.client.FORBIDDEN)

    def test_read_notification_for_users(self):
        notification = factory.make_Notification(users=True)
        uri = get_notification_uri(notification)
        response = self.client.get(uri)
        self.assertEqual(response.status_code, http.client.OK)
        self.assert_notification_matches(notification, response.json())

    def test_read_notification_for_admins(self):
        notification = factory.make_Notification(admins=True)
        uri = get_notification_uri(notification)
        response = self.client.get(uri)
        if self.user.is_superuser:
            self.assertEqual(response.status_code, http.client.OK)
            self.assert_notification_matches(notification, response.json())
        else:
            self.assertEqual(response.status_code, http.client.FORBIDDEN)

    def test_update_is_for_admins_only(self):
        notification = factory.make_Notification()
        message_new = factory.make_name("message")
        uri = get_notification_uri(notification)
        response = self.client.put(uri, {"message": message_new})
        if self.user.is_superuser:
            self.assertEqual(response.status_code, http.client.OK)
            notification = reload_object(notification)
            self.assertEqual(message_new, notification.message)
            self.assert_notification_matches(notification, response.json())
        else:
            self.assertEqual(response.status_code, http.client.FORBIDDEN)

    def test_delete_is_for_admins_only(self):
        notification = factory.make_Notification()
        uri = get_notification_uri(notification)
        response = self.client.delete(uri)
        if self.user.is_superuser:
            self.assertEqual(response.status_code, http.client.NO_CONTENT)
            self.assertIsNone(reload_object(notification))
        else:
            self.assertEqual(response.status_code, http.client.FORBIDDEN)

    def test_dismiss_notification_for_self(self):
        notification = factory.make_Notification(user=self.user)
        uri = get_notification_uri(notification)
        response = self.client.post(uri, {"op": "dismiss"})
        self.assertEqual(response.status_code, http.client.OK)
        has_been_dismissed = NotificationDismissal.objects.filter(
            notification=notification, user=self.user
        ).exists()
        self.assertTrue(has_been_dismissed)

    def test_dismiss_notification_for_other(self):
        other = factory.make_User()
        notification = factory.make_Notification(user=other)
        uri = get_notification_uri(notification)
        response = self.client.post(uri, {"op": "dismiss"})
        self.assertEqual(response.status_code, http.client.FORBIDDEN)

    def test_dismiss_notification_for_users(self):
        notification = factory.make_Notification(users=True)
        uri = get_notification_uri(notification)
        response = self.client.post(uri, {"op": "dismiss"})
        if notification.is_relevant_to(self.user):
            self.assertEqual(response.status_code, http.client.OK)
            has_been_dismissed = NotificationDismissal.objects.filter(
                notification=notification, user=self.user
            ).exists()
            self.assertTrue(has_been_dismissed)
        else:
            self.assertEqual(response.status_code, http.client.FORBIDDEN)

    def test_dismiss_notification_for_admins(self):
        notification = factory.make_Notification(admins=True)
        uri = get_notification_uri(notification)
        response = self.client.post(uri, {"op": "dismiss"})
        if notification.is_relevant_to(self.user):
            self.assertEqual(response.status_code, http.client.OK)
            has_been_dismissed = NotificationDismissal.objects.filter(
                notification=notification, user=self.user
            ).exists()
            self.assertTrue(has_been_dismissed)
        else:
            self.assertEqual(response.status_code, http.client.FORBIDDEN)


class TestNotificationAPI_Anonymous(APITestCase.ForAnonymous):
    def test_read_notification_for_other(self):
        other = factory.make_User()
        notification = factory.make_Notification(user=other)
        uri = get_notification_uri(notification)
        response = self.client.get(uri)
        self.assertEqual(response.status_code, http.client.UNAUTHORIZED)

    def test_read_notification_for_users(self):
        notification = factory.make_Notification(users=True)
        uri = get_notification_uri(notification)
        response = self.client.get(uri)
        self.assertEqual(response.status_code, http.client.UNAUTHORIZED)

    def test_read_notification_for_admins(self):
        notification = factory.make_Notification(admins=True)
        uri = get_notification_uri(notification)
        response = self.client.get(uri)
        self.assertEqual(response.status_code, http.client.UNAUTHORIZED)

    def test_update_is_for_admins_only(self):
        notification = factory.make_Notification()
        message_new = factory.make_name("message")
        uri = get_notification_uri(notification)
        response = self.client.put(uri, {"message": message_new})
        self.assertEqual(response.status_code, http.client.UNAUTHORIZED)

    def test_delete_is_for_admins_only(self):
        notification = factory.make_Notification()
        uri = get_notification_uri(notification)
        response = self.client.delete(uri)
        self.assertEqual(response.status_code, http.client.UNAUTHORIZED)
