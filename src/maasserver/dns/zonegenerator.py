# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DNS zone generator."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'ZoneGenerator',
    ]


import collections
from itertools import (
    chain,
    groupby,
    )
import socket

from maasserver import logger
from maasserver.exceptions import MAASException
from maasserver.models.config import Config
from maasserver.models.nodegroup import NodeGroup
from maasserver.server_address import get_maas_facing_server_address
from netaddr import IPAddress
from provisioningserver.dns.zoneconfig import (
    DNSForwardZoneConfig,
    DNSReverseZoneConfig,
    )


class lazydict(dict):
    """A `dict` that lazily populates itself.

    Somewhat like a :class:`collections.defaultdict`, but that the factory
    function is called with the missing key, and the value returned is saved.
    """

    __slots__ = ("factory", )

    def __init__(self, factory):
        super(lazydict, self).__init__()
        self.factory = factory

    def __missing__(self, key):
        value = self[key] = self.factory(key)
        return value


def sequence(thing):
    """Make a sequence from `thing`.

    If `thing` is a sequence, return it unaltered. If it's iterable, return a
    list of its elements. Otherwise, return `thing` as the sole element in a
    new list.
    """
    if isinstance(thing, collections.Sequence):
        return thing
    elif isinstance(thing, collections.Iterable):
        return list(thing)
    else:
        return [thing]


def get_hostname_ip_mapping(nodegroup):
    """Return a mapping {hostnames -> ips} for the allocated nodes in
    `nodegroup`.

    This is backward-compatibility layer which combines the mappings from
    StaticIPAddressManager.get_hostname_ip_mapping and
    DHCPLeaseManager.get_hostname_ip_mapping.  The latter is used to retrieve
    the hostname -> ip mappings for the allocated nodes with an IP in the
    dynamic range (i.e. the nodes that have been allocated before the static
    mapping was introduced).
    """
    # Circular imports.
    from maasserver.models.staticipaddress import StaticIPAddress
    from maasserver.models.dhcplease import DHCPLease
    mapping = DHCPLease.objects.get_hostname_ip_mapping(nodegroup)
    static_mapping = StaticIPAddress.objects.get_hostname_ip_mapping(nodegroup)
    # The static mapping entries take precedence over the dynamic mapping
    # entries.
    mapping.update(static_mapping)
    return mapping


class DNSException(MAASException):
    """An error occured when setting up MAAS's DNS server."""


WARNING_MESSAGE = (
    "The DNS server will use the address '%s',  which is inside the "
    "loopback network.  This may not be a problem if you're not using "
    "MAAS's DNS features or if you don't rely on this information.  "
    "Be sure to configure the DEFAULT_MAAS_URL setting in MAAS's "
    "/etc/maas/maas_local_settings.py.")


def warn_loopback(ip):
    """Warn if the given IP address is in the loopback network."""
    if IPAddress(ip).is_loopback():
        logger.warn(WARNING_MESSAGE % ip)


def get_dns_server_address(nodegroup=None):
    """Return the DNS server's IP address.

    That address is derived from DEFAULT_MAAS_URL or nodegroup.maas_url.
    """
    try:
        ip = get_maas_facing_server_address(nodegroup)
    except socket.error as e:
        raise DNSException(
            "Unable to find MAAS server IP address: %s.  "
            "MAAS's DNS server requires this IP address for the NS records "
            "in its zone files.  Make sure that the DEFAULT_MAAS_URL setting "
            "has the correct hostname."
            % e.strerror)

    warn_loopback(ip)
    return ip


class ZoneGenerator:
    """Generate zones describing those relating to the given node groups."""

    def __init__(self, nodegroups, serial=None, serial_generator=None):
        """
        :param serial: A serial number to reuse when creating zones in bulk.
        :param serial_generator: As an alternative to `serial`, a callback
            that returns a fresh serial number on every call.
        """
        self.nodegroups = sequence(nodegroups)
        self.serial = serial
        self.serial_generator = serial_generator

    @staticmethod
    def _filter_dns_managed(nodegroups):
        """Return the subset of `nodegroups` for which we manage DNS."""
        return set(
            nodegroup
            for nodegroup in nodegroups
            if nodegroup.manages_dns())

    @staticmethod
    def _get_forward_nodegroups(domains):
        """Return the set of forward nodegroups for the given `domains`.

        These are all nodegroups with any of the given domains.
        """
        return ZoneGenerator._filter_dns_managed(
            NodeGroup.objects.filter(name__in=domains))

    @staticmethod
    def _get_reverse_nodegroups(nodegroups):
        """Return the set of reverse nodegroups among `nodegroups`.

        This is the subset of the given nodegroups that are managed.
        """
        return ZoneGenerator._filter_dns_managed(nodegroups)

    @staticmethod
    def _get_mappings():
        """Return a lazily evaluated nodegroup:mapping dict."""
        return lazydict(get_hostname_ip_mapping)

    @staticmethod
    def _get_networks():
        """Return a lazily evaluated nodegroup:network dict."""
        return lazydict(lambda ng: [
            interface.network for interface in ng.get_managed_interfaces()])

    @staticmethod
    def _get_srv_mappings():
        """Return list of srv records.

        Each srv record is a dictionary with the following required keys
        srv, port, target. Optional keys are priority and weight.
        """
        # Avoid circular imports.
        from provisioningserver.dns.config import SRVRecord

        windows_kms_host = Config.objects.get_config("windows_kms_host")
        if windows_kms_host is None or windows_kms_host == '':
            return
        yield SRVRecord(
            service='_vlmcs._tcp', port=1688, target=windows_kms_host,
            priority=0, weight=0)

    @staticmethod
    def _gen_forward_zones(nodegroups, serial, mappings, srv_mappings):
        """Generator of forward zones, collated by domain name."""
        get_domain = lambda nodegroup: nodegroup.name
        dns_ip = get_dns_server_address()
        forward_nodegroups = sorted(nodegroups, key=get_domain)
        for domain, nodegroups in groupby(forward_nodegroups, get_domain):
            nodegroups = list(nodegroups)
            # A forward zone encompassing all nodes in the same domain.
            yield DNSForwardZoneConfig(
                domain, serial=serial, dns_ip=dns_ip,
                mapping={
                    hostname: ip
                    for nodegroup in nodegroups
                    for hostname, ip in mappings[nodegroup].items()
                    },
                srv_mapping=set(srv_mappings)
            )

    @staticmethod
    def _gen_reverse_zones(nodegroups, serial, mappings, networks):
        """Generator of reverse zones, sorted by network."""
        get_domain = lambda nodegroup: nodegroup.name
        reverse_nodegroups = sorted(nodegroups, key=networks.get)
        for nodegroup in reverse_nodegroups:
            for network in networks[nodegroup]:
                mapping = mappings[nodegroup]
                yield DNSReverseZoneConfig(
                    get_domain(nodegroup), serial=serial, mapping=mapping,
                    network=network
                )

    def __iter__(self):
        """Iterate over zone configs.

        Yields `DNSForwardZoneConfig` and `DNSReverseZoneConfig` configs.
        """
        # For testing and such it's fine if we don't have a serial, but once
        # we get to this point, we really need one.
        assert not (self.serial is None and self.serial_generator is None), (
            "No serial number or serial number generator specified.")

        forward_nodegroups = self._get_forward_nodegroups(
            {nodegroup.name for nodegroup in self.nodegroups})
        reverse_nodegroups = self._get_reverse_nodegroups(self.nodegroups)
        mappings = self._get_mappings()
        networks = self._get_networks()
        srv_mappings = self._get_srv_mappings()
        serial = self.serial or self.serial_generator()
        return chain(
            self._gen_forward_zones(
                forward_nodegroups, serial, mappings, srv_mappings),
            self._gen_reverse_zones(
                reverse_nodegroups, serial, mappings, networks),
            )

    def as_list(self):
        """Return the zones as a list."""
        return list(self)
