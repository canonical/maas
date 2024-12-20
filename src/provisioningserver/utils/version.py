# Copyright 2015-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Version utilities."""

import dataclasses
from functools import lru_cache, total_ordering
from importlib.metadata import distribution
import re
from typing import Optional, Self

from packaging.version import Version

from provisioningserver.utils import deb, shell, snap

DISTRIBUTION = distribution("maas")


@total_ordering
@dataclasses.dataclass(frozen=True)
class MAASVersion:
    """Details about MAAS version."""

    major: int
    minor: int
    point: int
    qualifier_type: Optional[str] = None
    qualifier_version: int = 0
    revno: int = 0
    git_rev: str = ""

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
    def main_version(self) -> Self:
        """Return a MAASVersion up to the qualifier."""
        return MAASVersion(
            self.major,
            self.minor,
            self.point,
            self.qualifier_type,
            self.qualifier_version,
        )

    @property
    def short_version(self) -> str:
        """Version string which includes up to the qualifier."""
        version = f"{self.major}.{self.minor}.{self.point}"
        if self.qualifier_type:
            version += f"~{self.qualifier_type}{self.qualifier_version or ''}"
        return version

    @property
    def extended_info(self) -> str:
        """Additional version string. Contains git commit details."""
        tokens = []
        if self.revno:
            tokens.append(str(self.revno))
        if self.git_rev:
            tokens.append(f"g.{self.git_rev}")
        return "-".join(tokens)

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

    version_str = ""
    if snap.running_in_snap():
        version_str = snap.get_snap_version().version
    else:
        deb_versions = deb.get_deb_versions_info()
        if deb_versions:
            version_str = deb_versions.current.version
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


def get_versions_info():
    """Get a versions info object based on the install type."""
    versions_info = snap.get_snap_versions_info()
    if not versions_info:
        versions_info = deb.get_deb_versions_info()
    return versions_info


def _get_version_from_python_package():
    """Return a string with the version from the python package."""
    parsed_version = Version(DISTRIBUTION.version)
    str_version = parsed_version.base_version
    # pre is a tuple with qualifier and version, or None
    if pre := parsed_version.pre:
        qualifier, qual_version = pre
        qualifiers = {"a": "alpha", "b": "beta"}
        if qualifier in qualifiers:
            qualifier = qualifiers[qualifier]
        str_version += f"~{qualifier}{qual_version}"
    return str_version


def _get_maas_repo_hash():
    """Return the Git hash for this running MAAS.

    :return: A string if MAAS is running from a git working tree, else `None`.
    """
    return _git_cmd("rev-parse", "--short", "HEAD")


def _get_maas_repo_commit_count():
    """Return the number of commit counts in the git tree, or 0 when not in a tree."""
    return _git_cmd("rev-list", "--count", "HEAD") or 0


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
