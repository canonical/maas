# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test doubles for the region's RPC implementation."""

from unittest.mock import sentinel

import attr
from twisted.internet.defer import succeed
from zope.interface import implementer
from zope.interface.verify import verifyObject

from provisioningserver.drivers.osystem import OperatingSystem
from provisioningserver.rpc.interfaces import IConnection, IConnectionToRegion


@implementer(IConnection)
class DummyConnection:
    """A dummy connection.

    Implements `IConnection`.
    """


@attr.s(eq=False, order=False)
@implementer(IConnection)
class FakeConnection:
    "A fake `IConnection`." ""

    ident = attr.ib(default=sentinel.ident)
    hostCertificate = attr.ib(default=sentinel.hostCertificate)
    peerCertificate = attr.ib(default=sentinel.peerCertificate)
    in_use = attr.ib(default=False)

    def callRemote(self, cmd, **arguments):
        return succeed(sentinel.response)


verifyObject(IConnection, FakeConnection())


@attr.s(eq=False, order=False)
@implementer(IConnectionToRegion)
class FakeConnectionToRegion:
    "A fake `IConnectionToRegion`." ""

    ident = attr.ib(default=sentinel.ident)
    localIdent = attr.ib(default=sentinel.localIdent)
    address = attr.ib(default=(sentinel.host, sentinel.port))
    hostCertificate = attr.ib(default=sentinel.hostCertificate)
    peerCertificate = attr.ib(default=sentinel.peerCertificate)
    in_use = attr.ib(default=False)

    def callRemote(self, cmd, **arguments):
        return succeed(sentinel.response)


verifyObject(IConnectionToRegion, FakeConnectionToRegion())


@attr.s(eq=False, order=False)
@implementer(IConnectionToRegion)
class FakeBusyConnectionToRegion:
    "A fake `IConnectionToRegion` that appears busy." ""

    ident = attr.ib(default=sentinel.ident)
    localIdent = attr.ib(default=sentinel.localIdent)
    address = attr.ib(default=(sentinel.host, sentinel.port))
    hostCertificate = attr.ib(default=sentinel.hostCertificate)
    peerCertificate = attr.ib(default=sentinel.peerCertificate)
    in_use = attr.ib(default=True)

    def callRemote(self, cmd, **arguments):
        return succeed(sentinel.response)


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
        super().__init__()
        self.name = name
        self.title = name.capitalize()
        self.releases = releases

    def is_release_supported(self, release):
        return release in self.releases

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

    def get_boot_image_purposes(self):
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
