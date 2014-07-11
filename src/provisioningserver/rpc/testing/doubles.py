# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test doubles for the region's RPC implementation."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "DummyConnection",
    "StubOS",
]

from provisioningserver.drivers.osystem import OperatingSystem
from provisioningserver.rpc.interfaces import IConnection
from zope.interface import implementer


@implementer(IConnection)
class DummyConnection:
    """A dummy connection.

    Implements `IConnection`.
    """


class StubOS(OperatingSystem):
    """An :py:class:`OperatingSystem` subclass that has canned answers.

    - The name is capitalised to derive the title.

    - The first release is the default.

    - Odd releases (in the order they're specified) require license
      keys.

    """

    name = title = None

    def __init__(self, name, releases):
        """
        :param name: A string name, usually all lowercase.
        :param releases: A list of (name, title) tuples.
        """
        super(StubOS, self).__init__()
        self.name = name
        self.title = name.capitalize()
        self.releases = releases

    def get_supported_releases(self):
        return [name for name, _ in self.releases]

    def get_default_release(self):
        if len(self.releases) == 0:
            return None
        else:
            name, _ = self.releases[0]
            return name

    def get_release_title(self, release):
        for name, title in self.releases:
            if name == release:
                return title
        else:
            return None

    def format_release_choices(self):
        raise NotImplementedError()

    def get_boot_image_purposes(self, arch, subarch, release, label):
        raise NotImplementedError()

    def requires_license_key(self, release):
        for index, (name, _) in enumerate(self.releases):
            if name == release:
                return index % 2 == 1
        else:
            return False

    def get_default_commissioning_release(self):
        if len(self.releases) >= 2:
            name, _ = self.releases[1]
            return name
        else:
            return None

    def get_supported_commissioning_releases(self):
        return [name for name, _ in self.releases[1:3]]
