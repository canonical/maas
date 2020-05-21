from pathlib import Path

from fixtures import EnvironmentVariable

from maasserver.deprecations import (
    get_deprecations,
    log_deprecations,
    sync_deprecation_notifications,
)
from maasserver.models import Notification
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.testcase import MAASTestCase
from provisioningserver.logger import LegacyLogger


class TestGetDeprecations(MAASTestCase):
    def test_empty(self):
        self.assertEqual(get_deprecations(), [])

    def test_deprecation_notices_snap_not_all_mode(self):
        self.useFixture(EnvironmentVariable("SNAP", "/snap/maas/current"))
        snap_common_path = Path(self.make_dir())
        self.useFixture(
            EnvironmentVariable("SNAP_COMMON", str(snap_common_path))
        )
        snap_common_path.joinpath("snap_mode").write_text(
            "region+rack", "utf-8"
        )
        self.assertEqual(get_deprecations(), [])

    def test_deprecation_notices_snap_all_mode(self):
        self.useFixture(EnvironmentVariable("SNAP", "/snap/maas/current"))
        snap_common_path = Path(self.make_dir())
        self.useFixture(
            EnvironmentVariable("SNAP_COMMON", str(snap_common_path))
        )
        snap_common_path.joinpath("snap_mode").write_text("all", "utf-8")
        [notice] = get_deprecations()
        self.assertEqual(notice.id, "MD1")
        self.assertEqual(notice.since, "2.8")
        self.assertEqual(notice.url, "https://maas.io/deprecations/MD1")


class TestLogDeprecations(MAASTestCase):
    def test_log_deprecations(self):
        self.useFixture(EnvironmentVariable("SNAP", "/snap/maas/current"))
        snap_common_path = Path(self.make_dir())
        self.useFixture(
            EnvironmentVariable("SNAP_COMMON", str(snap_common_path))
        )
        snap_common_path.joinpath("snap_mode").write_text("all", "utf-8")

        events = []
        logger = LegacyLogger(observer=events.append)
        log_deprecations(logger=logger)
        [event] = events
        self.assertEqual(
            event["_message_0"],
            "Deprecation MD1 (https://maas.io/deprecations/MD1): "
            "The setup for this MAAS is deprecated and not suitable for production "
            "environments, as the database is running inside the snap.",
        )


class TestSyncDeprecationNotifications(MAASServerTestCase):
    def test_create_notifications(self):
        self.useFixture(EnvironmentVariable("SNAP", "/snap/maas/current"))
        snap_common_path = Path(self.make_dir())
        self.useFixture(
            EnvironmentVariable("SNAP_COMMON", str(snap_common_path))
        )
        snap_common_path.joinpath("snap_mode").write_text("all", "utf-8")

        sync_deprecation_notifications()
        notification1, notification2 = Notification.objects.order_by("ident")
        self.assertEqual(notification1.ident, "deprecation_MD1_admins")
        self.assertEqual(notification1.category, "warning")
        self.assertFalse(notification1.dismissable)
        self.assertTrue(notification1.admins)
        self.assertFalse(notification1.users)
        self.assertIn(
            "https://maas.io/deprecations/MD1", notification1.message
        )
        self.assertNotIn(
            "Please contact your MAAS administrator.", notification1.message
        )
        self.assertEqual(notification2.ident, "deprecation_MD1_users")
        self.assertEqual(notification2.category, "warning")
        self.assertFalse(notification2.dismissable)
        self.assertFalse(notification2.admins)
        self.assertTrue(notification2.users)
        self.assertIn(
            "Please contact your MAAS administrator.", notification2.message
        )

    def test_remove_deprecations(self):
        Notification(
            ident="deprecation_MD1_admins", message="some text"
        ).save()
        sync_deprecation_notifications()
        # the notification is removed since there is no active deprecation
        self.assertFalse(Notification.objects.exists())
