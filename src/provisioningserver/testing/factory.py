# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Provisioning test-objects factory."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'CobblerFakeFactory',
    'ProvisioningFakeFactory',
    ]

from abc import ABCMeta
from itertools import count
from random import randint
from time import time
from xmlrpclib import Fault

from provisioningserver.enum import POWER_TYPE
from twisted.internet.defer import (
    inlineCallbacks,
    returnValue,
    )


names = ("test%d" % num for num in count(int(time())))


def fake_name():
    """Return a fake name. Each call returns a different name."""
    return next(names)


class ProvisioningFakeFactory:
    """Mixin for test cases: factory of fake provisioning objects.

    This can be used while testing against a real Cobbler, or a real
    provisioning server with a fake Cobbler, or a fake provisioning server.

    All objects you create using this factory will be cleaned up at the end of
    each test.
    """

    __metaclass__ = ABCMeta

    @staticmethod
    def clean_up_objects(deleter, *object_names):
        """Remove named objects from the PAPI.

        `delete_func` is expected to be one of the ``delete_*_by_name``
        methods of the Provisioning API. XML-RPC errors are ignored; this
        function does its best to remove the object but a failure to do so is
        not an error.
        """
        d = deleter(object_names)
        if d is not None:
            d.addErrback(lambda failure: failure.trap(Fault))
        return d

    @inlineCallbacks
    def add_distro(self, papi, name=None):
        """Creates a new distro object via `papi`.

        Arranges for it to be deleted during test clean-up. If `name` is not
        specified, `fake_name` will be called to obtain one.
        """
        if name is None:
            name = fake_name()
        # For the initrd and kernel, use a file that we know will exist for a
        # running Cobbler instance (at least, on Ubuntu) so that we can test
        # against remote instances, like one in odev.
        initrd = "/etc/cobbler/settings"
        kernel = "/etc/cobbler/version"
        distro_name = yield papi.add_distro(name, initrd, kernel)
        self.addCleanup(
            self.clean_up_objects,
            papi.delete_distros_by_name,
            distro_name)
        returnValue(distro_name)

    @inlineCallbacks
    def add_profile(self, papi, name=None, distro_name=None):
        """Creates a new profile object via `papi`.

        Arranges for it to be deleted during test clean-up. If `name` is not
        specified, `fake_name` will be called to obtain one. If `distro_name`
        is not specified, one will be obtained by calling `add_distro`.
        """
        if name is None:
            name = fake_name()
        if distro_name is None:
            distro_name = yield self.add_distro(papi)
        profile_name = yield papi.add_profile(name, distro_name)
        self.addCleanup(
            self.clean_up_objects,
            papi.delete_profiles_by_name,
            profile_name)
        returnValue(profile_name)

    @inlineCallbacks
    def add_node(self, papi, name=None, hostname=None, profile_name=None,
                 power_type=None, preseed_data=None):
        """Creates a new node object via `papi`.

        Arranges for it to be deleted during test clean-up. If `name` is not
        specified, `fake_name` will be called to obtain one. If `profile_name`
        is not specified, one will be obtained by calling `add_profile`.
        """
        if name is None:
            name = fake_name()
        if hostname is None:
            hostname = fake_name()
        if profile_name is None:
            profile_name = yield self.add_profile(papi)
        if power_type is None:
            power_type = POWER_TYPE.WAKE_ON_LAN
        if preseed_data is None:
            preseed_data = ""
        node_name = yield papi.add_node(
            name, hostname, profile_name, power_type, preseed_data)
        self.addCleanup(
            self.clean_up_objects,
            papi.delete_nodes_by_name,
            node_name)
        returnValue(node_name)


class CobblerFakeFactory:
    """Mixin for test cases: factory of fake objects in Cobbler.

    Warning: there is no cleanup for these yet.  Don't just run this against
    a real cobbler, or there will be trouble.
    """

    def default_to_file(self, attributes, attribute, required_attrs):
        """If `attributes[attribute]` is missing, make it a file.

        Sets the given attribute to a newly-created file, if it is a required
        attribute and not already set in attributes.
        """
        if attribute in required_attrs and attribute not in attributes:
            attributes[attribute] = self.make_file()

    @inlineCallbacks
    def default_to_object(self, attributes, attribute, required_attrs,
                          session, cobbler_class):
        """If `attributes[attribute]` is missing, make it an object.

        Sets the given attribute to a newly-created Cobbler object, if it is
        a required attribute and not already set in attributes.
        """
        if attribute in required_attrs and attribute not in attributes:
            other_obj = yield self.fake_cobbler_object(session, cobbler_class)
            attributes[attribute] = other_obj.name

    @inlineCallbacks
    def fake_cobbler_object(self, session, object_class, name=None,
                            attributes=None):
        """Create a fake Cobbler object.

        :param session: `CobblerSession`.
        :param object_class: concrete `CobblerObject` class to instantiate.
        :param name: Option name for the object.
        :param attributes: Optional dict of attribute values for the object.
        """
        if attributes is None:
            attributes = {}
        else:
            attributes = attributes.copy()
        unique_int = randint(1, 9999)
        if name is None:
            name = 'name-%s-%d' % (object_class.object_type, unique_int)
        attributes['name'] = name
        self.default_to_file(
            attributes, 'kernel', object_class.required_attributes),
        self.default_to_file(
            attributes, 'initrd', object_class.required_attributes),
        for attr in object_class.required_attributes:
            if attr not in attributes:
                attributes[attr] = '%s-%d' % (attr, unique_int)
        new_object = yield object_class.new(session, name, attributes)
        returnValue(new_object)
