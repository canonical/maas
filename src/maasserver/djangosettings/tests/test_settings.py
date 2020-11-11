# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the maas package."""


import os
import types

from django.db import connections
from psycopg2.extensions import ISOLATION_LEVEL_REPEATABLE_READ
from testtools import TestCase
from testtools.matchers import ContainsDict, Equals, Is

from maasserver.djangosettings import find_settings, import_settings
from maasserver.djangosettings.settings import (
    _get_local_timezone,
    _read_timezone,
)
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.factory import factory


class TestSettingsHelpers(MAASServerTestCase):
    """Test Django settings helper functions."""

    def test_find_settings(self):
        # find_settings() returns a dict of settings from a Django-like
        # settings file. It excludes settings beginning with underscores.
        module = types.ModuleType("example")
        module.SETTING = factory.make_string()
        module._NOT_A_SETTING = factory.make_string()
        expected = {"SETTING": module.SETTING}
        observed = find_settings(module)
        self.assertEqual(expected, observed)

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
        self.assertEqual(expected, observed)


class TestDatabaseConfiguration(MAASServerTestCase):
    def test_atomic_requests_are_enabled(self):
        # ATOMIC_REQUESTS *must* be set for the default connection.
        self.assertThat(
            connections.databases,
            ContainsDict(
                {"default": ContainsDict({"ATOMIC_REQUESTS": Is(True)})}
            ),
        )

    def test_isolation_level_is_serializable(self):
        # Transactions *must* be SERIALIZABLE for the default connection.
        self.assertThat(
            connections.databases,
            ContainsDict(
                {
                    "default": ContainsDict(
                        {
                            "OPTIONS": ContainsDict(
                                {
                                    "isolation_level": Equals(
                                        ISOLATION_LEVEL_REPEATABLE_READ
                                    )
                                }
                            )
                        }
                    )
                }
            ),
        )


class TestTimezoneSettings(TestCase):
    def test_etc_timezone_exists(self):
        self.assertTrue(
            os.path.isfile("/etc/timezone"),
            "If this assert fails, that means /etc/timezone was removed from "
            "Ubuntu, and we need to use systemd APIs to get it instead.",
        )

    def test_read_timezone(self):
        timezone = _read_timezone()
        self.assertIsNotNone(timezone)
        self.assertTrue(
            os.path.isfile(
                os.path.join("/", "usr", "share", "zoneinfo", timezone)
            )
        )

    def get_local_timezone_falls_back_to_utc(self):
        # Force the file open to fail by passing an empty filename.
        timezone = _get_local_timezone(tzfilename="")
        self.assertTrue(timezone, Equals("UTC"))
