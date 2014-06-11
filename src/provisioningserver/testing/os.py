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
from provisioningserver.drivers.osystem import OperatingSystem


class FakeOS(OperatingSystem):

    name = ""
    title = ""

    def __init__(self, name, purpose, releases=None):
        self.name = name
        self.title = name
        self.purpose = purpose
        if releases is None:
            self.fake_list = [
                factory.getRandomString()
                for _ in range(3)
                ]
        else:
            self.fake_list = releases

    def get_boot_image_purposes(self, *args):
        return self.purpose

    def get_supported_releases(self):
        return self.fake_list

    def get_default_release(self):
        return self.fake_list[0]

    def format_release_choices(self, releases):
        return [
            (release, release)
            for release in releases
            if release in self.fake_list
            ]
