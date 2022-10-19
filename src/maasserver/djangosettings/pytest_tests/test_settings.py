# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the maas package."""


import os
import types
from unittest.mock import MagicMock

from django.core.exceptions import ImproperlyConfigured
from django.db import connections
from hvac.exceptions import InvalidPath, VaultError
from psycopg2.extensions import ISOLATION_LEVEL_REPEATABLE_READ
import pytest

from maasserver import vault
from maasserver.config import RegionConfiguration
from maasserver.djangosettings import find_settings, import_settings, settings
from maasserver.djangosettings.settings import (
    _get_default_db_config,
    _get_local_timezone,
    _read_timezone,
)
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

    def test_isolation_level_is_serializable(self):
        # Transactions *must* be SERIALIZABLE for the default connection.
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

    def get_local_timezone_falls_back_to_utc(self):
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
    def _call_with_vault_migrated_region_config(self):
        return _get_default_db_config(
            RegionConfiguration(
                {
                    "database_name": "",
                    "database_user": "127.0.0.1",
                    "database_pass": factory.make_name("uuid"),
                }
            )
        )

    def test_uses_values_from_local_config_when_provided(self, mocker):
        get_vault_mock = mocker.patch.object(vault, "get_region_vault_client")
        get_vault_mock.return_value = MagicMock()
        regionconfig = RegionConfiguration(
            {
                "database_name": "postgres",
                "database_user": factory.make_name("uuid"),
                "database_pass": factory.make_name("uuid"),
            }
        )

        _get_default_db_config(regionconfig)
        get_vault_mock.assert_not_called()

    def test_uses_vault_when_database_name_is_empty_and_vault_is_configured(
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
            raise InvalidPath()

        vault_client.get.side_effect = side_effect
        get_vault_mock = mocker.patch.object(
            settings, "get_region_vault_client"
        )
        get_vault_mock.return_value = vault_client

        observed = self._call_with_vault_migrated_region_config()
        get_vault_mock.assert_called_once()
        assert observed["NAME"] == expected["name"]
        assert observed["USER"] == expected["user"]
        assert observed["PASSWORD"] == expected["pass"]

    def test_raises_when_database_name_is_empty_and_credentials_not_found_in_vault(
        self, mocker, db_creds_vault_path
    ):
        vault_client = MagicMock()
        vault_client.get.side_effect = [InvalidPath()]
        get_vault_mock = mocker.patch.object(
            settings, "get_region_vault_client"
        )
        get_vault_mock.return_value = vault_client

        with pytest.raises(
            ImproperlyConfigured, match="credentials were not found"
        ):
            self._call_with_vault_migrated_region_config()

        get_vault_mock.assert_called_once()

    def test_raises_when_database_name_is_empty_and_no_vault_available(
        self, mocker
    ):
        get_vault_mock = mocker.patch.object(
            settings, "get_region_vault_client"
        )
        get_vault_mock.return_value = None

        with pytest.raises(
            ImproperlyConfigured, match="Vault is not configured"
        ):
            self._call_with_vault_migrated_region_config()

        get_vault_mock.assert_called_once()

    def test_reraises_vault_exceptions(self, mocker, db_creds_vault_path):
        vault_client = MagicMock()
        vault_client.get.side_effect = [VaultError()]
        get_vault_mock = mocker.patch.object(
            settings, "get_region_vault_client"
        )
        get_vault_mock.return_value = vault_client

        with pytest.raises(VaultError):
            self._call_with_vault_migrated_region_config()

        get_vault_mock.assert_called_once()
