# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Notification forms."""

import json
import random

from maasserver.forms.notification import NotificationForm
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase

categories = "info", "success", "warning", "error"


class TestNotificationForm(MAASServerTestCase):
    def test_notification_can_be_created_with_just_message(self):
        notification_message = factory.make_name("message")
        form = NotificationForm({"message": notification_message})
        self.assertTrue(form.is_valid(), form.errors)
        notification = form.save()
        self.assertIsNone(notification.ident)
        self.assertEqual(notification.message, notification_message)
        self.assertIsNone(notification.user)
        self.assertFalse(notification.users)
        self.assertFalse(notification.admins)
        self.assertEqual(notification.category, "info")
        self.assertEqual(notification.context, {})

    def test_notification_can_be_created_with_empty_fields(self):
        notification_message = factory.make_name("message")
        form = NotificationForm(
            {
                "ident": "",
                "user": "",
                "users": "",
                "admins": "",
                "message": notification_message,
                "context": "",
                "category": "",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        notification = form.save()
        self.assertIsNone(notification.ident)
        self.assertEqual(notification.message, notification_message)
        self.assertIsNone(notification.user)
        self.assertFalse(notification.users)
        self.assertFalse(notification.admins)
        self.assertEqual(notification.category, "info")
        self.assertEqual(notification.context, {})
        self.assertTrue(notification.dismissable)

    def test_notification_can_be_created_with_all_fields(self):
        user = factory.make_User()
        data = {
            "ident": factory.make_name("ident"),
            "user": str(user.id),
            "users": random.choice(["true", "false"]),
            "admins": random.choice(["true", "false"]),
            "message": factory.make_name("message"),
            "context": json.dumps(
                {factory.make_name("key"): factory.make_name("value")}
            ),
            "category": random.choice(categories),
            "dismissable": random.choice(["true", "false"]),
        }
        form = NotificationForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        notification = form.save()
        self.assertEqual(notification.ident, data["ident"])
        self.assertEqual(notification.message, data["message"])
        self.assertEqual(notification.user, user)
        if data["users"] == "true":
            self.assertTrue(notification.users)
        else:
            self.assertFalse(notification.users)
        if data["admins"] == "true":
            self.assertTrue(notification.admins)
        else:
            self.assertFalse(notification.admins)
        self.assertEqual(notification.context, json.loads(data["context"]))
        if data["dismissable"] == "true":
            self.assertTrue(notification.dismissable)
        else:
            self.assertFalse(notification.dismissable)
        self.assertEqual(notification.category, data["category"])

    def test_notification_can_be_updated(self):
        notification = factory.make_Notification()
        user = factory.make_User()
        data = {
            "ident": factory.make_name("ident"),
            "user": str(user.id),
            "users": "false" if notification.users else "true",
            "admins": "false" if notification.admins else "true",
            "message": factory.make_name("message"),
            "context": json.dumps(
                {factory.make_name("key"): factory.make_name("value")}
            ),
            "category": random.choice(
                [c for c in categories if c != notification.category]
            ),
        }
        form = NotificationForm(instance=notification, data=data)
        self.assertTrue(form.is_valid(), form.errors)
        notification_saved = form.save()
        self.assertEqual(notification, notification_saved)
        self.assertEqual(notification_saved.ident, data["ident"])
        self.assertEqual(notification_saved.message, data["message"])
        self.assertEqual(notification_saved.user, user)
        if data["users"] == "true":
            self.assertTrue(notification_saved.users)
        else:
            self.assertFalse(notification_saved.users)
        if data["admins"] == "true":
            self.assertTrue(notification_saved.admins)
        else:
            self.assertFalse(notification_saved.admins)
        self.assertEqual(
            notification_saved.context, json.loads(data["context"])
        )
        self.assertEqual(notification_saved.category, data["category"])
