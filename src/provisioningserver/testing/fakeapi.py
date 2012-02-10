# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Fake Provisioning API.

:class:`FakeSynchronousProvisioningAPI` is intended to be useful in a Django
environment, or similar, where the Provisioning API is being used via
xmlrpclib.ServerProxy for example.

:class:`FakeAsynchronousProvisioningAPI` is intended to be used in a Twisted
environment, where all functions return :class:`defer.Deferred`s.
"""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "FakeAsynchronousProvisioningAPI",
    "FakeSynchronousProvisioningAPI",
    ]

from functools import wraps

from provisioningserver.interfaces import IProvisioningAPI
from twisted.internet import defer
from zope.interface import implementer
from zope.interface.interface import Method


class FakeProvisioningDatabase(dict):

    def __missing__(self, key):
        self[key] = {"name": key}
        return self[key]

    def select(self, keys):
        """Select a subset of this mapping."""
        keys = frozenset(keys)
        return {
            key: value
            for key, value in self.iteritems()
            if key in keys
            }

    def delete(self, keys):
        """Delete a subset of this mapping."""
        for key in keys:
            if key in self:
                del self[key]

    def dump(self):
        """Dump this mapping.

        Keys are assumed to be immutable, and values are assumed to have a
        `copy` method, like a `dict` for example.
        """
        return {
            key: value.copy()
            for key, value in self.iteritems()
            }


@implementer(IProvisioningAPI)
class FakeSynchronousProvisioningAPI:

    # TODO: Referential integrity might be a nice thing.

    def __init__(self):
        super(FakeSynchronousProvisioningAPI, self).__init__()
        self.distros = FakeProvisioningDatabase()
        self.profiles = FakeProvisioningDatabase()
        self.nodes = FakeProvisioningDatabase()

    def add_distro(self, name, initrd, kernel):
        self.distros[name]["initrd"] = initrd
        self.distros[name]["kernel"] = kernel
        return name

    def add_profile(self, name, distro):
        self.profiles[name]["distro"] = distro
        return name

    def add_node(self, name, profile):
        self.nodes[name]["profile"] = profile
        return name

    def get_distros_by_name(self, names):
        return self.distros.select(names)

    def get_profiles_by_name(self, names):
        return self.profiles.select(names)

    def get_nodes_by_name(self, names):
        return self.nodes.select(names)

    def delete_distros_by_name(self, names):
        return self.distros.delete(names)

    def delete_profiles_by_name(self, names):
        return self.profiles.delete(names)

    def delete_nodes_by_name(self, names):
        return self.nodes.delete(names)

    def get_distros(self):
        return self.distros.dump()

    def get_profiles(self):
        return self.profiles.dump()

    def get_nodes(self):
        return self.nodes.dump()


def async(func):
    """Decorate a function so that it always return a `defer.Deferred`."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        return defer.execute(func, *args, **kwargs)
    return wrapper


# Generate an asynchronous variant based on the synchronous one.
FakeAsynchronousProvisioningAPI = type(
    b"FakeAsynchronousProvisioningAPI", (FakeSynchronousProvisioningAPI,), {
        name: async(getattr(FakeSynchronousProvisioningAPI, name))
        for name in IProvisioningAPI.names(all=True)
        if isinstance(IProvisioningAPI[name], Method)
        })
