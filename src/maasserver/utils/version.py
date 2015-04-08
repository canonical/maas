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


try:
    from bzrlib.branch import Branch
    from bzrlib.errors import NotBranchError
except ImportError:
    Branch = None

# Initialize apt_pkg.
apt_pkg.init()

# Name of maas package to get version from.
REGION_PACKAGE_NAME = "maas-region-controller-min"


def get_version_from_apt(package):
    """Return the version output from `apt_pkg.Cache` for the given package."""
    cache = apt_pkg.Cache(None)
    version = None
    if package in cache:
        apt_package = cache[package]
        version = apt_package.current_ver

    if version is not None:
        return version.ver_str
    else:
        return ""


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


def get_maas_branch():
    """Return the `bzrlib.branch.Branch` for this running MAAS."""
    if Branch is None:
        return None
    try:
        return Branch.open(".")
    except NotBranchError:
        return None


_cache = {}


# A very simply memoize function: when we switch to Django 1.7 we should use
# Django's lru_cache method.
def simple_cache(fun):
    def wrapped(*args, **kwargs):
        key = hash(repr(fun) + repr(args) + repr(kwargs))
        if not key in _cache:
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
        branch = get_maas_branch()
        if branch is None:
            # Not installed not in branch, then no way to identify. This should
            # not happen, but just in case.
            return "unknown", ''
        else:
            return "from source (+bzr%s)" % branch.revno(), ''


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
