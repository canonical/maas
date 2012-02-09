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
        return self.get_objects_by_name(CobblerDistro, names)

    @deferred
    def get_profiles_by_name(self, names):
        return self.get_objects_by_name(CobblerProfile, names)

    @deferred
    def get_nodes_by_name(self, names):
        return self.get_objects_by_name(CobblerSystem, names)

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
        return CobblerDistro.get_all_values(self.session)

    @deferred
    def get_profiles(self):
        # WARNING: This could return a large number of results. Consider
        # adding filtering options to this function before using it in anger.
        return CobblerProfile.get_all_values(self.session)

    @deferred
    def get_nodes(self):
        # WARNING: This could return a *huge* number of results. Consider
        # adding filtering options to this function before using it in anger.
        return CobblerSystem.get_all_values(self.session)
