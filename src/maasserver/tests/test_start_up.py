# Copyright 2012-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pathlib import Path
import random
from unittest.mock import call, MagicMock
from uuid import uuid4

from maasserver import deprecations, eventloop, locks, start_up, vault
from maasserver.config import RegionConfiguration
from maasserver.enum import INTERFACE_TYPE, IPADDRESS_TYPE
from maasserver.models import Interface, StaticIPAddress
from maasserver.models.config import Config
from maasserver.models.controllerinfo import ControllerInfo
from maasserver.models.node import RegionController
from maasserver.models.notification import Notification
from maasserver.models.signals import bootsources
from maasserver.secrets import SecretManager, SecretNotFound
from maasserver.start_up import (
    _create_cluster_certificate_if_necessary,
    migrate_db_credentials_if_necessary,
)
from maasserver.testing.config import RegionConfigurationFixture
from maasserver.testing.eventloop import RegionEventLoopFixture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.testing.vault import FakeVaultClient
from maasserver.utils.certificates import (
    generate_ca_certificate,
    generate_signed_certificate,
)
from maasserver.utils.orm import post_commit_hooks
from maasserver.vault import UnknownSecretPath, VaultError
from maastesting import get_testing_timeout
from provisioningserver.certificates import (
    Certificate,
    get_maas_cluster_cert_paths,
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
        self.patch(MAAS_SHARED_SECRET, "_path", lambda: temp_dir / "secret")
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
        inner_start_up.assert_has_calls(
            [call(master=False), call(master=False)]
        )
        # It also slept once, for 3 seconds, between those attempts.
        start_up.pause.assert_called_once_with(3.0)

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
        self.patch(MAAS_SHARED_SECRET, "_path", lambda: temp_dir / "secret")
        MAAS_SECRET.set(factory.make_bytes())
        self.create_cluster_certificate_mock = self.patch(
            start_up, "_create_cluster_certificate_if_necessary"
        )
        self.store_maas_cluster_cert_tuple_mock = self.patch(
            start_up, "store_maas_cluster_cert_tuple"
        )

    def test_calls_dns_kms_setting_changed_if_master(self):
        with post_commit_hooks:
            start_up.inner_start_up(master=True)
        start_up.dns_kms_setting_changed.assert_called_once_with()

    def test_does_not_call_dns_kms_setting_changed_if_not_master(self):
        with post_commit_hooks:
            start_up.inner_start_up(master=False)
        start_up.dns_kms_setting_changed.assert_not_called()

    def test_calls_load_builtin_scripts_if_master(self):
        self.patch_autospec(start_up, "load_builtin_scripts")
        with post_commit_hooks:
            start_up.inner_start_up(master=True)
        start_up.load_builtin_scripts.assert_called_once_with()

    def test_does_not_call_load_builtin_scripts_if_not_master(self):
        self.patch_autospec(start_up, "load_builtin_scripts")
        with post_commit_hooks:
            start_up.inner_start_up(master=False)
        start_up.load_builtin_scripts.assert_not_called()

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
        start_up.dns_kms_setting_changed.assert_not_called()

    def test_creates_region_controller(self):
        self.assertCountEqual(RegionController.objects.all(), [])
        with post_commit_hooks:
            start_up.inner_start_up(master=False)
        self.assertNotEqual(list(RegionController.objects.all()), [])

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
        self.patch(deprecations, "get_deprecations").return_value = []
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
        self.patch(
            deprecations, "get_database_owner"
        ).return_value = "postgres"
        mock_log = self.patch(start_up, "log")
        with post_commit_hooks:
            start_up.inner_start_up(master=True)
        self.assertEqual(mock_log.msg.call_count, 2)

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

    def test_cluster_certificate_is_called_if_master(self):
        with post_commit_hooks:
            start_up.inner_start_up(master=True)
        self.create_cluster_certificate_mock.assert_called_once()

    def test_cluster_certificate_is_not_called_if_not_master(self):
        with post_commit_hooks:
            start_up.inner_start_up(master=False)
        self.create_cluster_certificate_mock.assert_not_called()

    def test_start_up_cleanup_expired_ip_addresses(self):
        # When a host not managed by MAAS requests an IP to the MAAS DHCP server, the rack will notify the region about the
        # event.
        # If the mac_address if the DHCP lease is unknown, the region
        # - creates an interface with type 'unknown'
        # - creates a StaticIPAddress(alloc_type=IPADDRESS_TYPE.DISCOVERED)
        # - attaches the ip address to the interface
        unknown_interface = factory.make_Interface(
            iftype=INTERFACE_TYPE.UNKNOWN,
            name="eth0",
        )

        # We already set the IP to None for testing purposes.
        ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
            ip=None,
            interface=unknown_interface,
        )

        # Create also some other interfaces with IP addresses so to check that they are not deleted by the cleanup procedure.
        for _ in range(5):
            interface = factory.make_Interface()
            factory.make_StaticIPAddress(interface=interface)

        with post_commit_hooks:
            start_up.inner_start_up(master=True)

        assert not Interface.objects.filter(id=unknown_interface.id).exists()
        assert not StaticIPAddress.objects.filter(id=ip.id).exists()
        assert StaticIPAddress.objects.all().count() == 5
        assert Interface.objects.all().count() == 5

    def test_start_up_stores_certificates_on_disk(self):
        with post_commit_hooks:
            start_up.inner_start_up(master=True)

        # The certificates are stored on the disk
        self.store_maas_cluster_cert_tuple_mock.assert_called_once()

    def test_startup_not_storing_certificates_if_exception_is_raised(self):
        self.patch(
            start_up, "initialize_image_storage"
        ).side_effect = factory.make_exception("boom")

        try:
            with post_commit_hooks:
                start_up.inner_start_up(master=True)
        except Exception:
            # The certificates are stored on the disk
            self.store_maas_cluster_cert_tuple_mock.assert_not_called()
        else:
            self.fail("No exceptions were raised.")

    def test_startup_raise_exception_in_post_commit(self):
        self.store_maas_cluster_cert_tuple_mock.side_effect = [
            factory.make_exception("Boom!"),
        ]

        try:
            with post_commit_hooks:
                start_up.inner_start_up(master=True)
        except Exception:
            # Exceptions raised in the post_commit are catchable.
            pass
        else:
            self.fail("No exceptions were raised.")


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


class TestCreateClusterCertificate(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        MAAS_SECRET.set(factory.make_bytes())
        self.useFixture(MAASUUIDFixture(str(uuid4())))

    def test_create_and_store_certificates(self):
        secret_manager = SecretManager()
        # No certificates on the database
        self.assertRaises(
            SecretNotFound,
            secret_manager.get_composite_secret,
            "maas-ca-certificate",
        )
        self.assertRaises(
            SecretNotFound,
            secret_manager.get_composite_secret,
            "cluster-certificate",
        )

        _create_cluster_certificate_if_necessary()

        maasca_secret = secret_manager.get_composite_secret(
            "maas-ca-certificate"
        )
        maasca = Certificate.from_pem(
            maasca_secret["key"],
            maasca_secret["cert"],
        )

        self.assertIsNotNone(maasca.private_key_pem())
        self.assertIsNotNone(maasca.certificate_pem())

        certificate_secret = secret_manager.get_composite_secret(
            "cluster-certificate"
        )
        certificate = Certificate.from_pem(
            certificate_secret["key"],
            certificate_secret["cert"],
        )

        self.assertIsNotNone(certificate.private_key_pem())
        self.assertIsNotNone(certificate.certificate_pem())
        self.assertIsNotNone(certificate.ca_certificates_pem())

    def test_fetch_certificates_from_db(self):
        # No certificates on the disk
        self.assertIsNone(get_maas_cluster_cert_paths())

        # store the certificates on the database
        secret_manager = SecretManager()
        maasca = generate_ca_certificate("maasca")
        secrets = {
            "key": maasca.private_key_pem(),
            "cert": maasca.certificate_pem(),
        }
        secret_manager.set_composite_secret("maas-ca-certificate", secrets)

        cluster_certificate = generate_signed_certificate(maasca, "cluster")
        secrets = {
            "key": cluster_certificate.private_key_pem(),
            "cert": cluster_certificate.certificate_pem(),
            "cacerts": cluster_certificate.ca_certificates_pem(),
        }
        secret_manager.set_composite_secret("cluster-certificate", secrets)

        retrieved_certificate = _create_cluster_certificate_if_necessary()
        self.assertEqual(
            cluster_certificate.private_key_pem().encode(),
            retrieved_certificate.private_key_pem().encode(),
        )
        self.assertEqual(
            cluster_certificate.certificate_pem().encode(),
            retrieved_certificate.certificate_pem().encode(),
        )
        self.assertEqual(
            cluster_certificate.ca_certificates_pem().encode(),
            retrieved_certificate.ca_certificates_pem().encode(),
        )
