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
from itertools import count

from provisioningserver.cobblerclient import (
    CobblerDistro,
    CobblerProfile,
    CobblerSystem,
    )
from provisioningserver.enum import POWER_TYPE
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
        for key, value in mapping.items()
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


def mac_addresses_to_cobbler_deltas(interfaces, mac_addresses):
    """Generate `modify_system` dicts for use with `xapi_object_edit`.

    This takes `interfaces` - the current state of a system's interfaces - and
    generates the operations required to transform it into a list of
    interfaces containing exactly `mac_addresses`.

    :param interfaces: A dict of interface-names -> interface-configurations.
    :param mac_addresses: A collection of desired MAC addresses.
    """
    # For the sake of this calculation, ignore interfaces without MACs
    # assigned. We may end up setting the MAC on these interfaces, but whether
    # or not that happens is undefined (for now).
    interfaces = {
        name: configuration
        for name, configuration in interfaces.items()
        if configuration["mac_address"]
        }

    interface_names_by_mac_address = {
        interface["mac_address"]: interface_name
        for interface_name, interface in interfaces.items()
        }
    mac_addresses_to_remove = set(
        interface_names_by_mac_address).difference(mac_addresses)
    mac_addresses_to_add = set(
        mac_addresses).difference(interface_names_by_mac_address)

    # Keep track of the used interface names.
    interface_names = set(interfaces)
    # The following generator will lazily return interface names that can be
    # used when adding MAC addresses.
    interface_names_unused = (
        "eth%d" % num for num in count(0)
        if "eth%d" % num not in interface_names)

    # Create a delta to remove an interface in Cobbler. We sort the MAC
    # addresses to provide stability in this function's output (which
    # facilitates testing).
    for mac_address in sorted(mac_addresses_to_remove):
        interface_name = interface_names_by_mac_address[mac_address]
        # Deallocate this interface name from our records; it can be used when
        # allocating interfaces later.
        interface_names.remove(interface_name)
        yield {
            "interface": interface_name,
            "delete_interface": True,
            }

    # Create a delta to add an interface in Cobbler. We sort the MAC addresses
    # to provide stability in this function's output (which facilitates
    # testing).
    for mac_address in sorted(mac_addresses_to_add):
        interface_name = next(interface_names_unused)
        # Allocate this interface name in our records; it's not actually
        # necessary (interface_names_unused will never go backwards) but we do
        # it defensively in case of later additions to this function, and
        # because it has a satifying symmetry.
        interface_names.add(interface_name)
        yield {
            "interface": interface_name,
            "mac_address": mac_address,
            }


# Preseed data to send to cloud-init.  We set this as MAAS_PRESEED in
# ks_meta, and it gets fed straight into debconf.
metadata_preseed_items = [
    ('datasources', 'multiselect', 'MaaS'),
    ('maas-metadata-url', 'string', '%(maas-metadata-url)s'),
    ('maas-metadata-credentials', 'string', '%(maas-metadata-credentials)s'),
    ]
metadata_preseed = '\n'.join(
    "cloud-init   cloud-init/%s  %s %s" % (item_name, item_type, item_value)
    for item_name, item_type, item_value in metadata_preseed_items)


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
    def add_node(self, name, profile, power_type, metadata):
        assert isinstance(name, basestring)
        assert isinstance(profile, basestring)
        assert power_type in (POWER_TYPE.VIRSH, POWER_TYPE.WAKE_ON_LAN)
        assert isinstance(metadata, dict)
        attributes = {
            "profile": profile,
            "ks_meta": {"MAAS_PRESEED": metadata_preseed % metadata},
            "power_type": power_type,
            }
        system = yield CobblerSystem.new(self.session, name, attributes)
        returnValue(system.name)

    @inlineCallbacks
    def modify_distros(self, deltas):
        for name, delta in deltas.items():
            yield CobblerDistro(self.session, name).modify(delta)

    @inlineCallbacks
    def modify_profiles(self, deltas):
        for name, delta in deltas.items():
            yield CobblerProfile(self.session, name).modify(delta)

    @inlineCallbacks
    def modify_nodes(self, deltas):
        for name, delta in deltas.items():
            system = CobblerSystem(self.session, name)
            if "mac_addresses" in delta:
                # This needs to be handled carefully.
                mac_addresses = delta.pop("mac_addresses")
                system_state = yield system.get_values()
                interfaces = system_state.get("interfaces", {})
                interface_modifications = mac_addresses_to_cobbler_deltas(
                    interfaces, mac_addresses)
                for interface_modification in interface_modifications:
                    yield system.modify(interface_modification)
            yield system.modify(delta)

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

    @deferred
    def start_nodes(self, names):
        d = CobblerSystem.powerOnMultiple(self.session, names)
        return d

    @deferred
    def stop_nodes(self, names):
        d = CobblerSystem.powerOffMultiple(self.session, names)
        return d
