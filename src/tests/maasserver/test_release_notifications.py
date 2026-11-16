import datetime

from django.utils import timezone

from maasserver import release_notifications
from maasserver.models import ControllerInfo, Notification
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)


class TestVersionCheck(MAASServerTestCase):
    def test_new_release_available(self):
        ControllerInfo.objects.set_version(
            factory.make_RackController(),
            "2.8.1",
        )
        self.assertTrue(release_notifications.notification_available("2.9.0"))

    def test_already_on_latest_version(self):
        ControllerInfo.objects.set_version(
            factory.make_RackController(),
            "2.9.0",
        )
        self.assertFalse(release_notifications.notification_available("2.9.0"))

    def test_notification_is_old(self):
        ControllerInfo.objects.set_version(
            factory.make_RackController(),
            "2.9.0",
        )
        self.assertFalse(release_notifications.notification_available("2.8.0"))


class TestReleaseNotification(MAASTransactionServerTestCase):
    def _get_release_notifications(self):
        return Notification.objects.filter(
            ident=release_notifications.RELEASE_NOTIFICATION_IDENT
        )

    def test_create_notification(self):
        """Test creating a new release notification"""

        message = "Upgrade to version 3.14 today"
        release_notifications.ensure_notification_exists(message)
        original_notification = self._get_release_notifications().get()

        release_notifications.ensure_notification_exists(message)

        self.assertEqual(self._get_release_notifications().count(), 1)

        notification = self._get_release_notifications().get()
        self.assertEqual(message, notification.message)
        self.assertEqual(notification.created, original_notification.created)
        # As the notification hasn't changed, we don't want the updated datetime
        # to be changed.
        self.assertEqual(notification.updated, original_notification.updated)

    def test_updating_notification(self):
        """Test updating a release notification with a new message"""

        message = "Upgrade to version 3.1 today"
        release_notifications.ensure_notification_exists(message)
        original_notification = self._get_release_notifications().get()

        message = "Upgrade to version 3.2 today"
        release_notifications.ensure_notification_exists(message)

        self.assertEqual(self._get_release_notifications().count(), 1)

        notification = self._get_release_notifications().get()
        self.assertEqual(message, notification.message)
        self.assertEqual(notification.created, original_notification.created)
        self.assertGreater(notification.updated, original_notification.updated)

    def test_resurface_notification(self):
        """Test resufacing release notifications that were dismissed"""
        user1 = factory.make_User("user")
        user2 = factory.make_User("user2")

        message = "Upgrade to version 3.14 today"
        release_notifications.ensure_notification_exists(message)

        notification = self._get_release_notifications().get()
        notification.dismiss(user1)
        notification.dismiss(user2)

        # We expect to have two dismissals here, one for each user
        self.assertEqual(notification.notificationdismissal_set.count(), 2)

        # Manually update the notification to appear in the past.
        three_weeks_ago = timezone.now() - datetime.timedelta(weeks=3)
        notification.notificationdismissal_set.filter(user=user2).update(
            updated=three_weeks_ago, created=three_weeks_ago
        )

        release_notifications.ensure_notification_exists(message)

        # as one of the dismissals was old it should be deleted, leaving us
        # with only one for user1
        self.assertEqual(
            notification.notificationdismissal_set.filter(user=user1).count(),
            1,
        )
        self.assertEqual(
            notification.notificationdismissal_set.filter(user=user2).count(),
            0,
        )

        self.assertEqual(self._get_release_notifications().count(), 1)

        notification = self._get_release_notifications().get()
        self.assertEqual(message, notification.message)
