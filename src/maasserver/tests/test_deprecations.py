from maasserver import deprecations
from maasserver.deprecations import (
    Deprecation,
    DEPRECATIONS,
    get_deprecations,
    log_deprecations,
    sync_deprecation_notifications,
)
from maasserver.models import Notification
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.testcase import MAASTestCase
from provisioningserver.logger import LegacyLogger
from provisioningserver.utils.version import MAASVersion


class TestGetDeprecations(MAASServerTestCase):
    def test_dhcp_snippets_not_included(self):
        self.patch(deprecations, "get_maas_version").return_value = (
            MAASVersion.from_string("3.5.0")
        )
        self.assertNotIn(DEPRECATIONS["DHCP_SNIPPETS"], get_deprecations())

    def test_dhcp_snippets_not_included_MAAS_4(self):
        self.patch(deprecations, "get_maas_version").return_value = (
            MAASVersion.from_string("4.0.0")
        )
        self.assertNotIn(DEPRECATIONS["DHCP_SNIPPETS"], get_deprecations())

    def test_dhcp_snippets_included(self):
        self.patch(deprecations, "get_maas_version").return_value = (
            MAASVersion.from_string("3.6.0")
        )
        self.assertIn(DEPRECATIONS["DHCP_SNIPPETS"], get_deprecations())

    def test_old_postgres_version(self):
        self.patch(deprecations, "postgresql_major_version").return_value = 14
        self.assertIn(
            DEPRECATIONS["POSTGRES_OLDER_THAN_16"], get_deprecations()
        )

    def test_wrong_database_owner(self):
        self.patch(deprecations, "get_database_owner").return_value = (
            "postgres"
        )
        self.assertIn(
            DEPRECATIONS["WRONG_MAAS_DATABASE_OWNER"], get_deprecations()
        )


class TestLogDeprecations(MAASTestCase):
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
        self.patch(deprecations, "get_deprecations").return_value = []
        sync_deprecation_notifications()
        # the notification is removed since there is no active deprecation
        self.assertFalse(Notification.objects.exists())
