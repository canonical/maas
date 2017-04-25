# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Version utilities."""

__all__ = [
    "get_maas_doc_version",
    "get_maas_version_subversion",
    "get_maas_version_ui",
    ]

from functools import lru_cache
import re

from maasserver import __version__ as old_version
from maasserver.api.logger import maaslog
from provisioningserver.utils import (
    shell,
    snappy,
)

# Only import apt_pkg and initialize when not running in a snap.
if not snappy.running_in_snap():
    import apt_pkg
    apt_pkg.init()

# Name of maas package to get version from.
REGION_PACKAGE_NAME = "maas-region-api"


def get_version_from_apt(package):
    """Return the version output from `apt_pkg.Cache` for the given package or
    an error message if the package data is not valid."""
    try:
        cache = apt_pkg.Cache(None)
    except SystemError:
        maaslog.error(
            'Installed version could not be determined. Ensure '
            '/var/lib/dpkg/status is valid.')
        return ""

    version = None
    if package in cache:
        apt_package = cache[package]
        version = apt_package.current_ver

    return version.ver_str if version is not None else ""


def extract_version_subversion(version):
    """Return a tuple (version, subversion) from the given apt version."""
    main_version, subversion = re.split('[+|-]', version, 1)
    return main_version, subversion


def get_maas_branch_version():
    """Return the Bazaar revision for this running MAAS.

    :return: An integer if MAAS is running from a Bazaar working tree, else
        `None`. The revision number is only representative of the BRANCH, not
        the working tree.
    """
    try:
        revno = shell.call_and_check(("bzr", "revno", __file__))
    except shell.ExternalProcessError:
        # We may not be in a Bazaar working tree, or any manner of other
        # errors. For the purposes of this function we don't care; simply say
        # we don't know.
        return None
    except FileNotFoundError:
        # Bazaar is not installed. We don't care and simply say we don't know.
        return None
    else:
        # `bzr revno` can return '???' when it can't find the working tree's
        # current revision in the branch. Hopefully a fairly unlikely thing to
        # happen, but we guard against it, and other ills, here.
        try:
            return int(revno)
        except ValueError:
            return None


@lru_cache(maxsize=1)
def get_maas_version():
    """Return the apt or snap version for the main MAAS package."""
    if snappy.running_in_snap():
        return snappy.get_snap_version()
    else:
        return get_version_from_apt(REGION_PACKAGE_NAME)


@lru_cache(maxsize=1)
def get_maas_version_subversion():
    """Return a tuple with the MAAS version and the MAAS subversion."""
    version = get_maas_version()
    if version:
        return extract_version_subversion(version)
    else:
        # Get the branch information
        branch_version = get_maas_branch_version()
        if branch_version is None:
            # Not installed not in branch, then no way to identify. This should
            # not happen, but just in case.
            return old_version, "unknown"
        else:
            return "%s from source" % old_version, "bzr%d" % branch_version


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
        return '.'.join(version.split('~')[0].split('.')[:2])
    else:
        return ''


def get_maas_version_tuple():
    """Returns a tuple of the MAAS version without the svn rev."""
    return tuple(int(x) for x in old_version.split('.'))
