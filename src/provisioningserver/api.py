# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Provisioning API for external use."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "ProvisioningAPI",
    ]

from base64 import b64encode
from functools import partial
from itertools import (
    chain,
    count,
    izip,
    repeat,
    )

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
        "hostname": data["hostname"],
        "profile": data["profile"],
        "mac_addresses": [
            mac_address.strip()
            for mac_address in mac_addresses
            if mac_address and not mac_address.isspace()
            ],
        "netboot_enabled": data.get("netboot_enabled"),
        "power_type": data["power_type"],
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


def gen_cobbler_interface_deltas(interfaces, hostname, mac_addresses):
    """Generate `modify_system` dicts for use with `xapi_object_edit`.

    This takes `interfaces` - the current state of a system's interfaces - and
    generates the operations required to transform it into a list of
    interfaces containing exactly `mac_addresses`.

    :param interfaces: A dict of interface-names -> interface-configurations.
    :param hostname: The hostname of the system.
    :param mac_addresses: A collection of desired MAC addresses.
    """
    # A lazy list of ethernet interface names, used for constructing the
    # target configuration. Names will be allocated in order, eth0 for the
    # first MAC address, eth1 for the second, and so on.
    eth_names = ("eth%d" % num for num in count(0))

    # Allocate DNS names in order too, `hostname` for the first interface, and
    # to the empty string for the rest. Cobbler will complain (in its default
    # config) if a dns_name is duplicated. Setting the dns_name for only a
    # single interface and keeping dns_name on the first interface at all
    # times also makes things slightly easier to reason about.
    dns_names = chain([hostname], repeat(""))

    # Calculate comparable mappings of the current interface configuration and
    # the desired interface configuration.
    interfaces_from = {
        interface_name: {
            "interface": interface_name,
            "mac_address": interface["mac_address"],
            "dns_name": interface.get("dns_name", ""),
            }
        for interface_name, interface
        in interfaces.items()
        }
    interfaces_to = {
        interface_name: {
            "interface": interface_name,
            "mac_address": mac_address,
            "dns_name": dns_name,
            }
        for interface_name, mac_address, dns_name
        in izip(eth_names, mac_addresses, dns_names)
        }

    # If we're removing all MAC addresses, we need to leave one unconfigured
    # interface behind to satisfy Cobbler's data model constraints.
    if len(mac_addresses) == 0:
        interfaces_to["eth0"] = {
            "interface": "eth0",
            "mac_address": "",
            "dns_name": "",
            }

    # Go through interfaces, generating deltas from `interfaces_from` to
    # `interfaces_to`. This is done in sorted order to make testing easier.
    interface_names = set().union(interfaces_from, interfaces_to)
    for interface_name in sorted(interface_names):
        interface_from = interfaces_from.get(interface_name)
        interface_to = interfaces_to.get(interface_name)
        if interface_to is None:
            assert interface_from is not None
            yield {"interface": interface_name, "delete_interface": True}
        elif interface_from is None:
            assert interface_to is not None
            yield interface_to
        elif interface_to != interface_from:
            yield interface_to
        else:
            pass  # No change.


class ProvisioningAPI:

    implements(IProvisioningAPI)

    def __init__(self, session):
        super(ProvisioningAPI, self).__init__()
        self.session = session

    def sync(self):
        """Request Cobbler to sync and return when it's finished."""
        return self.session.call(
            "sync", self.session.token_placeholder)

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
        yield self.sync()
        returnValue(distro.name)

    @inlineCallbacks
    def add_profile(self, name, distro):
        assert isinstance(name, basestring)
        assert isinstance(distro, basestring)
        profile = yield CobblerProfile.new(
            self.session, name, {"distro": distro})
        yield self.sync()
        returnValue(profile.name)

    @inlineCallbacks
    def add_node(self, name, hostname, profile, power_type, preseed_data):
        assert isinstance(name, basestring)
        assert isinstance(hostname, basestring)
        assert isinstance(profile, basestring)
        assert power_type in (POWER_TYPE.VIRSH, POWER_TYPE.WAKE_ON_LAN)
        assert isinstance(preseed_data, basestring)
        attributes = {
            "hostname": hostname,
            "profile": profile,
            "ks_meta": {"MAAS_PRESEED": b64encode(preseed_data)},
            "power_type": power_type,
            }
        system = yield CobblerSystem.new(self.session, name, attributes)
        yield self.sync()
        returnValue(system.name)

    @inlineCallbacks
    def modify_distros(self, deltas):
        for name, delta in deltas.items():
            yield CobblerDistro(self.session, name).modify(delta)
        yield self.sync()

    @inlineCallbacks
    def modify_profiles(self, deltas):
        for name, delta in deltas.items():
            yield CobblerProfile(self.session, name).modify(delta)
        yield self.sync()

    @inlineCallbacks
    def modify_nodes(self, deltas):
        for name, delta in deltas.items():
            system = CobblerSystem(self.session, name)
            if "mac_addresses" in delta:
                # This needs to be handled carefully.
                mac_addresses = delta.pop("mac_addresses")
                system_state = yield system.get_values()
                hostname = system_state.get("hostname", "")
                interfaces = system_state.get("interfaces", {})
                interface_modifications = gen_cobbler_interface_deltas(
                    interfaces, hostname, mac_addresses)
                for interface_modification in interface_modifications:
                    yield system.modify(interface_modification)
            yield system.modify(delta)
        yield self.sync()

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
        yield self.sync()

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
