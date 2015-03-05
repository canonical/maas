# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Version utilities."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "get_maas_doc_version",
    "get_maas_version",
    ]

import apt_pkg


try:
    from bzrlib.branch import Branch
    from bzrlib.errors import NotBranchError
except ImportError:
    Branch = None

# Initialize apt_pkg.
apt_pkg.init()

# Holds the version of maas.
MAAS_VERSION = None

# Name of maas package to get version from.
REGION_PACKAGE_NAME = "maas-region-controller-min"


def get_version_from_apt(package):
    """Return the version output from `apt_pkg.Cache` for the given package."""
    cache = apt_pkg.Cache()
    version = None
    if package in cache:
        apt_package = cache[package]
        version = apt_package.current_ver

    if version is not None:
        return version.ver_str
    else:
        return ""


def format_version(version):
    """Format `version` into a better looking string for the UI."""
    if "~" in version:
        main_version, extra = version.split("~", 1)
        return "%s (%s)" % (main_version, extra.split("-", 1)[0])
    elif "+" in version:
        main_version, extra = version.split("+", 1)
        return "%s (+%s)" % (main_version, extra.split("-", 1)[0])
    else:
        return version.split("-", 1)[0]


def get_maas_region_package_version():
    """Return the dpkg version for `REGION_PACKAGE_NAME`.

    Lazy loads the version. Once loaded it will not be loaded again.
    This is to speed up the call to this method and also to require the
    region to be restarted to see the new version.
    """
    global MAAS_VERSION
    if MAAS_VERSION is None:
        MAAS_VERSION = get_version_from_apt(REGION_PACKAGE_NAME)
        # Possibly this returned an empty string, meaning it's not installed
        # and no need to call again.
        if MAAS_VERSION:
            # It is a valid version so set the correct format.
            MAAS_VERSION = format_version(MAAS_VERSION)
    return MAAS_VERSION


def get_maas_branch():
    """Return the `bzrlib.branch.Branch` for this running MAAS."""
    if Branch is None:
        return None
    try:
        return Branch.open(".")
    except NotBranchError:
        return None


def get_maas_version():
    """Return the version string for the running MAAS region."""
    # MAAS is installed from package, return the version string.
    version = get_maas_region_package_version()
    if version:
        return version
    else:
        # Get the branch information
        branch = get_maas_branch()
        if branch is None:
            # Not installed not in branch, then no way to identify. This should
            # not happen, but just in case.
            return "unknown"
        else:
            return "from source (+bzr%s)" % branch.revno()


def get_maas_main_version():
    """Return the main version for the running MAAS region."""
    # MAAS is installed from package, return the version string.
    version = get_maas_region_package_version()
    if version:
        if " " in version:
            return version.split(" ")[0]
        else:
            return version
    else:
        return ""


def get_maas_doc_version():
    """Return the doc version for the running MAAS region."""
    main_version = get_maas_main_version()
    doc_prefix = 'docs'
    if not main_version:
        return doc_prefix
    else:
        return doc_prefix + '.'.join(main_version.split('.')[:2])
