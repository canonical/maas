# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import io
import os
from pathlib import Path
import sys
from unittest.mock import MagicMock

from fixtures import EnvironmentVariableFixture
import netifaces

from maascli import snap
from maascli.command import CommandError
from maascli.parser import ArgumentParser
import maasserver.vault
from maasserver.vault import VaultError
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase


class TestHelpers(MAASTestCase):
    def setUp(self):
        super().setUp()
        snap_common = self.make_dir()
        snap_data = self.make_dir()
        self.environ = {"SNAP_COMMON": snap_common, "SNAP_DATA": snap_data}
        self.patch(os, "environ", self.environ)

    def test_get_default_gateway_ip_no_defaults(self):
        self.patch(netifaces, "gateways").return_value = {}
        self.assertIsNone(snap.get_default_gateway_ip())

    def test_get_default_gateway_ip_returns_ipv4(self):
        gw_address = factory.make_ipv4_address()
        ipv4_address = factory.make_ipv4_address()
        iface_name = factory.make_name("eth")
        self.patch(netifaces, "gateways").return_value = {
            "default": {netifaces.AF_INET: (gw_address, iface_name)}
        }
        self.patch(netifaces, "ifaddresses").return_value = {
            netifaces.AF_INET: [{"addr": ipv4_address}]
        }
        self.assertEqual(ipv4_address, snap.get_default_gateway_ip())

    def test_get_default_gateway_ip_returns_ipv6(self):
        gw_address = factory.make_ipv6_address()
        ipv6_address = factory.make_ipv6_address()
        iface_name = factory.make_name("eth")
        self.patch(netifaces, "gateways").return_value = {
            "default": {netifaces.AF_INET6: (gw_address, iface_name)}
        }
        self.patch(netifaces, "ifaddresses").return_value = {
            netifaces.AF_INET6: [{"addr": ipv6_address}]
        }
        self.assertEqual(ipv6_address, snap.get_default_gateway_ip())

    def test_get_default_gateway_ip_returns_ipv4_over_ipv6(self):
        gw4_address = factory.make_ipv4_address()
        gw6_address = factory.make_ipv6_address()
        ipv4_address = factory.make_ipv4_address()
        ipv6_address = factory.make_ipv6_address()
        iface = factory.make_name("eth")
        self.patch(netifaces, "gateways").return_value = {
            "default": {
                netifaces.AF_INET: (gw4_address, iface),
                netifaces.AF_INET6: (gw6_address, iface),
            }
        }
        self.patch(netifaces, "ifaddresses").return_value = {
            netifaces.AF_INET: [{"addr": ipv4_address}],
            netifaces.AF_INET6: [{"addr": ipv6_address}],
        }
        self.assertEqual(ipv4_address, snap.get_default_gateway_ip())

    def test_get_default_gateway_ip_returns_first_ip(self):
        gw_address = factory.make_ipv4_address()
        ipv4_address1 = factory.make_ipv4_address()
        ipv4_address2 = factory.make_ipv4_address()
        iface = factory.make_name("eth")
        self.patch(netifaces, "gateways").return_value = {
            "default": {netifaces.AF_INET: (gw_address, iface)}
        }
        self.patch(netifaces, "ifaddresses").return_value = {
            netifaces.AF_INET: [
                {"addr": ipv4_address1},
                {"addr": ipv4_address2},
            ]
        }
        self.assertEqual(ipv4_address1, snap.get_default_gateway_ip())

    def test_get_default_url_uses_gateway_ip(self):
        ipv4_address = factory.make_ipv4_address()
        self.patch(snap, "get_default_gateway_ip").return_value = ipv4_address
        self.assertEqual(
            "http://%s:5240/MAAS" % ipv4_address, snap.get_default_url()
        )

    def test_get_default_url_fallsback_to_localhost(self):
        self.patch(snap, "get_default_gateway_ip").return_value = None
        self.assertEqual("http://localhost:5240/MAAS", snap.get_default_url())

    def test_get_mode_filepath(self):
        self.assertEqual(
            os.path.join(self.environ["SNAP_COMMON"], "snap_mode"),
            snap.get_mode_filepath(),
        )

    def test_get_current_mode_returns_none_when_missing(self):
        self.assertEqual("none", snap.get_current_mode())

    def test_get_current_mode_returns_file_contents(self):
        snap.set_current_mode("all")
        self.assertEqual("all", snap.get_current_mode())

    def test_set_current_mode_creates_file(self):
        snap.set_current_mode("all")
        self.assertTrue(os.path.exists(snap.get_mode_filepath()))

    def test_set_current_mode_overwrites(self):
        snap.set_current_mode("all")
        snap.set_current_mode("none")
        self.assertEqual("none", snap.get_current_mode())


class TestConfigHelpers(MAASTestCase):
    def setUp(self):
        super().setUp()
        maas_data = self.make_dir()
        self.secret_file = Path(maas_data) / "secret"
        self.useFixture(EnvironmentVariableFixture("MAAS_DATA", maas_data))

    def test_print_config_value(self):
        mock_print = self.patch(snap, "print_msg")
        key = factory.make_name("key")
        value = factory.make_name("value")
        config = {key: value}
        snap.print_config_value(config, key)
        mock_print.assert_called_once_with(f"{key}={value}")

    def test_print_config_value_hidden(self):
        mock_print = self.patch(snap, "print_msg")
        key = factory.make_name("key")
        value = factory.make_name("value")
        config = {key: value}
        snap.print_config_value(config, key, hidden=True)
        mock_print.assert_called_once_with(f"{key}=(hidden)")

    def test_get_rpc_secret_returns_secret(self):
        secret = factory.make_string()
        self.secret_file.write_text(secret)
        self.assertEqual(snap.get_rpc_secret(), secret)

    def test_get_rpc_secret_returns_None_when_no_file(self):
        self.assertIsNone(snap.get_rpc_secret())

    def test_get_rpc_secret_returns_None_when_empty_file(self):
        self.secret_file.write_text("")
        self.assertIsNone(snap.get_rpc_secret())

    def test_set_rpc_secret_sets_secret(self):
        secret = factory.make_string()
        snap.set_rpc_secret(secret)
        self.assertEqual(secret, snap.get_rpc_secret())

    def test_set_rpc_secret_clears_secret(self):
        secret = factory.make_string()
        snap.set_rpc_secret(secret)
        snap.set_rpc_secret(None)
        self.assertIsNone(snap.get_rpc_secret())
        self.assertFalse(self.secret_file.exists())


class TestCmdInit(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.parser = ArgumentParser()
        self.cmd = snap.cmd_init(self.parser)
        self.patch(os, "getuid").return_value = 0
        self.snap_common = self.make_dir()
        self.patch(
            os,
            "environ",
            {
                "SNAP": "/snap/maas",
                "SNAP_COMMON": self.snap_common,
                "SNAP_DATA": "/snap/maas/data",
            },
        )
        self.mock_read_input = self.patch(snap, "read_input")

    def test_init_snap_db_options_prompt(self):
        self.mock_maas_configuration = self.patch(snap, "MAASConfiguration")
        self.patch(snap, "set_rpc_secret")
        self.patch(snap.cmd_init, "_finalize_init")

        self.mock_read_input.side_effect = [
            "postgres://maas:pwd@localhost/db",
            "http://localhost:5240/MAAS",
        ]
        options = self.parser.parse_args(["region+rack"])
        self.cmd(options)
        self.mock_maas_configuration().update.assert_called_once_with(
            {
                "maas_url": "http://localhost:5240/MAAS",
                "database_host": "localhost",
                "database_name": "db",
                "database_user": "maas",
                "database_pass": "pwd",
            }
        )

    def test_init_db_parse_error(self):
        self.patch(snap, "print_msg")
        self.mock_maas_configuration = self.patch(snap, "MAASConfiguration")
        self.patch(snap, "set_rpc_secret")
        self.patch(snap.cmd_init, "_finalize_init")

        self.mock_read_input.side_effect = [
            "localhost",
            "db",
            "maas",
            "pwd",
            "http://localhost:5240/MAAS",
        ]
        options = self.parser.parse_args(
            ["region+rack", "--database-uri", "invalid"]
        )
        error = self.assertRaises(CommandError, self.cmd, options)
        self.assertEqual(
            "Database URI needs to be either 'maas-test-db:///' or start "
            "with 'postgres://'",
            str(error),
        )
        self.mock_maas_configuration().update.assert_not_called()

    def test_get_database_settings_no_prompt_dsn(self):
        options = self.parser.parse_args(
            [
                "region+rack",
                "--database-uri",
                "postgres://dbuser:pwd@dbhost/dbname",
            ]
        )
        settings = snap.get_database_settings(options)
        self.assertEqual(
            {
                "database_host": "dbhost",
                "database_name": "dbname",
                "database_user": "dbuser",
                "database_pass": "pwd",
            },
            settings,
        )

    def test_get_database_settings_prompt_dsn(self):
        self.mock_read_input.side_effect = [
            "postgres://dbuser:pwd@dbhost/dbname"
        ]
        options = self.parser.parse_args(["region+rack"])
        settings = snap.get_database_settings(options)
        self.assertEqual(
            {
                "database_host": "dbhost",
                "database_name": "dbname",
                "database_user": "dbuser",
                "database_pass": "pwd",
            },
            settings,
        )

    def test_get_database_settings_maas_test_db_prompt_default(self):
        options = self.parser.parse_args(["region+rack"])
        os.mkdir(os.path.join(self.snap_common, "test-db-socket"))
        self.mock_read_input.side_effect = [""]
        settings = snap.get_database_settings(options)
        self.assertEqual(
            {
                "database_host": f"{self.snap_common}/test-db-socket",
                "database_name": "maasdb",
                "database_user": "maas",
                "database_pass": None,
            },
            settings,
        )

    def test_get_database_settings_maas_test_db_prompt_no_default(self):
        options = self.parser.parse_args(["region+rack"])
        self.mock_read_input.side_effect = ["", "postgres:///?user=foo"]
        settings = snap.get_database_settings(options)
        self.assertEqual(
            {
                "database_host": "localhost",
                "database_name": "foo",
                "database_user": "foo",
                "database_pass": None,
            },
            settings,
        )

    def test_get_database_settings_maas_test_db(self):
        options = self.parser.parse_args(
            ["region+rack", "--database-uri", "maas-test-db:///"]
        )
        settings = snap.get_database_settings(options)
        self.assertEqual(
            {
                "database_host": f"{self.snap_common}/test-db-socket",
                "database_name": "maasdb",
                "database_user": "maas",
                "database_pass": None,
            },
            settings,
        )

    def test_get_database_settings_minimal_postgres(self):
        options = self.parser.parse_args(
            ["region+rack", "--database-uri", "postgres:///?user=myuser"]
        )
        settings = snap.get_database_settings(options)
        self.assertEqual(
            {
                "database_host": "localhost",
                "database_name": "myuser",
                "database_user": "myuser",
                "database_pass": None,
            },
            settings,
        )

    def test_get_database_settings_full_postgres(self):
        options = self.parser.parse_args(
            [
                "region+rack",
                "--database-uri",
                "postgres://myuser:pwd@myhost:1234/mydb",
            ]
        )
        settings = snap.get_database_settings(options)
        self.assertEqual(
            {
                "database_host": "myhost",
                "database_name": "mydb",
                "database_user": "myuser",
                "database_pass": "pwd",
                "database_port": 1234,
            },
            settings,
        )

    def test_get_database_settings_invalid_parameters(self):
        options = self.parser.parse_args(
            [
                "region+rack",
                "--database-uri",
                "postgres://myuser:pwd@myhost:1234/mydb?foo=bar",
            ]
        )
        error = self.assertRaises(
            snap.DatabaseSettingsError, snap.get_database_settings, options
        )
        self.assertEqual(
            "Error parsing database URI: "
            'invalid dsn: invalid URI query parameter: "foo"',
            str(error),
        )

    def test_get_database_settings_unsupported_parameters(self):
        options = self.parser.parse_args(
            [
                "region+rack",
                "--database-uri",
                "postgres://myuser:pwd@myhost/?passfile=foo&options=bar",
            ]
        )
        error = self.assertRaises(
            snap.DatabaseSettingsError, snap.get_database_settings, options
        )
        self.assertEqual(
            "Error parsing database URI: "
            "Unsupported parameters: options, passfile",
            str(error),
        )

    def test_get_database_settings_missing_user(self):
        options = self.parser.parse_args(
            ["region+rack", "--database-uri", "postgres://myhost/"]
        )
        error = self.assertRaises(
            snap.DatabaseSettingsError, snap.get_database_settings, options
        )
        self.assertEqual(
            "No user found in URI: postgres://myhost/", str(error)
        )

    def test_get_database_settings_invalid_maas_test_db(self):
        options = self.parser.parse_args(
            ["region+rack", "--database-uri", "maas-test-db:///foo"]
        )
        error = self.assertRaises(
            snap.DatabaseSettingsError, snap.get_database_settings, options
        )
        self.assertEqual(
            "Database URI needs to be either 'maas-test-db:///' or start with "
            "'postgres://'",
            str(error),
        )

    def test_get_database_settings_incomplete_postgres_uri(self):
        # The URI needs to start with at least postgres:// before we
        # even try to parse it.
        options = self.parser.parse_args(
            ["region+rack", "--database-uri", "postgres:/"]
        )
        error = self.assertRaises(
            snap.DatabaseSettingsError, snap.get_database_settings, options
        )
        self.assertEqual(
            "Database URI needs to be either 'maas-test-db:///' or start with "
            "'postgres://'",
            str(error),
        )

    def test_get_vault_settings_returns_empty_dict_with_no_vault_uri(self):
        options = self.parser.parse_args(
            ["region+rack", "--database-uri", "maas-test-db:///"]
        )
        self.assertEqual(snap.get_vault_settings(options), {})

    def test_get_vault_settings_requires_args_when_vault_uri_provided(self):
        options = self.parser.parse_args(
            [
                "region+rack",
                "--database-uri",
                "maas-test-db:///",
                "--vault-uri",
                "http://vault:8200",
            ]
        )
        self.assertRaises(CommandError, snap.get_vault_settings, options)

    def test_get_vault_settings_returns_default_mount_when_not_specified(self):
        url = "http://vault:8200"
        approle_id = factory.make_name("uuid")
        wrapped_token = factory.make_name("uuid")
        secret_id = factory.make_name("uuid")
        secrets_path = "path"
        options = self.parser.parse_args(
            [
                "region+rack",
                "--database-uri",
                "maas-test-db:///",
                "--vault-uri",
                url,
                "--vault-approle-id",
                approle_id,
                "--vault-wrapped-token",
                wrapped_token,
                "--vault-secrets-path",
                secrets_path,
            ]
        )

        prepare_mock = self.patch(maasserver.vault, "prepare_wrapped_approle")
        prepare_mock.return_value = secret_id

        assert snap.get_vault_settings(options) == {
            "vault_url": url,
            "vault_approle_id": approle_id,
            "vault_secret_id": secret_id,
            "vault_secrets_mount": "secret",
            "vault_secrets_path": secrets_path,
        }
        prepare_mock.assert_called_once_with(
            url=url,
            role_id=approle_id,
            wrapped_token=wrapped_token,
            secrets_path=secrets_path,
            secrets_mount="secret",
        )

    def test_get_vault_settings_returns_mount_when_specified(self):
        url = "http://vault:8200"
        approle_id = factory.make_name("uuid")
        wrapped_token = factory.make_name("uuid")
        secret_id = factory.make_name("uuid")
        secrets_path = "path"
        secrets_mount = "test_mount"
        options = self.parser.parse_args(
            [
                "region+rack",
                "--database-uri",
                "maas-test-db:///",
                "--vault-uri",
                url,
                "--vault-approle-id",
                approle_id,
                "--vault-wrapped-token",
                wrapped_token,
                "--vault-secrets-path",
                secrets_path,
                "--vault-secrets-mount",
                secrets_mount,
            ]
        )

        prepare_mock = self.patch(maasserver.vault, "prepare_wrapped_approle")
        prepare_mock.return_value = secret_id

        assert snap.get_vault_settings(options) == {
            "vault_url": url,
            "vault_approle_id": approle_id,
            "vault_secret_id": secret_id,
            "vault_secrets_mount": secrets_mount,
            "vault_secrets_path": secrets_path,
        }
        prepare_mock.assert_called_once_with(
            url=url,
            role_id=approle_id,
            wrapped_token=wrapped_token,
            secrets_path=secrets_path,
            secrets_mount=secrets_mount,
        )

    def test_get_vault_settings_raises_command_error_for_vault_issues(self):
        url = "http://vault:8200"
        approle_id = factory.make_name("uuid")
        wrapped_token = factory.make_name("uuid")
        secrets_path = "path"
        options = self.parser.parse_args(
            [
                "region+rack",
                "--database-uri",
                "maas-test-db:///",
                "--vault-uri",
                url,
                "--vault-approle-id",
                approle_id,
                "--vault-wrapped-token",
                wrapped_token,
                "--vault-secrets-path",
                secrets_path,
            ]
        )

        prepare_mock = self.patch(maasserver.vault, "prepare_wrapped_approle")
        prepare_mock.side_effect = [VaultError()]

        self.assertRaises(CommandError, snap.get_vault_settings, options)

    def test_get_vault_settings_reraises_unknown_error(self):
        url = "http://vault:8200"
        approle_id = factory.make_name("uuid")
        wrapped_token = factory.make_name("uuid")
        secrets_path = "path"
        options = self.parser.parse_args(
            [
                "region+rack",
                "--database-uri",
                "maas-test-db:///",
                "--vault-uri",
                url,
                "--vault-approle-id",
                approle_id,
                "--vault-wrapped-token",
                wrapped_token,
                "--vault-secrets-path",
                secrets_path,
            ]
        )

        prepare_mock = self.patch(maasserver.vault, "prepare_wrapped_approle")
        exc = factory.make_exception()
        prepare_mock.side_effect = [exc]
        self.assertRaises(type(exc), snap.get_vault_settings, options)


class TestCmdStatus(MAASTestCase):
    def test_requires_root(self):
        parser = ArgumentParser()
        cmd = snap.cmd_status(parser)
        self.patch(os, "getuid").return_value = 1000
        error = self.assertRaises(SystemExit, cmd, parser.parse_args([]))
        self.assertEqual(
            str(error), "The 'status' command must be run by root."
        )


class TestCmdConfig(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.parser = ArgumentParser()
        self.cmd = snap.cmd_config(self.parser)
        self.patch(os, "getuid").return_value = 0
        snap_common = self.make_dir()
        snap_data = self.make_dir()
        self.useFixture(EnvironmentVariableFixture("SNAP_COMMON", snap_common))
        self.useFixture(EnvironmentVariableFixture("SNAP_DATA", snap_data))

    def test_show(self):
        # Regression test for LP:1892868
        stdout = io.StringIO()
        self.patch(sys, "stdout", stdout)
        options = self.parser.parse_args([])
        self.assertIsNone(self.cmd(options))
        self.assertEqual(stdout.getvalue(), "Mode: none\n")

    def test_enable_debugging(self):
        mock_maas_configuration = self.patch(snap, "MAASConfiguration")
        mock_restart_pebble = self.patch(snap, "restart_pebble")
        options = self.parser.parse_args(["--enable-debug"])
        stdout = io.StringIO()
        self.patch(sys, "stdout", stdout)

        self.cmd(options)
        mock_maas_configuration().update.assert_called_once_with(
            {"debug": True}
        )
        # After config is changed, services are restarted
        self.assertEqual(stdout.getvalue(), "Stopping services\n")
        mock_restart_pebble.assert_called_once_with()

    def test_reenable_debugging(self):
        mock_maas_configuration = self.patch(snap, "MAASConfiguration")
        config_manager = mock_maas_configuration()
        mock_restart_pebble = self.patch(snap, "restart_pebble")
        options = self.parser.parse_args(["--enable-debug"])
        stdout = io.StringIO()
        self.patch(sys, "stdout", stdout)

        # Simulate the value already being enabled
        current_config = config_manager.get()
        current_config.get.side_effect = {"debug": True}.__getitem__

        self.cmd(options)
        config_manager.update.assert_not_called()
        self.assertEqual(stdout.getvalue(), "")
        mock_restart_pebble.assert_not_called()


class TestDBNeedInit(MAASTestCase):
    def test_has_tables(self):
        connection = MagicMock()
        connection.introspection.table_names.return_value = [
            "table1",
            "table2",
        ]
        self.assertFalse(snap.db_need_init(connection))

    def test_no_tables(self):
        connection = MagicMock()
        connection.introspection.table_names.return_value = []
        self.assertTrue(snap.db_need_init(connection))

    def test_fail(self):
        connection = MagicMock()
        connection.introspection.table_names.side_effect = Exception(
            "connection failed"
        )
        self.assertTrue(snap.db_need_init(connection))
