# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Provisioning API for external use."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "ProvisioningAPI",
    ]

from functools import partial

from provisioningserver.cobblerclient import (
    CobblerDistro,
    CobblerProfile,
    CobblerSystem,
    )
from provisioningserver.interfaces import IProvisioningAPI
from provisioningserver.utils import deferred
from twisted.internet.defer import (
    inlineCallbacks,
    returnValue,
    )
from zope.interface import implements


def postprocess_mapping(mapping, function):
    """Apply `function` to each value in `mapping`, returned in a new dict."""
    return {
        key: function(value)
        for key, value in mapping.iteritems()
        }


def cobbler_to_papi_node(data):
    """Convert a Cobbler representation of a system to a PAPI node."""
    interfaces = data.get("interfaces", {})
    mac_addresses = (
        interface["mac_address"]
        for interface in interfaces.itervalues())
    return {
        "name": data["name"],
        "profile": data["profile"],
        "mac_addresses": [
            mac_address.strip()
            for mac_address in mac_addresses
            if not mac_address.isspace()
            ],
        }

cobbler_mapping_to_papi_nodes = partial(
    postprocess_mapping, function=cobbler_to_papi_node)


def cobbler_to_papi_profile(data):
    """Convert a Cobbler representation of a profile to a PAPI profile."""
    return {
        "name": data["name"],
        "distro": data["distro"],
        }

cobbler_mapping_to_papi_profiles = partial(
    postprocess_mapping, function=cobbler_to_papi_profile)


def cobbler_to_papi_distro(data):
    """Convert a Cobbler representation of a distro to a PAPI distro."""
    return {
        "name": data["name"],
        "initrd": data["initrd"],
        "kernel": data["kernel"],
        }

cobbler_mapping_to_papi_distros = partial(
    postprocess_mapping, function=cobbler_to_papi_distro)


class ProvisioningAPI:

    implements(IProvisioningAPI)

    def __init__(self, session):
        super(ProvisioningAPI, self).__init__()
        self.session = session

    @inlineCallbacks
    def add_distro(self, name, initrd, kernel):
        assert isinstance(name, basestring)
        assert isinstance(initrd, basestring)
        assert isinstance(kernel, basestring)
        distro = yield CobblerDistro.new(
            self.session, name, {
                "initrd": initrd,
                "kernel": kernel,
                })
        returnValue(distro.name)

    @inlineCallbacks
    def add_profile(self, name, distro):
        assert isinstance(name, basestring)
        assert isinstance(distro, basestring)
        profile = yield CobblerProfile.new(
            self.session, name, {"distro": distro})
        returnValue(profile.name)

    @inlineCallbacks
    def add_node(self, name, profile):
        assert isinstance(name, basestring)
        assert isinstance(profile, basestring)
        system = yield CobblerSystem.new(
            self.session, name, {"profile": profile})
        returnValue(system.name)

    @inlineCallbacks
    def get_objects_by_name(self, object_type, names):
        """Get `object_type` objects by name.

        :param object_type: The type of object to look for.
        :type object_type:
            :class:`provisioningserver.cobblerclient.CobblerObjectType`
        :param names: A list of names to search for.
        :type names: list
        """
        assert all(isinstance(name, basestring) for name in names)
        objects_by_name = {}
        for name in names:
            values = yield object_type(self.session, name).get_values()
            if values is not None:
                objects_by_name[name] = values
        returnValue(objects_by_name)

    @deferred
    def get_distros_by_name(self, names):
        d = self.get_objects_by_name(CobblerDistro, names)
        return d.addCallback(cobbler_mapping_to_papi_distros)

    @deferred
    def get_profiles_by_name(self, names):
        d = self.get_objects_by_name(CobblerProfile, names)
        return d.addCallback(cobbler_mapping_to_papi_profiles)

    @deferred
    def get_nodes_by_name(self, names):
        d = self.get_objects_by_name(CobblerSystem, names)
        return d.addCallback(cobbler_mapping_to_papi_nodes)

    @inlineCallbacks
    def delete_objects_by_name(self, object_type, names):
        """Delete `object_type` objects by name.

        :param object_type: The type of object to delete.
        :type object_type:
            :class:`provisioningserver.cobblerclient.CobblerObjectType`
        :param names: A list of names to search for.
        :type names: list
        """
        assert all(isinstance(name, basestring) for name in names)
        for name in names:
            yield object_type(self.session, name).delete()

    @deferred
    def delete_distros_by_name(self, names):
        return self.delete_objects_by_name(CobblerDistro, names)

    @deferred
    def delete_profiles_by_name(self, names):
        return self.delete_objects_by_name(CobblerProfile, names)

    @deferred
    def delete_nodes_by_name(self, names):
        return self.delete_objects_by_name(CobblerSystem, names)

    @deferred
    def get_distros(self):
        # WARNING: This could return a large number of results. Consider
        # adding filtering options to this function before using it in anger.
        d = CobblerDistro.get_all_values(self.session)
        return d.addCallback(cobbler_mapping_to_papi_distros)

    @deferred
    def get_profiles(self):
        # WARNING: This could return a large number of results. Consider
        # adding filtering options to this function before using it in anger.
        d = CobblerProfile.get_all_values(self.session)
        return d.addCallback(cobbler_mapping_to_papi_profiles)

    @deferred
    def get_nodes(self):
        # WARNING: This could return a *huge* number of results. Consider
        # adding filtering options to this function before using it in anger.
        d = CobblerSystem.get_all_values(self.session)
        return d.addCallback(cobbler_mapping_to_papi_nodes)
