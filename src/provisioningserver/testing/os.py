# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
"""Utilities for testing operating systems-related code."""

from maastesting.factory import factory
from provisioningserver.drivers.osystem import (
    BOOT_IMAGE_PURPOSE,
    OperatingSystem,
    OperatingSystemRegistry,
)


class FakeOS(OperatingSystem):
    name = ""
    title = ""

    def __init__(self, name, purpose=None, releases=None):
        self.name = name
        self.title = name
        self.purpose = purpose
        if releases is None:
            self.fake_list = [factory.make_string() for _ in range(3)]
        else:
            self.fake_list = releases

    def get_boot_image_purposes(self, *args):
        if self.purpose is None:
            return [BOOT_IMAGE_PURPOSE.XINSTALL]
        else:
            return self.purpose

    def get_supported_releases(self):
        return self.fake_list

    def get_default_release(self):
        return self.fake_list[0]

    def get_release_title(self, release):
        return release


def make_osystem(testcase, osystem, purpose=None, releases=None):
    """Makes the operating system class and registers it."""
    if osystem not in OperatingSystemRegistry:
        fake = FakeOS(osystem, purpose, releases)
        OperatingSystemRegistry.register_item(fake.name, fake)
        testcase.addCleanup(OperatingSystemRegistry.unregister_item, osystem)
        return fake

    else:
        obj = OperatingSystemRegistry[osystem]
        old_func = obj.get_boot_image_purposes
        testcase.patch(obj, "get_boot_image_purposes").return_value = purpose

        def reset_func(obj, old_func):
            obj.get_boot_image_purposes = old_func

        testcase.addCleanup(reset_func, obj, old_func)

        return obj
