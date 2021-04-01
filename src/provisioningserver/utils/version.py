# Copyright 2015-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Version utilities."""

import dataclasses
from functools import lru_cache, total_ordering
import re

import pkg_resources

from provisioningserver.logger import get_maas_logger
from provisioningserver.utils import shell, snap

maaslog = get_maas_logger("version")

# the first requirement is always the required package itself
DISTRIBUTION = pkg_resources.require("maas")[0]


# Only import apt_pkg and initialize when not running in a snap.
if not snap.running_in_snap():
    import apt_pkg

    apt_pkg.init()

# Name of maas package to get version from.
REGION_PACKAGE_NAME = "maas-region-api"
RACK_PACKAGE_NAME = "maas-rack-controller"


@total_ordering
@dataclasses.dataclass(frozen=True)
class MAASVersion:
    """Details about MAAS version."""

    major: int
    minor: int
    point: int
    qualifier_type: str
    qualifier_version: int
    revno: int
    git_rev: str

    def __str__(self):
        version = self.short_version
        if self.extended_info:
            version += f"-{self.extended_info}"
        return version

    def __lt__(self, other):
        # only take into account numeric fields for comparison
        return (
            self.major,
            self.minor,
            self.point,
            self._qualifier_type_order,
            self.qualifier_version,
            self.revno,
        ) < (
            other.major,
            other.minor,
            other.point,
            other._qualifier_type_order,
            other.qualifier_version,
            other.revno,
        )

    @property
    def short_version(self) -> str:
        version = f"{self.major}.{self.minor}.{self.point}"
        if self.qualifier_type:
            version += f"~{self.qualifier_type}{self.qualifier_version or ''}"
        return version

    @property
    def extended_info(self) -> str:
        """Additional version string. Contains git commit details."""
        info = ""
        if self.revno:
            info += str(self.revno)
        if self.git_rev:
            info += f"-g.{self.git_rev}"
        return info

    @classmethod
    def from_string(cls, version: str):
        r = re.compile(
            r"((?P<epoch>\d+):)?"  # deb package epoch
            r"(?P<major>\d+)\.(?P<minor>\d+)\.(?P<point>\d+)"
            r"(~?(?P<qualifier_type>[a-z]+)(?P<qualifier_version>\d+))?"
            r"(-(?P<revno>\d+))?"  # number of commits in tree
            r"(-g\.?(?P<git_rev>\w+))?"  # git short hash
        )
        groups = r.match(version).groupdict()

        def to_int(field_name):
            return int(groups.get(field_name) or 0)

        def to_str(field_name):
            return groups.get(field_name) or ""

        return cls(
            int(groups["major"]),
            int(groups["minor"]),
            int(groups["point"]),
            groups["qualifier_type"],
            to_int("qualifier_version"),
            to_int("revno"),
            to_str("git_rev"),
        )

    @property
    def _qualifier_type_order(self) -> int:
        """Return an integer for qualifier type ordering."""
        qualifier_types = {"rc": -1, "beta": -2, "alpha": -3}
        return qualifier_types.get(self.qualifier_type, 0)


@lru_cache(maxsize=1)
def get_running_version() -> MAASVersion:
    """Return the version for the running MAAS."""
    git_rev = None
    revno = 0

    if snap.running_in_snap():
        version_str = snap.get_snap_version().version
    else:
        version_str = _get_version_from_apt(
            RACK_PACKAGE_NAME, REGION_PACKAGE_NAME
        )
    if not version_str:
        version_str = _get_version_from_python_package()
        git_rev = _get_maas_repo_hash()
        revno = _get_maas_repo_commit_count()

    maas_version = MAASVersion.from_string(version_str)
    if (not maas_version.git_rev) and git_rev:
        maas_version = dataclasses.replace(maas_version, git_rev=git_rev)
    if (not maas_version.revno) and revno:
        maas_version = dataclasses.replace(maas_version, revno=revno)

    return maas_version


def get_maas_version_track_channel():
    """Return the track/channel where a snap of this version can be found."""
    # if running from source, default to current version
    version = get_running_version()
    risk_map = {"alpha": "edge", "beta": "beta", "rc": "candidate"}
    risk = risk_map.get(version.qualifier_type, "stable")
    return f"{version.major}.{version.minor}/{risk}"


def _get_version_from_python_package():
    """Return a string with the version from the python package."""
    parsed_version = DISTRIBUTION.parsed_version
    str_version = parsed_version.base_version
    # pre is a tuple with qualifier and version, or None
    pre = parsed_version._version.pre
    if pre:
        qualifier, qual_version = pre
        qualifiers = {"a": "alpha", "b": "beta"}
        if qualifier in qualifiers:
            qualifier = qualifiers[qualifier]
        str_version += f"~{qualifier}{qual_version}"
    return str_version


def _get_version_from_apt(*packages):
    """Return the version output from `apt_pkg.Cache` for the given package(s),
    or log an error message if the package data is not valid."""
    try:
        cache = apt_pkg.Cache(None)
    except SystemError:
        maaslog.error(
            "Installed version could not be determined. Ensure "
            "/var/lib/dpkg/status is valid."
        )
        return ""

    version = None
    for package in packages:
        try:
            apt_package = cache[package]
        except KeyError:
            continue
        version = apt_package.current_ver
        # If the version is None or an empty string, try the next package.
        if not version:
            continue
        break

    return version.ver_str if version else ""


def _get_maas_repo_hash():
    """Return the Git hash for this running MAAS.

    :return: A string if MAAS is running from a git working tree, else `None`.
    """
    return _git_cmd("rev-parse", "--short", "HEAD")


def _get_maas_repo_commit_count():
    """Return the number of commit counts in the git tree, or 0 when not in a tree."""
    return _git_cmd("rev-list", "--count") or 0


def _git_cmd(*cmd):
    """Run a git command and return output, or None in case of error."""
    try:
        return (
            shell.call_and_check(["git"] + list(cmd)).decode("ascii").strip()
        )
    except (shell.ExternalProcessError, FileNotFoundError):
        # We may not be in a git repository, or any manner of other errors, or
        # git is not installed.
        return None
