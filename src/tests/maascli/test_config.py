# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maascli.config`."""

import contextlib
import os.path
import sqlite3
from unittest import TestCase
from unittest.mock import patch

from twisted.python.filepath import FilePath

from maascli import api
from maastesting.testcase import MAASTestCase


class TestProfileConfig(MAASTestCase):
    """Tests for `ProfileConfig`."""

    def test_init(self):
        database = sqlite3.connect(":memory:")
        config = api.ProfileConfig(database)
        with config.cursor() as cursor:
            # The profiles table has been created.
            self.assertEqual(
                cursor.execute(
                    "SELECT COUNT(*) FROM sqlite_master"
                    " WHERE type = 'table'"
                    "   AND name = 'profiles'"
                ).fetchone(),
                (1,),
            )

    def test_profiles_pristine(self):
        # A pristine configuration has no profiles.
        database = sqlite3.connect(":memory:")
        config = api.ProfileConfig(database)
        self.assertSetEqual(set(), set(config))

    def test_adding_profile(self):
        database = sqlite3.connect(":memory:")
        config = api.ProfileConfig(database)
        config["alice"] = {"abc": 123}
        self.assertEqual({"alice"}, set(config))
        self.assertEqual({"abc": 123}, config["alice"])

    def test_replacing_profile(self):
        database = sqlite3.connect(":memory:")
        config = api.ProfileConfig(database)
        config["alice"] = {"abc": 123}
        config["alice"] = {"def": 456}
        self.assertEqual({"alice"}, set(config))
        self.assertEqual({"def": 456}, config["alice"])

    def test_cache(self):
        database = sqlite3.connect(":memory:")
        config = api.ProfileConfig(database)
        config["alice"] = {"abc": 123}
        with patch.object(config, "cursor") as cursor:
            self.assertEqual({"abc": 123}, config["alice"])
            cursor.assert_not_called()

    def test_getting_profile(self):
        database = sqlite3.connect(":memory:")
        config = api.ProfileConfig(database)
        config["alice"] = {"abc": 123}
        self.assertEqual({"abc": 123}, config["alice"])

    def test_getting_non_existent_profile(self):
        database = sqlite3.connect(":memory:")
        config = api.ProfileConfig(database)
        self.assertRaises(KeyError, lambda: config["alice"])

    def test_removing_profile(self):
        database = sqlite3.connect(":memory:")
        config = api.ProfileConfig(database)
        config["alice"] = {"abc": 123}
        del config["alice"]
        self.assertEqual(set(), set(config))

    def test_open_no_file_fail(self):
        config_file = os.path.join(self.make_dir(), "config")
        with TestCase.assertRaises(self, FileNotFoundError):
            with api.ProfileConfig.open(config_file):
                pass

    def test_open_and_close(self):
        # ProfileConfig.open() returns a context manager that closes the
        # database on exit.
        config_file = os.path.join(self.make_dir(), "config")
        config = api.ProfileConfig.open(config_file, create=True)
        self.assertIsInstance(config, contextlib._GeneratorContextManager)
        with config as config:
            self.assertIsInstance(config, api.ProfileConfig)
            with config.cursor() as cursor:
                self.assertEqual((1,), cursor.execute("SELECT 1").fetchone())
        self.assertRaises(sqlite3.ProgrammingError, config.cursor)

    def test_open_permissions_new_database(self):
        # ProfileConfig.open() applies restrictive file permissions to newly
        # created configuration databases.
        config_file = os.path.join(self.make_dir(), "config")
        with api.ProfileConfig.open(config_file, create=True):
            perms = FilePath(config_file).getPermissions()
            self.assertEqual("rw-------", perms.shorthand())

    def test_open_permissions_existing_database(self):
        # ProfileConfig.open() leaves the file permissions of existing
        # configuration databases.
        config_file = os.path.join(self.make_dir(), "config")
        open(config_file, "wb").close()  # touch.
        os.chmod(config_file, 0o644)  # u=rw,go=r
        with api.ProfileConfig.open(config_file):
            perms = FilePath(config_file).getPermissions()
            self.assertEqual("rw-r--r--", perms.shorthand())
