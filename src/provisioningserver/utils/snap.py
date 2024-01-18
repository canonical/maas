# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Snap utilities."""

import dataclasses
from functools import total_ordering
import os
from pathlib import Path
import re
from typing import NamedTuple, Optional

import yaml

from provisioningserver.enum import CONTROLLER_INSTALL_TYPE
from provisioningserver.utils.shell import run_command


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


@total_ordering
@dataclasses.dataclass
class SnapChannel:
    """A snap channel."""

    track: str
    risk: str = "stable"
    branch: str = ""

    RISK_ORDER = ("stable", "beta", "candidate", "edge")

    _release_branch = re.compile("ubuntu-[0-9]{2}.[0-9]{2}$")

    @classmethod
    def from_string(cls, string) -> "SnapChannel":
        """Return a SnapChannel from a Channel string."""
        return cls(*string.split("/"))

    def is_release_branch(self) -> bool:
        """Whether the channel points to an Ubuntu release branch."""
        return bool(self._release_branch.match(self.branch))

    def __str__(self):
        tokens = []
        for field in dataclasses.fields(self):
            value = getattr(self, field.name)
            if value:
                tokens.append(value)
        return "/".join(tokens)

    def __lt__(self, other):
        return self._comparable < other._comparable

    @property
    def _comparable(self):
        """Return a tuple that can be used in comparison operators."""
        if self.track == "latest":
            track = (10000, 10000)  # make this the highest version
        else:
            track = tuple(int(token) for token in self.track.split("."))

        risk = self.RISK_ORDER.index(self.risk)
        # consider the following ascending order for branches:
        #  - no branch
        #  - generic branch
        #  - release branch (ubuntu-XX.YY), in release order
        if self.branch and not self.is_release_branch():
            # make it higher than empty but lower than a release branch
            branch = "branch"
        else:
            branch = self.branch

        return track, risk, branch


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
    if snap_paths.common is None:
        return None
    path = snap_paths.common / "snap_mode"
    if not path.exists():
        return None
    mode = path.read_text().strip()
    if mode == "none":
        return None
    return mode


@dataclasses.dataclass
class SnapVersionsInfo:
    """Information about snap versions."""

    install_type = CONTROLLER_INSTALL_TYPE.SNAP

    current: SnapVersion
    channel: Optional[SnapChannel] = None
    update: Optional[SnapVersion] = None
    cohort: str = ""

    def __post_init__(self):
        # deserialize nested dataclasses, if needed
        if isinstance(self.current, dict):
            self.current = SnapVersion(**self.current)
        if isinstance(self.channel, dict):
            self.channel = SnapChannel(**self.channel)
        if isinstance(self.update, dict):
            self.update = SnapVersion(**self.update)


def get_snap_versions_info() -> Optional[SnapVersionsInfo]:
    """Return versions information for current snap and update."""
    if not running_in_snap():
        return None

    versions = SnapVersionsInfo(current=get_snap_version())

    result = run_command("snapctl", "refresh", "--pending")
    if result.returncode == 0:
        refresh_info = yaml.safe_load(result.stdout)
        if "channel" in refresh_info:
            versions.channel = SnapChannel.from_string(refresh_info["channel"])
        if "version" in refresh_info:
            versions.update = SnapVersion(
                revision=str(refresh_info["revision"]),
                version=refresh_info["version"],
            )
        versions.cohort = refresh_info.get("cohort", "")
    return versions
