# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the maas package."""

import os
import types
from unittest.mock import MagicMock

from django.core.exceptions import ImproperlyConfigured
from django.db import connections
from psycopg2.extensions import ISOLATION_LEVEL_REPEATABLE_READ
import pytest

from maasserver.config import RegionConfiguration
from maasserver.djangosettings import find_settings, import_settings, settings
from maasserver.djangosettings.settings import (
    _get_default_db_config,
    _get_local_timezone,
    _read_timezone,
)
from maasserver.vault import UnknownSecretPath, VaultError
from maastesting.factory import factory


class TestSettingsHelpers:
    """Test Django settings helper functions."""

    def test_find_settings(self):
        # find_settings() returns a dict of settings from a Django-like
        # settings file. It excludes settings beginning with underscores.
        module = types.ModuleType("example")
        module.SETTING = factory.make_string()
        module._NOT_A_SETTING = factory.make_string()
        expected = {"SETTING": module.SETTING}
        observed = find_settings(module)
        assert observed == expected

    def test_import_settings(self):
        # import_settings() copies settings from another module into the
        # caller's global scope.
        source = types.ModuleType("source")
        source.SETTING = factory.make_string()
        target = types.ModuleType("target")
        target._source = source
        target._import_settings = import_settings
        eval("_import_settings(_source)", vars(target))
        expected = {"SETTING": source.SETTING}
        observed = find_settings(target)
        assert observed == expected


class TestDatabaseConfiguration:
    def test_atomic_requests_are_enabled(self):
        # ATOMIC_REQUESTS *must* be set for the default connection.
        assert connections.databases["default"]["ATOMIC_REQUESTS"] is True

    def test_isolation_level_is_repeatable_read(self):
        # Default connection isolation level must be REPEATABLE READ.
        assert (
            connections.databases["default"]["OPTIONS"]["isolation_level"]
            == ISOLATION_LEVEL_REPEATABLE_READ
        )


class TestTimezoneSettings:
    def test_etc_timezone_exists(self):
        assert os.path.isfile("/etc/timezone"), (
            "If this assert fails, that means /etc/timezone was removed from "
            "Ubuntu, and we need to use systemd APIs to get it instead."
        )

    def test_read_timezone(self):
        timezone = _read_timezone()
        assert timezone is not None
        assert os.path.isfile(
            os.path.join("/", "usr", "share", "zoneinfo", timezone)
        )

    def test_local_timezone_falls_back_to_utc(self):
        # Force the file open to fail by passing an empty filename.
        timezone = _get_local_timezone(tzfilename="")
        assert timezone == "UTC"


@pytest.fixture
def db_creds_vault_path(mocker):
    path = factory.make_name("uuid")
    mocker.patch.object(
        settings, "get_db_creds_vault_path"
    ).return_value = path
    yield path


class TestGetDefaultDbConfig:
    def test_uses_local_creds_when_vault_not_configured(self, mocker):
        get_vault_mock = mocker.patch.object(
            settings, "get_region_vault_client"
        )
        get_vault_mock.return_value = None
        config = {
            "database_name": "postgres",
            "database_user": factory.make_name("uuid"),
            "database_pass": factory.make_name("uuid"),
        }

        observed = _get_default_db_config(RegionConfiguration(config))

        get_vault_mock.assert_called_once()
        assert observed["NAME"] == config["database_name"]
        assert observed["USER"] == config["database_user"]
        assert observed["PASSWORD"] == config["database_pass"]

    def test_uses_vault_when_vault_is_configured(
        self, mocker, db_creds_vault_path
    ):
        vault_client = MagicMock()
        expected = {
            "name": factory.make_name("uuid"),
            "user": factory.make_name("uuid"),
            "pass": factory.make_name("uuid"),
        }

        def side_effect(given_path):
            if given_path == db_creds_vault_path:
                return expected
            raise UnknownSecretPath(given_path)

        vault_client.get.side_effect = side_effect
        get_vault_mock = mocker.patch.object(
            settings, "get_region_vault_client"
        )
        get_vault_mock.return_value = vault_client

        observed = _get_default_db_config(RegionConfiguration({}))
        assert observed["NAME"] == expected["name"]
        assert observed["USER"] == expected["user"]
        assert observed["PASSWORD"] == expected["pass"]

    def test_raises_when_vault_db_creds_incomplete(
        self, mocker, db_creds_vault_path
    ):
        vault_client = MagicMock()
        vault_client.get.return_value = {"name": "any", "pass": "any"}
        mocker.patch.object(
            settings, "get_region_vault_client"
        ).return_value = vault_client
        with pytest.raises(ImproperlyConfigured, match="'user'"):
            _get_default_db_config(RegionConfiguration({}))

    def test_uses_local_creds_when_no_creds_in_vault(
        self, mocker, db_creds_vault_path
    ):
        expected = {
            "database_name": "postgres",
            "database_user": factory.make_name("uuid"),
            "database_pass": factory.make_name("uuid"),
        }
        vault_client = MagicMock()
        vault_client.get.side_effect = [UnknownSecretPath("some-path")]
        mocker.patch.object(
            settings, "get_region_vault_client"
        ).return_value = vault_client
        observed = _get_default_db_config(RegionConfiguration(expected))
        assert observed["NAME"] == expected["database_name"]
        assert observed["USER"] == expected["database_user"]
        assert observed["PASSWORD"] == expected["database_pass"]

    def test_uses_local_creds_on_vault_error(
        self, mocker, db_creds_vault_path
    ):
        expected = {
            "database_name": "postgres",
            "database_user": factory.make_name("uuid"),
            "database_pass": factory.make_name("uuid"),
        }
        vault_client = MagicMock()
        vault_client.get.side_effect = [VaultError()]
        mocker.patch.object(
            settings, "get_region_vault_client"
        ).return_value = vault_client
        observed = _get_default_db_config(RegionConfiguration(expected))
        assert observed["NAME"] == expected["database_name"]
        assert observed["USER"] == expected["database_user"]
        assert observed["PASSWORD"] == expected["database_pass"]

    def test_returns_expected_application_name(self, mocker):
        mocker.patch.object(
            settings, "get_region_vault_client"
        ).return_value = None
        maas_id_mock = mocker.patch.object(settings, "MAAS_ID")
        maas_id = factory.make_name("id")
        maas_id_mock.get.return_value = maas_id

        observed = _get_default_db_config(RegionConfiguration({}))
        assert "application_name" in observed["OPTIONS"]
        assert (
            observed["OPTIONS"]["application_name"]
            == f"maas-regiond-{maas_id}"
        )

    def test_returns_random_application_name_with_no_maas_id(self, mocker):
        mocker.patch.object(
            settings, "get_region_vault_client"
        ).return_value = None
        mocker.patch.object(settings, "MAAS_ID").get.return_value = None

        observed = _get_default_db_config(RegionConfiguration({}))
        assert "application_name" in observed["OPTIONS"]
        assert observed["OPTIONS"]["application_name"] == "maas-regiond-NO_ID"

    def test_sslmode_in_options(self, mocker):
        """sslmode must appear in the Django OPTIONS dict."""
        mocker.patch.object(
            settings, "get_region_vault_client"
        ).return_value = None
        config = RegionConfiguration({"database_sslmode": "verify-full"})
        observed = _get_default_db_config(config)
        assert "sslmode" in observed["OPTIONS"]
        assert observed["OPTIONS"]["sslmode"] == "verify-full"

    def test_sslmode_defaults_to_prefer(self, mocker):
        """When database_sslmode is absent from config, OPTIONS.sslmode is 'prefer'."""
        mocker.patch.object(
            settings, "get_region_vault_client"
        ).return_value = None
        observed = _get_default_db_config(RegionConfiguration({}))
        assert observed["OPTIONS"].get("sslmode") == "prefer"

    def test_sslmode_sourced_from_region_configuration(self, mocker):
        """Each valid sslmode value from RegionConfiguration propagates to OPTIONS."""
        mocker.patch.object(
            settings, "get_region_vault_client"
        ).return_value = None
        for mode in (
            "disable",
            "allow",
            "prefer",
            "require",
            "verify-ca",
            "verify-full",
        ):
            config = RegionConfiguration({"database_sslmode": mode})
            observed = _get_default_db_config(config)
            assert observed["OPTIONS"]["sslmode"] == mode, (
                f"Expected OPTIONS.sslmode={mode!r}, "
                f"got {observed['OPTIONS'].get('sslmode')!r}"
            )

    def test_cert_fields_in_options_when_set(self, mocker):
        """Non-empty sslcert/sslkey/sslrootcert appear in OPTIONS."""
        mocker.patch.object(
            settings, "get_region_vault_client"
        ).return_value = None
        config = RegionConfiguration(
            {
                "database_sslcert": "/etc/maas/db.crt",
                "database_sslkey": "/etc/maas/db.key",
                "database_sslrootcert": "/etc/maas/ca.crt",
            }
        )
        observed = _get_default_db_config(config)
        assert observed["OPTIONS"]["sslcert"] == "/etc/maas/db.crt"
        assert observed["OPTIONS"]["sslkey"] == "/etc/maas/db.key"
        assert observed["OPTIONS"]["sslrootcert"] == "/etc/maas/ca.crt"

    def test_cert_fields_absent_from_options_when_empty(self, mocker):
        """Empty cert paths must not appear in OPTIONS (avoids psycopg2 open-file error)."""
        mocker.patch.object(
            settings, "get_region_vault_client"
        ).return_value = None
        observed = _get_default_db_config(RegionConfiguration({}))
        assert "sslcert" not in observed["OPTIONS"]
        assert "sslkey" not in observed["OPTIONS"]
        assert "sslrootcert" not in observed["OPTIONS"]

    def test_rootcert_only_without_client_cert(self, mocker):
        """sslrootcert alone (server verification, no mTLS) is permitted."""
        mocker.patch.object(
            settings, "get_region_vault_client"
        ).return_value = None
        config = RegionConfiguration(
            {"database_sslrootcert": "/etc/maas/ca.crt"}
        )
        observed = _get_default_db_config(config)
        assert observed["OPTIONS"]["sslrootcert"] == "/etc/maas/ca.crt"
        assert "sslcert" not in observed["OPTIONS"]
        assert "sslkey" not in observed["OPTIONS"]
