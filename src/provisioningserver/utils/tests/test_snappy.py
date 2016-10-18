# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for snappy utilities."""

__all__ = []

import os

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.utils import snappy
import yaml


class TestSnappyUtils(MAASTestCase):

    def test_running_in_snap_returns_True(self):
        self.patch(os, "environ", {
            "SNAP": factory.make_name()
        })
        self.assertTrue(snappy.running_in_snap())

    def test_running_in_snap_returns_False(self):
        self.patch(os, "environ", {})
        self.assertFalse(snappy.running_in_snap())

    def test_get_snap_path_returns_path(self):
        path = factory.make_name()
        self.patch(os, "environ", {
            "SNAP": path
        })
        self.assertEqual(path, snappy.get_snap_path())

    def test_get_snap_path_returns_None(self):
        self.patch(os, "environ", {})
        self.assertIsNone(snappy.get_snap_path())

    def test_get_snap_data_path_returns_path(self):
        path = factory.make_name()
        self.patch(os, "environ", {
            "SNAP_DATA": path
        })
        self.assertEqual(path, snappy.get_snap_data_path())

    def test_get_snap_data_path_returns_None(self):
        self.patch(os, "environ", {})
        self.assertIsNone(snappy.get_snap_data_path())

    def test_get_snap_common_path_returns_path(self):
        path = factory.make_name()
        self.patch(os, "environ", {
            "SNAP_COMMON": path
        })
        self.assertEqual(path, snappy.get_snap_common_path())

    def test_get_snap_common_path_returns_None(self):
        self.patch(os, "environ", {})
        self.assertIsNone(snappy.get_snap_common_path())

    def test_get_snap_version_returns_None_when_no_snap(self):
        self.patch(snappy, "get_snap_path").return_value = None
        self.assertIsNone(snappy.get_snap_version())

    def test_get_snap_version_returns_version_from_meta(self):
        snap_path = self.make_dir()
        os.makedirs(os.path.join(snap_path, "meta"))
        snap_yaml = {
            "version": factory.make_name("version")
        }
        with open(os.path.join(snap_path, "meta", "snap.yaml"), "w") as fp:
            yaml.dump(snap_yaml, fp)
        self.patch(snappy, "get_snap_path").return_value = snap_path
        self.assertEqual(snap_yaml['version'], snappy.get_snap_version())
