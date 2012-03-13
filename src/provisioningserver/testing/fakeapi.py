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


def prevent_keyword_args(func):
    """Forbid use of keyword arguments.

    The Provisioning API is meant to be used via XML-RPC, at least for now, so
    we prevent all API methods from being used with keyword arguments, which
    are not supported via XML-RPC.
    """
    @wraps(func)
    def wrapper(*args):
        return func(*args)
    return wrapper


class FakeProvisioningDatabase(dict):

    def __missing__(self, key):
        self[key] = {"name": key}
        return self[key]

    def select(self, keys):
        """Select a subset of this mapping."""
        keys = frozenset(keys)
        return {
            key: value
            for key, value in self.items()
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
            for key, value in self.items()
            }


@implementer(IProvisioningAPI)
class FakeSynchronousProvisioningAPI:

    # TODO: Referential integrity might be a nice thing.

    def __init__(self):
        super(FakeSynchronousProvisioningAPI, self).__init__()
        self.distros = FakeProvisioningDatabase()
        self.profiles = FakeProvisioningDatabase()
        self.nodes = FakeProvisioningDatabase()
        # Record power_type settings for nodes (by node name).  This is
        # not part of the provisioning-server node as returned to the
        # maasserver, so it's not stored as a regular attribute even if
        # it works like one internally.
        self.power_types = {}
        # This records nodes that start/stop commands have been issued
        # for.  If a node has been started, its name maps to 'start'; if
        # it has been stopped, its name maps to 'stop' (whichever
        # happened most recently).
        self.power_status = {}

    @prevent_keyword_args
    def add_distro(self, name, initrd, kernel):
        self.distros[name]["initrd"] = initrd
        self.distros[name]["kernel"] = kernel
        return name

    @prevent_keyword_args
    def add_profile(self, name, distro):
        self.profiles[name]["distro"] = distro
        return name

    @prevent_keyword_args
    def add_node(self, name, profile, power_type, metadata):
        self.nodes[name]["profile"] = profile
        self.nodes[name]["mac_addresses"] = []
        self.nodes[name]["metadata"] = metadata
        self.power_types[name] = power_type
        return name

    @prevent_keyword_args
    def modify_distros(self, deltas):
        for name, delta in deltas.items():
            distro = self.distros[name]
            distro.update(delta)

    @prevent_keyword_args
    def modify_profiles(self, deltas):
        for name, delta in deltas.items():
            profile = self.profiles[name]
            profile.update(delta)

    @prevent_keyword_args
    def modify_nodes(self, deltas):
        for name, delta in deltas.items():
            node = self.nodes[name]
            node.update(delta)

    @prevent_keyword_args
    def get_distros_by_name(self, names):
        return self.distros.select(names)

    @prevent_keyword_args
    def get_profiles_by_name(self, names):
        return self.profiles.select(names)

    @prevent_keyword_args
    def get_nodes_by_name(self, names):
        return self.nodes.select(names)

    @prevent_keyword_args
    def delete_distros_by_name(self, names):
        return self.distros.delete(names)

    @prevent_keyword_args
    def delete_profiles_by_name(self, names):
        return self.profiles.delete(names)

    @prevent_keyword_args
    def delete_nodes_by_name(self, names):
        return self.nodes.delete(names)

    @prevent_keyword_args
    def get_distros(self):
        return self.distros.dump()

    @prevent_keyword_args
    def get_profiles(self):
        return self.profiles.dump()

    @prevent_keyword_args
    def get_nodes(self):
        return self.nodes.dump()

    @prevent_keyword_args
    def start_nodes(self, names):
        for name in names:
            self.power_status[name] = 'start'

    @prevent_keyword_args
    def stop_nodes(self, names):
        for name in names:
            self.power_status[name] = 'stop'


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
