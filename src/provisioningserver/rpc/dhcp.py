# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to DHCP."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "create_host_maps",
]

from provisioningserver.logger import get_maas_logger
from provisioningserver.omshell import Omshell
from provisioningserver.rpc.exceptions import (
    CannotCreateHostMap,
    CannotRemoveHostMap,
    )
from provisioningserver.utils import ExternalProcessError


maaslog = get_maas_logger("dhcp")


def create_host_maps(mappings, shared_key):
    """Create DHCP host maps for the given mappings.

    :param mappings: A list of dicts containing ``ip_address`` and
        ``mac_address`` keys.
    :param shared_key: The key used to access the DHCP server via OMAPI.
    """
    # See bug 1039362 regarding server_address.
    omshell = Omshell(server_address='127.0.0.1', shared_key=shared_key)
    for mapping in mappings:
        ip_address = mapping["ip_address"]
        mac_address = mapping["mac_address"]
        try:
            omshell.create(ip_address, mac_address)
        except ExternalProcessError as e:
            maaslog.error(
                "Could not create host map for %s with address %s: %s",
                mac_address, ip_address, unicode(e))
            raise CannotCreateHostMap("%s \u2192 %s: %s" % (
                mac_address, ip_address, e.output_as_unicode))


def remove_host_maps(ip_addresses, shared_key):
    """Remove DHCP host maps for the given IP addresses.

    :param ip_addresses: A list of IP addresses.
    :param shared_key: The key used to access the DHCP server via OMAPI.
    """
    # See bug 1039362 regarding server_address.
    omshell = Omshell(server_address='127.0.0.1', shared_key=shared_key)
    for ip_address in ip_addresses:
        try:
            omshell.remove(ip_address)
        except ExternalProcessError as e:
            maaslog.error(
                "Could not remove host map for %s: %s",
                ip_address, unicode(e))
            raise CannotRemoveHostMap("%s: %s" % (
                ip_address, e.output_as_unicode))
