# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Notification forms."""


import json
import random

from testtools.matchers import MatchesStructure

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
        self.assertThat(
            notification,
            MatchesStructure.byEquality(
                ident=None,
                message=notification_message,
                user=None,
                users=False,
                admins=False,
                category="info",
                context={},
            ),
        )

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
        self.assertThat(
            notification,
            MatchesStructure.byEquality(
                ident=None,
                message=notification_message,
                user=None,
                users=False,
                admins=False,
                category="info",
                context={},
                dismissable=True,
            ),
        )

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
        expected = dict(
            data,
            user=user,
            users=(data["users"] == "true"),
            admins=(data["admins"] == "true"),
            context=json.loads(data["context"]),
            dismissable=(data["dismissable"] == "true"),
        )
        self.assertThat(notification, MatchesStructure.byEquality(**expected))

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
        expected = dict(
            data,
            user=user,
            users=(data["users"] == "true"),
            admins=(data["admins"] == "true"),
            context=json.loads(data["context"]),
        )
        self.assertThat(
            notification_saved, MatchesStructure.byEquality(**expected)
        )
