# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
"""Utilities for testing operating systems-related code."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'FakeOS',
    ]


from maastesting.factory import factory
from provisioningserver.drivers.osystem import (
    OperatingSystem,
    OperatingSystemRegistry,
    )


class FakeOS(OperatingSystem):

    name = ""
    title = ""

    def __init__(self, name, purpose, releases=None):
        self.name = name
        self.title = name
        self.purpose = purpose
        if releases is None:
            self.fake_list = [
                factory.make_string()
                for _ in range(3)
                ]
        else:
            self.fake_list = releases

    def get_boot_image_purposes(self, *args):
        return self.purpose

    def is_release_supported(self, release):
        return release in self.fake_list

    def get_supported_releases(self):
        return self.fake_list

    def get_default_release(self):
        return self.fake_list[0]

    def get_release_title(self, release):
        return release


def make_osystem(testcase, osystem, purpose):
    """Makes the operating system class and registers it."""
    if osystem not in OperatingSystemRegistry:
        fake = FakeOS(osystem, purpose)
        OperatingSystemRegistry.register_item(fake.name, fake)
        testcase.addCleanup(
            OperatingSystemRegistry.unregister_item, osystem)
        return fake

    else:

        obj = OperatingSystemRegistry[osystem]
        old_func = obj.get_boot_image_purposes
        testcase.patch(obj, 'get_boot_image_purposes').return_value = purpose

        def reset_func(obj, old_func):
            obj.get_boot_image_purposes = old_func

        testcase.addCleanup(reset_func, obj, old_func)

        return obj
