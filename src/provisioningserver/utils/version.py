# Copyright 2015-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Version utilities."""

__all__ = [
    "get_maas_doc_version",
    "get_maas_version_subversion",
    "get_maas_version_ui",
    "MAASVersion",
]

from collections import namedtuple
from functools import lru_cache
import re

import pkg_resources

from provisioningserver.logger import get_maas_logger
from provisioningserver.utils import shell, snappy

maaslog = get_maas_logger("version")

# the first requirement is always the required package itself
DEFAULT_PARSED_VERSION = pkg_resources.require("maas")[0].parsed_version

DEFAULT_VERSION = str(DEFAULT_PARSED_VERSION)


# Only import apt_pkg and initialize when not running in a snap.
if not snappy.running_in_snap():
    import apt_pkg

    apt_pkg.init()

# Name of maas package to get version from.
REGION_PACKAGE_NAME = "maas-region-api"
RACK_PACKAGE_NAME = "maas-rack-controller"


def get_version_from_apt(*packages):
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
        if package in cache:
            apt_package = cache[package]
            version = apt_package.current_ver
            # If the version is None or an empty string, try the next package.
            if not version:
                continue
            break

    return version.ver_str if version is not None else ""


def extract_version_subversion(version):
    """Return a tuple (version, subversion) from the given apt version."""
    main_version, subversion = re.split("[+|-]", version, 1)
    return main_version, subversion


def get_maas_repo_hash():
    """Return the Git hash for this running MAAS.

    :return: A string if MAAS is running from a git working tree, else `None`.
    """
    try:
        return (
            shell.call_and_check(["git", "rev-parse", "HEAD"])
            .decode("ascii")
            .strip()
        )
    except shell.ExternalProcessError:
        # We may not be in a git repository, or any manner of other errors. For
        # the purposes of this function we don't care; simply say we don't
        # know.
        return None
    except FileNotFoundError:
        # Git is not installed. We don't care and simply say we don't know.
        return None


def get_maas_version_track_channel():
    """Returns the track/channel where a snap of this version can be found."""
    # if running from source, default to current version
    maas_version = get_maas_version() or DEFAULT_VERSION
    version = get_version_tuple(maas_version)
    risk_map = {"alpha": "edge", "beta": "beta", "rc": "candidate"}
    risk = risk_map.get(version.qualifier_type, "stable")
    return f"{version.major}.{version.minor}/{risk}"


MAASVersion = namedtuple(
    "MAASVersion",
    (
        "major",
        "minor",
        "point",
        "qualifier_type_version",
        "qualifier_version",
        "revno",
        "git_rev",
        "short_version",
        "extended_info",
        "qualifier_type",
        "is_snap",
    ),
)


def _coerce_to_int(string: str) -> int:
    """Strips all non-numeric characters out of the string and returns an int.

    Returns 0 for an empty string.
    """
    numbers = re.sub(r"[^\d]+", "", string)
    if len(numbers) > 0:
        return int(numbers)
    else:
        return 0


def get_version_tuple(maas_version: str) -> MAASVersion:
    without_epoch = maas_version.split(":", 1)[-1]
    version_parts = re.split(r"[-|+]", without_epoch, 1)
    short_version = version_parts[0]
    major_minor_point = re.sub(r"~.*", "", short_version).split(".", 2)
    for i in range(3):
        try:
            major_minor_point[i] = _coerce_to_int(major_minor_point[i])
        except ValueError:
            major_minor_point[i] = 0
        except IndexError:
            major_minor_point.append(0)
    major, minor, point = major_minor_point
    extended_info = ""
    if len(version_parts) > 1:
        extended_info = version_parts[1]
    qualifier_type = None
    qualifier_type_version = 0
    qualifier_version = 0
    if "~" in short_version:
        # Parse the alpha/beta/rc version.
        base_version, qualifier = short_version.split("~", 2)
        qualifier_types = {"rc": -1, "beta": -2, "alpha": -3}
        # A release build won't have a qualifier, so its version should be
        # greater than releases qualified with alpha/beta/rc revisions.
        qualifier_type = re.sub(r"[\d]+", "", qualifier)
        qualifier_version = _coerce_to_int(qualifier)
        qualifier_type_version = qualifier_types.get(qualifier_type, 0)
    revno = 0
    git_rev = ""
    # If we find a '-g' or '.g', that means the extended info indicates a
    # git revision.
    if "-g" in extended_info or ".g" in extended_info:
        # unify separators
        revisions = extended_info.replace("-g.", "-g")
        revno, git_rev = re.split(r"[-|.|+]", revisions)[0:2]
        # Strip any non-numeric characters from the revno, just in case.
        revno = _coerce_to_int(revno)
        # Remove anything that doesn't look like a hexadecimal character.
        git_rev = re.sub(r"[^0-9a-f]+", "", git_rev)
    extended_info = re.sub(r"-*snap$", "", extended_info)
    # Remove unnecessary garbage from the extended info string.
    if "-" in extended_info:
        extended_info = "-".join(extended_info.split("-")[0:2])
    return MAASVersion(
        major,
        minor,
        point,
        qualifier_type_version,
        qualifier_version,
        revno,
        git_rev,
        short_version,
        extended_info,
        qualifier_type,
        snappy.running_in_snap(),
    )


@lru_cache(maxsize=1)
def get_maas_version():
    """Return the apt or snap version for the main MAAS package."""
    if snappy.running_in_snap():
        return snappy.get_snap_version()
    else:
        return get_version_from_apt(RACK_PACKAGE_NAME, REGION_PACKAGE_NAME)


@lru_cache(maxsize=1)
def get_maas_version_subversion():
    """Return a tuple with the MAAS version and the MAAS subversion."""
    version = get_maas_version()
    if version:
        return extract_version_subversion(version)
    else:
        # Get the branch information
        commit_hash = get_maas_repo_hash()
        if commit_hash is None:
            # Not installed or not in repo, then no way to identify. This
            # should not happen, but just in case.
            return DEFAULT_VERSION, "unknown"
        else:
            return "%s from source" % DEFAULT_VERSION, "git+%s" % commit_hash


@lru_cache(maxsize=1)
def get_maas_version_ui():
    """Return the version string for the running MAAS region.

    The returned string is suitable to display in the UI.
    """
    version, subversion = get_maas_version_subversion()
    return "%s (%s)" % (version, subversion) if subversion else version


@lru_cache(maxsize=1)
def get_maas_version_user_agent():
    """Return the version string for the running MAAS region.

    The returned string is suitable to set the user agent.
    """
    version, subversion = get_maas_version_subversion()
    return "maas/%s/%s" % (version, subversion)


@lru_cache(maxsize=1)
def get_maas_doc_version():
    """Return the doc version for the running MAAS region."""
    apt_version = get_maas_version()
    if apt_version:
        version, _ = extract_version_subversion(apt_version)
        return ".".join(version.split("~")[0].split(".")[:2])
    else:
        return ""
