# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Snap utilities."""

import dataclasses
import os
from pathlib import Path
from typing import NamedTuple, Optional


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


@dataclasses.dataclass
class SnapChannel:
    """A snap channel."""

    track: str
    risk: str = "stable"
    branch: str = ""

    def __str__(self):
        tokens = []
        for field in dataclasses.fields(self):
            value = getattr(self, field.name)
            if value:
                tokens.append(value)
        return "/".join(tokens)

    @classmethod
    def from_string(cls, string):
        return cls(*string.split("/"))


@dataclasses.dataclass
class SnapVersion:
    """Information about a snap version."""

    revision: str  # can contain letters (e.g. "x1")
    version: str


def get_snap_version(environ=None) -> Optional[SnapVersion]:
    """Return the running snap version."""
    if environ is None:
        environ = os.environ

    version = environ.get("SNAP_VERSION")
    if not version:
        return None
    return SnapVersion(version=version, revision=environ["SNAP_REVISION"])


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
