# Copyright 2016-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for snappy utilities."""

__all__ = []

import os
from pathlib import Path

from fixtures import EnvironmentVariable
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.utils import snappy
import yaml


class TestSnappyUtils(MAASTestCase):
    def test_running_in_snap_returns_True(self):
        self.patch(os, "environ", {"SNAP": factory.make_name()})
        self.assertTrue(snappy.running_in_snap())

    def test_running_in_snap_returns_False(self):
        self.patch(os, "environ", {})
        self.assertFalse(snappy.running_in_snap())

    def test_get_snap_path_returns_path(self):
        path = factory.make_name()
        self.patch(os, "environ", {"SNAP": path})
        self.assertEqual(path, snappy.get_snap_path())

    def test_get_snap_path_returns_None(self):
        self.patch(os, "environ", {})
        self.assertIsNone(snappy.get_snap_path())

    def test_get_snap_data_path_returns_path(self):
        path = factory.make_name()
        self.patch(os, "environ", {"SNAP_DATA": path})
        self.assertEqual(path, snappy.get_snap_data_path())

    def test_get_snap_data_path_returns_None(self):
        self.patch(os, "environ", {})
        self.assertIsNone(snappy.get_snap_data_path())

    def test_get_snap_common_path_returns_path(self):
        path = factory.make_name()
        self.patch(os, "environ", {"SNAP_COMMON": path})
        self.assertEqual(path, snappy.get_snap_common_path())

    def test_get_snap_common_path_returns_None(self):
        self.patch(os, "environ", {})
        self.assertIsNone(snappy.get_snap_common_path())

    def test_get_snap_version_returns_None_when_no_snap(self):
        self.patch(snappy, "get_snap_path").return_value = None
        self.assertIsNone(snappy.get_snap_version())

    def _get_snap_version(self, snap_yaml):
        """Arrange for `snap_yaml` to be loaded by `get_snap_version`.

        Puts `snap_yaml` at $tmpdir/meta/snap.yaml, sets SNAP=$tmpdir in the
        environment, then calls `get_snap_version`.
        """
        snap_path = Path(self.make_dir())
        snap_yaml_path = snap_path.joinpath("meta", "snap.yaml")
        snap_yaml_path.parent.mkdir()
        snap_yaml_path.write_text(snap_yaml, "utf-8")
        with EnvironmentVariable("SNAP", str(snap_path)):
            return snappy.get_snap_version()

    def test_get_snap_version_returns_version_from_meta(self):
        version = factory.make_name("version")
        snap_yaml = yaml.safe_dump({"version": version})
        self.assertEqual(version, self._get_snap_version(snap_yaml))

    def test_get_snap_version_loads_yaml_safely(self):
        snap_yaml = "version: !!python/object/apply:os.getcwd []"
        # The YAML with unsafe !!python notation can be loaded.
        yaml_load_unsafe = getattr(yaml, "load")  # Avoid tripping alarms.
        self.assertEqual({"version": os.getcwd()}, yaml_load_unsafe(snap_yaml))
        # However, it will not be loaded by get_snap_version.
        self.assertRaises(yaml.YAMLError, self._get_snap_version, snap_yaml)
