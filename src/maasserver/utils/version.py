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
    "get_maas_version_subversion",
    "get_maas_version_ui",
    ]

import apt_pkg
from maasserver.api.logger import maaslog
from provisioningserver.utils import shell

# Initialize apt_pkg.
apt_pkg.init()

# Name of maas package to get version from.
REGION_PACKAGE_NAME = "maas-region-controller-min"


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
    if "~" in version:
        main_version, extra = version.split("~", 1)
        return main_version, extra.split("-", 1)[0]
    elif "+" in version:
        main_version, extra = version.split("+", 1)
        return main_version, "+" + extra.split("-", 1)[0]
    else:
        return version.split("-", 1)[0], ''


def get_maas_branch_version():
    """Return the Bazaar revision for this running MAAS.

    :return: An integer if MAAS is running from a Bazaar working tree, else
        `None`. The revision number is only representative of the BRANCH, not
        the working tree.
    """
    try:
        revno = shell.call_and_check(("bzr", "revno", __file__))
    except shell.ExternalProcessError:
        # We may not be in a Bazaar working tree, or Bazaar is not installed,
        # or any manner of other errors. For the purposes of this function we
        # don't care; simply say we don't know.
        return None
    else:
        # `bzr revno` can return '???' when it can't find the working tree's
        # current revision in the branch. Hopefully a fairly unlikely thing to
        # happen, but we guard against it, and other ills, here.
        try:
            return int(revno)
        except ValueError:
            return None


_cache = {}


# A very simply memoize function: when we switch to Django 1.7 we should use
# Django's lru_cache method.
def simple_cache(fun):
    def wrapped(*args, **kwargs):
        key = hash(repr(fun) + repr(args) + repr(kwargs))
        if key not in _cache:
            _cache[key] = fun(*args, **kwargs)
        return _cache[key]

    wrapped.__doc__ = "%s %s" % (fun.__doc__, "(cached)")
    return wrapped


@simple_cache
def get_maas_package_version():
    """Return the apt version for the main MAAS package."""
    return get_version_from_apt(REGION_PACKAGE_NAME)


@simple_cache
def get_maas_version_subversion():
    """Return a tuple with the MAAS version and the MAAS subversion."""
    apt_version = get_maas_package_version()
    if apt_version:
        return extract_version_subversion(apt_version)
    else:
        # Get the branch information
        branch_version = get_maas_branch_version()
        if branch_version is None:
            # Not installed not in branch, then no way to identify. This should
            # not happen, but just in case.
            return "unknown", ''
        else:
            return "from source (+bzr%d)" % branch_version, ''


@simple_cache
def get_maas_version_ui():
    """Return the version string for the running MAAS region.

    The returned string is suitable to display in the UI.
    """
    version, subversion = get_maas_version_subversion()
    return "%s (%s)" % (version, subversion) if subversion else version


@simple_cache
def get_maas_doc_version():
    """Return the doc version for the running MAAS region."""
    doc_prefix = 'docs'
    apt_version = get_maas_package_version()
    if apt_version:
        version, _ = extract_version_subversion(apt_version)
        return doc_prefix + '.'.join(version.split('.')[:2])
    else:
        return doc_prefix
