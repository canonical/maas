# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helpers for operating systems in testing."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'make_usable_osystem',
    'patch_usable_osystems',
    ]

from random import randint

from maasserver import forms
from maasserver.testing.factory import factory
from provisioningserver.boot.tests.test_tftppath import make_osystem
from provisioningserver.drivers.osystem import BOOT_IMAGE_PURPOSE


def make_osystem_with_releases(testcase, osystem_name=None, releases=None,
                               purposes=None):
    """Generate an arbitrary operating system.

    :param osystem_name: The operating system name. Useful in cases where
        we need to test that not supplying an os works correctly.
    :param releases: The list of releases name. Useful in cases where
        we need to test that not supplying a release works correctly.
    :param purposes: The purpose's of the boot images.
    """
    if osystem_name is None:
        osystem_name = factory.make_name('os')
    if releases is None:
        releases = [factory.make_name('release') for _ in range(3)]
    if purposes is None:
        purposes = [BOOT_IMAGE_PURPOSE.INSTALL, BOOT_IMAGE_PURPOSE.XINSTALL]

    osystem = make_osystem(
        testcase,
        osystem_name,
        purposes)
    if releases is not None and releases != []:
        osystem.fake_list = releases
    return osystem


def patch_usable_osystems(testcase, osystems=None, allow_empty=True):
    """Set a fixed list of usable operating systems.

    A usable operating system is one for which boot images are available.

    :param testcase: A `TestCase` whose `patch` this function can use.
    :param osystems: Optional list of operating systems.  If omitted,
        defaults to a list (which may be empty) of random operating systems.
    """
    start = 0
    if allow_empty is False:
        start = 1
    if osystems is None:
        osystems = [
            make_osystem_with_releases(testcase)
            for _ in range(randint(start, 2))
            ]
    distro_series = {}
    for osystem in osystems:
        distro_series[osystem.name] = osystem.get_supported_releases()
    testcase.patch(forms, 'list_all_usable_osystems').return_value = osystems
    testcase.patch(
        forms, 'list_all_usable_releases').return_value = distro_series


def make_usable_osystem(testcase, osystem_name=None, releases=None,
                        purposes=None):
    """Return arbitrary operating system, and make it "usable."

    A usable operating system is one for which boot images are available.

    :param testcase: A `TestCase` whose `patch` this function can pass to
        `patch_usable_osystems`.
    :param osystem_name: The operating system name. Useful in cases where
        we need to test that not supplying an os works correctly.
    :param releases: The list of releases name. Useful in cases where
        we need to test that not supplying a release works correctly.
    :param purposse: The list of purposes. Useful in cases where
        we need to test that not supplying a purpose works correctly.
    """
    osystem = make_osystem_with_releases(
        testcase, osystem_name=osystem_name, releases=releases,
        purposes=purposes)
    patch_usable_osystems(testcase, [osystem])
    return osystem
