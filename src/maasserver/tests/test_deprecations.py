from maasserver import deprecations
from maasserver.deprecations import (
    Deprecation,
    get_deprecations,
    log_deprecations,
    sync_deprecation_notifications,
)
from maasserver.models import Notification
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from provisioningserver.logger import LegacyLogger


class TestGetDeprecations(MAASServerTestCase):
    def test_empty(self):
        self.assertEqual(get_deprecations(), [])

    def test_md2(self):
        factory.make_Pod(pod_type="rsd")
        [md2] = get_deprecations()
        self.assertEqual(md2.id, "MD2")
        self.assertEqual(md2.since, "2.9.4")


class TestLogDeprecations(MAASServerTestCase):
    def test_log_deprecations(self):
        self.patch(deprecations, "get_deprecations").return_value = [
            Deprecation(
                id="MD123", since="2.9", description="something is deprecated"
            )
        ]

        events = []
        logger = LegacyLogger(observer=events.append)
        log_deprecations(logger=logger)
        [event] = events
        self.assertEqual(
            event["_message_0"],
            "Deprecation MD123 (https://maas.io/deprecations/MD123): "
            "something is deprecated",
        )


class TestSyncDeprecationNotifications(MAASServerTestCase):
    def test_create_notifications(self):
        self.patch(deprecations, "get_deprecations").return_value = [
            Deprecation(
                id="MD123", since="2.9", description="something is deprecated"
            )
        ]

        sync_deprecation_notifications()
        notification1, notification2 = Notification.objects.order_by("ident")
        self.assertEqual(notification1.ident, "deprecation_MD123_admins")
        self.assertEqual(notification1.category, "warning")
        self.assertFalse(notification1.dismissable)
        self.assertTrue(notification1.admins)
        self.assertFalse(notification1.users)
        self.assertIn(
            "https://maas.io/deprecations/MD123", notification1.message
        )
        self.assertNotIn(
            "Please contact your MAAS administrator.", notification1.message
        )
        self.assertEqual(notification2.ident, "deprecation_MD123_users")
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
