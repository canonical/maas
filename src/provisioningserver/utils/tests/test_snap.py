# Copyright 2016-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import os
from pathlib import Path

from fixtures import EnvironmentVariable

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.utils.snap import (
    get_snap_mode,
    get_snap_version,
    running_in_snap,
    SnapChannel,
    SnapPaths,
    SnapVersion,
)


class TestSnapPaths(MAASTestCase):
    def test_from_environ_no_env(self):
        paths = SnapPaths.from_environ(environ={})
        self.assertIsNone(paths.snap)
        self.assertIsNone(paths.common)
        self.assertIsNone(paths.data)

    def test_from_environ(self):
        paths = SnapPaths.from_environ(
            environ={
                "SNAP": "/snap/base",
                "SNAP_COMMON": "/snap/common",
                "SNAP_DATA": "/snap/data",
            }
        )
        self.assertEqual(paths.snap, Path("/snap/base"))
        self.assertEqual(paths.common, Path("/snap/common"))
        self.assertEqual(paths.data, Path("/snap/data"))


class TestRunningInSnap(MAASTestCase):
    def test_in_snap(self):
        self.patch(os, "environ", {"SNAP": factory.make_name()})
        self.assertTrue(running_in_snap())

    def test_not_in_snap(self):
        self.patch(os, "environ", {})
        self.assertFalse(running_in_snap())


class TestSnapChannel(MAASTestCase):
    def test_str_default(self):
        self.assertEqual(str(SnapChannel(track="latest")), "latest/stable")

    def test_str_no_branch(self):
        self.assertEqual(
            str(SnapChannel(track="2.0", risk="beta")), "2.0/beta"
        )

    def test_str_with_branch(self):
        self.assertEqual(
            str(SnapChannel(track="2.0", risk="beta", branch="test")),
            "2.0/beta/test",
        )

    def test_from_string_no_branch(self):
        self.assertEqual(
            SnapChannel.from_string("2.0/beta"),
            SnapChannel(track="2.0", risk="beta"),
        )

    def test_from_string_with_branch(self):
        self.assertEqual(
            SnapChannel.from_string("2.0/beta/test"),
            SnapChannel(track="2.0", risk="beta", branch="test"),
        )


class TestGetSnapVersion(MAASTestCase):
    def test_get_snap_version_None_when_no_snap(self):
        self.assertIsNone(get_snap_version(environ={}))

    def test_get_snap_version(self):
        environ = {
            "SNAP_VERSION": "3.0.0-456-g.deadbeef",
            "SNAP_REVISION": "1234",
        }
        self.assertEqual(
            get_snap_version(environ=environ),
            SnapVersion(
                version="3.0.0-456-g.deadbeef",
                revision="1234",
            ),
        )


class TestGetSnapMode(MAASTestCase):
    def _write_snap_mode(self, mode):
        snap_common_path = Path(self.make_dir())
        snap_mode_path = snap_common_path.joinpath("snap_mode")
        if mode is not None:
            snap_mode_path.write_text(mode, "utf-8")
        self.useFixture(
            EnvironmentVariable("SNAP_COMMON", str(snap_common_path))
        )

    def test_get_snap_mode_no_mode(self):
        self._write_snap_mode(None)
        self.assertIsNone(get_snap_mode())

    def test_get_snap_mode_mode_none(self):
        self._write_snap_mode("none")
        self.assertIsNone(get_snap_mode())

    def test_get_snap_mode_mode_other(self):
        self._write_snap_mode("rack+region")
        self.assertEqual(get_snap_mode(), "rack+region")
