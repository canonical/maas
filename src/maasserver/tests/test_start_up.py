# Copyright 2012-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pathlib import Path
import random
from unittest.mock import call, MagicMock

from testtools.matchers import HasLength

from maasserver import deprecations, eventloop, locks, start_up, vault
from maasserver.config import RegionConfiguration
from maasserver.models.config import Config
from maasserver.models.controllerinfo import ControllerInfo
from maasserver.models.node import RegionController
from maasserver.models.notification import Notification
from maasserver.models.signals import bootsources
from maasserver.secrets import SecretManager
from maasserver.start_up import migrate_db_credentials_if_necessary
from maasserver.testing.config import RegionConfigurationFixture
from maasserver.testing.eventloop import RegionEventLoopFixture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.testing.vault import FakeVaultClient
from maasserver.utils.orm import post_commit_hooks
from maasserver.vault import UnknownSecretPath, VaultError
from maastesting import get_testing_timeout
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from provisioningserver.config import ConfigurationFile
from provisioningserver.drivers.osystem.ubuntu import UbuntuOS
from provisioningserver.security import to_hex
from provisioningserver.utils import ipaddr
from provisioningserver.utils.deb import DebVersionsInfo
from provisioningserver.utils.env import (
    MAAS_ID,
    MAAS_SECRET,
    MAAS_SHARED_SECRET,
)
from provisioningserver.utils.testing import MAASIDFixture, MAASUUIDFixture


class TestStartUp(MAASTransactionServerTestCase):

    """Tests for the `start_up` function.

    The actual work happens in `inner_start_up` and `test_start_up`; the tests
    you see here are for the locking wrapper only.
    """

    def setUp(self):
        super().setUp()
        self.useFixture(RegionEventLoopFixture())
        self.patch(ipaddr, "get_ip_addr").return_value = {}
        temp_dir = Path(self.make_dir())
        self.patch(MAAS_SHARED_SECRET, "path", temp_dir / "secret")
        MAAS_SECRET.set(factory.make_bytes())

    def tearDown(self):
        super().tearDown()
        # start_up starts the Twisted event loop, so we need to stop it.
        eventloop.reset().wait(get_testing_timeout())

    def test_inner_start_up_runs_in_exclusion(self):
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

        locked = factory.make_exception("locked")
        unlocked = factory.make_exception("unlocked")

        def check_lock():
            raise locked if locks.startup.is_locked() else unlocked

        self.patch(start_up, "load_builtin_scripts").side_effect = check_lock
        self.assertRaises(type(locked), start_up.inner_start_up, master=True)

    def test_start_up_retries_with_wait_on_exception(self):
        inner_start_up = self.patch(start_up, "inner_start_up")
        inner_start_up.side_effect = [
            factory.make_exception("Boom!"),
            None,  # Success.
        ]
        # We don't want to really sleep.
        self.patch(start_up, "pause")
        # start_up() returns without error.
        start_up.start_up()
        # However, it did call inner_start_up() twice; the first call resulted
        # in the "Boom!" exception so it tried again.
        self.expectThat(
            inner_start_up,
            MockCallsMatch(call(master=False), call(master=False)),
        )
        # It also slept once, for 3 seconds, between those attempts.
        self.expectThat(start_up.pause, MockCalledOnceWith(3.0))

    def test_start_up_fetches_secret_from_vault_after_migration(self):
        vault.clear_vault_client_caches()
        # Apparently, MAAS_SECRET state is shared between the tests
        old_secret = MAAS_SECRET.get()
        # Prepare fake vault
        expected_shared_secret = b"EXPECTED"
        client = FakeVaultClient()
        self.patch(vault, "_get_region_vault_client").return_value = client
        SecretManager(client).set_simple_secret(
            "rpc-shared", to_hex(expected_shared_secret)
        )
        # Cache vault being disabled
        Config.objects.set_config("vault_enabled", False)
        self.assertIsNone(vault.get_region_vault_client_if_enabled())
        # Enable vault as if migration was finished before the call
        Config.objects.set_config("vault_enabled", True)
        # No need to do actual startup
        self.patch(start_up, "inner_start_up")
        self.patch(start_up, "pause")

        with post_commit_hooks:
            start_up.start_up()

        self.assertEqual(expected_shared_secret, MAAS_SECRET.get())
        MAAS_SECRET.set(old_secret)
        vault.clear_vault_client_caches()


class TestInnerStartUp(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        self.useFixture(MAASIDFixture(None))
        self.useFixture(MAASUUIDFixture("uuid"))
        self.patch_autospec(start_up, "dns_kms_setting_changed")
        self.patch(ipaddr, "get_ip_addr").return_value = {}
        self.versions_info = DebVersionsInfo(
            current={"version": "1:3.1.0-1234-g.deadbeef"}
        )
        self.patch(
            start_up, "get_versions_info"
        ).return_value = self.versions_info
        temp_dir = Path(self.make_dir())
        self.patch(MAAS_SHARED_SECRET, "path", temp_dir / "secret")
        MAAS_SECRET.set(factory.make_bytes())

    def test_calls_dns_kms_setting_changed_if_master(self):
        with post_commit_hooks:
            start_up.inner_start_up(master=True)
        self.assertThat(start_up.dns_kms_setting_changed, MockCalledOnceWith())

    def test_does_not_call_dns_kms_setting_changed_if_not_master(self):
        with post_commit_hooks:
            start_up.inner_start_up(master=False)
        self.assertThat(start_up.dns_kms_setting_changed, MockNotCalled())

    def test_calls_load_builtin_scripts_if_master(self):
        self.patch_autospec(start_up, "load_builtin_scripts")
        with post_commit_hooks:
            start_up.inner_start_up(master=True)
        self.assertThat(start_up.load_builtin_scripts, MockCalledOnceWith())

    def test_does_not_call_load_builtin_scripts_if_not_master(self):
        self.patch_autospec(start_up, "load_builtin_scripts")
        with post_commit_hooks:
            start_up.inner_start_up(master=False)
        self.assertThat(start_up.load_builtin_scripts, MockNotCalled())

    def test_resets_deprecated_commissioning_release_if_master(self):
        Config.objects.set_config(
            "commissioning_distro_series", random.choice(["precise", "trusty"])
        )
        with post_commit_hooks:
            start_up.inner_start_up(master=True)
        ubuntu = UbuntuOS()
        self.assertEqual(
            Config.objects.get_config("commissioning_distro_series"),
            ubuntu.get_default_commissioning_release(),
        )
        self.assertTrue(
            Notification.objects.filter(
                ident="commissioning_release_deprecated"
            ).exists()
        )

    def test_doesnt_reset_deprecated_commissioning_release_if_notmaster(self):
        release = random.choice(["precise", "trusty"])
        Config.objects.set_config("commissioning_distro_series", release)
        with post_commit_hooks:
            start_up.inner_start_up(master=False)
        self.assertEqual(
            Config.objects.get_config("commissioning_distro_series"), release
        )
        self.assertFalse(
            Notification.objects.filter(
                ident="commissioning_release_deprecated"
            ).exists()
        )

    def test_sets_maas_url_master(self):
        Config.objects.set_config("maas_url", "http://default.example.com/")
        self.useFixture(
            RegionConfigurationFixture(maas_url="http://custom.example.com/")
        )
        with post_commit_hooks:
            start_up.inner_start_up(master=True)

        self.assertEqual(
            "http://custom.example.com/", Config.objects.get_config("maas_url")
        )

    def test_sets_maas_url_not_master(self):
        Config.objects.set_config("maas_url", "http://default.example.com/")
        self.useFixture(
            RegionConfigurationFixture(maas_url="http://my.example.com/")
        )
        with post_commit_hooks:
            start_up.inner_start_up(master=False)

        self.assertEqual(
            "http://default.example.com/",
            Config.objects.get_config("maas_url"),
        )

    def test_doesnt_call_dns_kms_setting_changed_if_not_master(self):
        with post_commit_hooks:
            start_up.inner_start_up(master=False)
        self.assertThat(start_up.dns_kms_setting_changed, MockNotCalled())

    def test_creates_region_controller(self):
        self.assertThat(RegionController.objects.all(), HasLength(0))
        with post_commit_hooks:
            start_up.inner_start_up(master=False)
        self.assertThat(RegionController.objects.all(), HasLength(1))

    def test_creates_maas_id_file(self):
        self.assertIsNone(MAAS_ID.get())
        with post_commit_hooks:
            start_up.inner_start_up(master=False)
        self.assertIsNotNone(MAAS_ID.get())

    def test_creates_maas_uuid(self):
        self.assertIsNone(MAAS_ID.get())
        with post_commit_hooks:
            start_up.inner_start_up(master=False)
        self.assertIsNotNone(Config.objects.get_config("uuid"))

    def test_sets_maas_uuid(self):
        self.assertIsNone(MAAS_ID.get())
        with post_commit_hooks:
            start_up.inner_start_up(master=False)
        self.assertIsNotNone(MAAS_ID.get())

    def test_syncs_deprecation_notifications(self):
        Notification(ident="deprecation_test", message="some text").save()
        with post_commit_hooks:
            start_up.inner_start_up(master=True)
        # existing deprecations are removed since none is active
        self.assertEqual(
            Notification.objects.filter(
                ident__startswith="deprecation_"
            ).count(),
            0,
        )

    def test_logs_deprecation_notifications(self):
        self.patch(deprecations, "postgresql_major_version").return_value = 12
        mock_log = self.patch(start_up, "log")
        with post_commit_hooks:
            start_up.inner_start_up(master=True)
        mock_log.msg.assert_called_once()

    def test_updates_version(self):
        with post_commit_hooks:
            start_up.inner_start_up()
        region = RegionController.objects.first()
        self.assertEqual(region.version, "1:3.1.0-1234-g.deadbeef")
        self.assertEqual(region.info.install_type, "deb")

    def test_sets_vault_flag_disabled(self):
        self.patch(start_up, "get_region_vault_client").return_value = None
        with post_commit_hooks:
            start_up.inner_start_up(master=True)

        region = RegionController.objects.first()
        controller = ControllerInfo.objects.get(node_id=region.id)
        self.assertFalse(controller.vault_configured)

    def test_sets_vault_flag_enabled(self):
        self.patch(start_up, "get_region_vault_client").return_value = object()
        self.patch(start_up, "migrate_db_credentials_if_necessary")
        with post_commit_hooks:
            start_up.inner_start_up(master=True)

        region = RegionController.objects.first()
        controller = ControllerInfo.objects.get(node_id=region.id)
        self.assertTrue(controller.vault_configured)

    def test_migrates_db_credentials_when_configured(self):
        self.patch(start_up, "get_region_vault_client").return_value = object()
        migrate_mock = self.patch(
            start_up, "migrate_db_credentials_if_necessary"
        )

        with post_commit_hooks:
            start_up.inner_start_up(master=True)

        migrate_mock.assert_called_once()

    def test_does_not_migrate_db_credentials_when_not_configured(self):
        self.patch(start_up, "get_region_vault_client").return_value = None
        migrate_mock = self.patch(
            start_up, "migrate_db_credentials_if_necessary"
        )

        with post_commit_hooks:
            start_up.inner_start_up(master=True)

        migrate_mock.assert_not_called()


class TestVaultMigrateDbCredentials(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        self.creds_path = factory.make_name("uuid")
        self.patch(
            start_up, "get_db_creds_vault_path"
        ).return_value = self.creds_path

    def test_does_nothing_when_on_disk_and_vault_disabled(self):
        db_name = factory.make_name("uuid")
        self.useFixture(RegionConfigurationFixture(database_name=db_name))

        client = MagicMock()
        Config.objects.set_config("vault_enabled", False)
        migrate_db_credentials_if_necessary(client)
        client.assert_not_called()
        with RegionConfiguration.open() as config:
            self.assertEqual(db_name, config.database_name)

    def test_does_nothing_when_not_on_disk_and_vault_enabled(self):
        self.useFixture(RegionConfigurationFixture(database_name=""))

        client = MagicMock()
        Config.objects.set_config("vault_enabled", True)
        migrate_db_credentials_if_necessary(client)
        Config.objects.set_config("vault_enabled", False)
        client.assert_not_called()
        with RegionConfiguration.open() as config:
            self.assertEqual("", config.database_name)

    def test_migrates_to_vault_when_on_disk_and_vault_enabled(self):
        db_name = factory.make_name("uuid")
        db_user = factory.make_name("uuid")
        db_pass = factory.make_name("uuid")
        self.useFixture(
            RegionConfigurationFixture(
                database_name=db_name,
                database_user=db_user,
                database_pass=db_pass,
            )
        )

        client = MagicMock()
        Config.objects.set_config("vault_enabled", True)
        migrate_db_credentials_if_necessary(client)
        Config.objects.set_config("vault_enabled", False)
        client.set.assert_called_once_with(
            self.creds_path,
            {"name": db_name, "user": db_user, "pass": db_pass},
        )
        with RegionConfiguration.open() as config:
            self.assertEqual("", config.database_name)
            self.assertEqual("", config.database_user)
            self.assertEqual("", config.database_pass)

    def test_retain_creds_on_disk_when_migration_to_vault_fails(self):
        db_name = factory.make_name("uuid")
        db_user = factory.make_name("uuid")
        db_pass = factory.make_name("uuid")
        self.useFixture(
            RegionConfigurationFixture(
                database_name=db_name,
                database_user=db_user,
                database_pass=db_pass,
            )
        )

        client = MagicMock()
        client.set.side_effect = [VaultError()]
        Config.objects.set_config("vault_enabled", True)
        self.assertRaises(
            VaultError, migrate_db_credentials_if_necessary, client
        )
        Config.objects.set_config("vault_enabled", False)
        with RegionConfiguration.open() as config:
            self.assertEqual(db_name, config.database_name)
            self.assertEqual(db_user, config.database_user)
            self.assertEqual(db_pass, config.database_pass)

    def test_migrates_to_disk_when_not_on_disk_and_vault_disabled(self):
        db_name = factory.make_name("uuid")
        db_user = factory.make_name("uuid")
        db_pass = factory.make_name("uuid")
        self.useFixture(
            RegionConfigurationFixture(
                database_name="",
                database_user="",
                database_pass="",
            )
        )

        def get_side_effect(path):
            if path == self.creds_path:
                return {"name": db_name, "user": db_user, "pass": db_pass}
            raise UnknownSecretPath(path)

        client = MagicMock()
        client.get.side_effect = get_side_effect
        Config.objects.set_config("vault_enabled", False)
        migrate_db_credentials_if_necessary(client)
        client.get.assert_called_once_with(self.creds_path)
        with RegionConfiguration.open() as config:
            self.assertEqual(db_name, config.database_name)
            self.assertEqual(db_user, config.database_user)
            self.assertEqual(db_pass, config.database_pass)
        client.delete.assert_called_once_with(self.creds_path)

    def test_retain_creds_in_vault_when_config_save_fails(self):
        db_name = factory.make_name("uuid")
        db_user = factory.make_name("uuid")
        db_pass = factory.make_name("uuid")
        self.useFixture(
            RegionConfigurationFixture(
                database_name="",
                database_user="",
                database_pass="",
            )
        )

        client = MagicMock()
        client.get.return_value = {
            "name": db_name,
            "user": db_user,
            "pass": db_pass,
        }
        Config.objects.set_config("vault_enabled", False)
        exc = factory.make_exception()
        self.patch(ConfigurationFile, "save").side_effect = exc
        self.assertRaises(
            type(exc), migrate_db_credentials_if_necessary, client
        )
        with RegionConfiguration.open() as config:
            self.assertEqual("", config.database_name)
            self.assertEqual("", config.database_user)
            self.assertEqual("", config.database_pass)
        client.delete.assert_not_called()
