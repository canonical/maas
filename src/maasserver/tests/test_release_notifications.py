import datetime

from maasserver import release_notifications
from maasserver.models import Notification
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)


class TestVersionCheck(MAASServerTestCase):
    def test_new_release_available(self):
        current_version = "2.8.1"
        notification_maas_version = "2.9.0"
        self.assertTrue(
            release_notifications.notification_available(
                notification_maas_version, current_version
            )
        )

    def test_already_on_latest_version(self):
        current_version = "2.9.0"
        notification_maas_version = "2.9.0"
        self.assertFalse(
            release_notifications.notification_available(
                notification_maas_version, current_version
            )
        )

    def test_notification_is_old(self):
        current_version = "2.9.0"
        notification_maas_version = "2.8.0"
        self.assertFalse(
            release_notifications.notification_available(
                notification_maas_version, current_version
            )
        )


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

        message = "Upgrade to version 3.14 today"
        release_notifications.ensure_notification_exists(message)

        # Manually update the notification to appear in the past.
        seven_weeks_ago = datetime.datetime.now() - datetime.timedelta(weeks=7)
        self._get_release_notifications().update(
            updated=seven_weeks_ago, created=seven_weeks_ago
        )
        original_notification = self._get_release_notifications().get()

        release_notifications.ensure_notification_exists(message)

        self.assertEqual(self._get_release_notifications().count(), 1)

        notification = self._get_release_notifications().get()
        self.assertEqual(message, notification.message)
        self.assertEqual(notification.created, original_notification.created)
        self.assertGreater(notification.updated, original_notification.updated)
