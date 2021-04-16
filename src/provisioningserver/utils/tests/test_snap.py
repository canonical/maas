# Copyright 2016-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import json
import os
from pathlib import Path

from fixtures import EnvironmentVariable

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.utils.snap import (
    get_snap_mode,
    get_snap_version,
    get_snap_versions_info,
    running_in_snap,
    SnapChannel,
    SnapPaths,
    SnapVersion,
    SnapVersionsInfo,
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


class TestSnapVersionsInfo(MAASTestCase):
    def test_deserialize(self):
        info = SnapVersionsInfo(
            current={
                "revision": "1234",
                "version": "3.0.0~alpha1-111-g.deadbeef",
            },
            channel={"track": "3.0", "risk": "stable"},
            update={
                "revision": "5678",
                "version": "3.0.0~alpha2-222-g.cafecafe",
            },
        )
        self.assertEqual(
            info.current,
            SnapVersion(
                revision="1234", version="3.0.0~alpha1-111-g.deadbeef"
            ),
        )
        self.assertEqual(info.channel, SnapChannel(track="3.0"))
        self.assertEqual(
            info.update,
            SnapVersion(
                revision="5678", version="3.0.0~alpha2-222-g.cafecafe"
            ),
        )


class TestGetSnapVersionsInfo(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.patch(
            os,
            "environ",
            {
                "SNAP_REVISION": "1234",
                "SNAP_VERSION": "3.0.0~alpha1-111-g.deadbeef",
            },
        )

    def test_get_snap_versions_info_no_file(self):
        versions = get_snap_versions_info(Path("/not/here"))
        self.assertEqual(
            versions,
            SnapVersionsInfo(
                current=SnapVersion(
                    revision="1234", version="3.0.0~alpha1-111-g.deadbeef"
                ),
                channel=None,
                update=None,
                cohort="",
            ),
        )

    def test_get_snap_versions_info(self):
        data = {
            "channel": "3.0/edge/fix-9991",
            "update": {
                "revision": "5678",
                "version": "3.0.0~alpha2-222-g.cafecafe",
            },
            "cohort": "abcd1234",
        }
        path = self.make_file(contents=json.dumps(data))
        versions = get_snap_versions_info(info_file=Path(path))
        self.assertEqual(
            versions,
            SnapVersionsInfo(
                current=SnapVersion(
                    revision="1234", version="3.0.0~alpha1-111-g.deadbeef"
                ),
                channel=SnapChannel(
                    track="3.0", risk="edge", branch="fix-9991"
                ),
                update=SnapVersion(
                    revision="5678", version="3.0.0~alpha2-222-g.cafecafe"
                ),
                cohort="abcd1234",
            ),
        )

    def test_get_snap_version_info_no_update(self):
        data = {
            "channel": "3.0/edge/fix-9991",
        }
        path = self.make_file(contents=json.dumps(data))
        versions = get_snap_versions_info(info_file=Path(path))
        self.assertEqual(
            versions,
            SnapVersionsInfo(
                current=SnapVersion(
                    revision="1234", version="3.0.0~alpha1-111-g.deadbeef"
                ),
                channel=SnapChannel(
                    track="3.0", risk="edge", branch="fix-9991"
                ),
                update=None,
                cohort="",
            ),
        )
