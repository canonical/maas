# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Snap utilities."""

import os
from pathlib import Path
from typing import NamedTuple, Optional

import yaml


def running_in_snap():
    """Return True if running in a snap."""
    return "SNAP" in os.environ


class SnapPaths(NamedTuple):
    """Paths inside a snap."""

    snap: Optional[Path] = None
    common: Optional[Path] = None
    data: Optional[Path] = None

    @classmethod
    def from_environ(cls, environ=None):
        """Return snap paths from the environment."""
        if environ is None:
            environ = os.environ
        var_map = {
            "snap": "SNAP",
            "common": "SNAP_COMMON",
            "data": "SNAP_DATA",
        }
        args = {}
        for key, var in var_map.items():
            value = environ.get(var, None)
            if value:
                value = Path(value)
            args[key] = value
        return cls(**args)


def get_snap_version():
    """Return the version string in the snap metadata."""
    snap_paths = SnapPaths.from_environ()
    if not snap_paths.snap:
        return None

    with (snap_paths.snap / "meta/snap.yaml").open() as fp:
        snap_meta = yaml.safe_load(fp)
    return snap_meta["version"]


def get_snap_mode():
    """Return the snap mode."""
    snap_paths = SnapPaths.from_environ()
    path = snap_paths.common / "snap_mode"
    if not path.exists():
        return None
    mode = path.read_text().strip()
    if mode == "none":
        return None
    return mode
