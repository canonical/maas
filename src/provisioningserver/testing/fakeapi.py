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
class FakeProvisioningAPIBase:

    # TODO: Referential integrity might be a nice thing.

    def __init__(self):
        super(FakeProvisioningAPIBase, self).__init__()
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

    def add_distro(self, name, initrd, kernel):
        self.distros[name]["initrd"] = initrd
        self.distros[name]["kernel"] = kernel
        return name

    def add_profile(self, name, distro):
        self.profiles[name]["distro"] = distro
        return name

    def add_node(self, name, profile, power_type, metadata):
        self.nodes[name]["profile"] = profile
        self.nodes[name]["mac_addresses"] = []
        self.nodes[name]["metadata"] = metadata
        self.power_types[name] = power_type
        return name

    def modify_distros(self, deltas):
        for name, delta in deltas.items():
            distro = self.distros[name]
            distro.update(delta)

    def modify_profiles(self, deltas):
        for name, delta in deltas.items():
            profile = self.profiles[name]
            profile.update(delta)

    def modify_nodes(self, deltas):
        for name, delta in deltas.items():
            node = self.nodes[name]
            node.update(delta)

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

    def start_nodes(self, names):
        for name in names:
            self.power_status[name] = 'start'

    def stop_nodes(self, names):
        for name in names:
            self.power_status[name] = 'stop'


PAPI_METHODS = {
    name: getattr(FakeProvisioningAPIBase, name)
    for name in IProvisioningAPI.names(all=True)
    if isinstance(IProvisioningAPI[name], Method)
    }


def sync_xmlrpc_func(func):
    """Decorate a function so that it acts similarly to a synchronously
    accessed remote XML-RPC call.

    All method calls return synchronously.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        assert len(kwargs) == 0, (
            "The Provisioning API is meant to be used via XML-RPC, "
            "for now, so its methods are prevented from use with "
            "keyword arguments, which XML-RPC does not support.")
        # TODO: Convert exceptions into Faults.
        return func(*args)
    return wrapper


# Generate an synchronous variant.
FakeSynchronousProvisioningAPI = type(
    b"FakeSynchronousProvisioningAPI", (FakeProvisioningAPIBase,), {
        name: sync_xmlrpc_func(func) for name, func in PAPI_METHODS.items()
        })


def async_xmlrpc_func(func):
    """Decorate a function so that it acts similarly to an asynchronously
    accessed remote XML-RPC call.

    All method calls return asynchronously, via a :class:`defer.Deferred`.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        assert len(kwargs) == 0, (
            "The Provisioning API is meant to be used via XML-RPC, "
            "for now, so its methods are prevented from use with "
            "keyword arguments, which XML-RPC does not support.")
        # TODO: Convert exceptions into Faults.
        return defer.execute(func, *args)
    return wrapper


# Generate an asynchronous variant.
FakeAsynchronousProvisioningAPI = type(
    b"FakeAsynchronousProvisioningAPI", (FakeProvisioningAPIBase,), {
        name: async_xmlrpc_func(func) for name, func in PAPI_METHODS.items()
        })
