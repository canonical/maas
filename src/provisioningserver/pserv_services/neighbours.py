# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""A service that maintains a fresh idea of our network neighbours."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'NeighboursService',
    ]

from netaddr import (
    EUI,
    IPAddress,
)
from provisioningserver.utils.network import NeighboursProtocol
from twisted.application.internet import TimerService
from twisted.internet import reactor
from twisted.python import log


class NeighboursService(TimerService, object):
    """Update our idea of the local network neighbourhood every second."""

    command = b"ip", b"neigh"

    def __init__(self):
        self._ip_to_mac, self._mac_to_ip = {}, {}
        super(NeighboursService, self).__init__(1.0, self.update)

    def update(self):
        try:
            neigh = NeighboursProtocol()
            neigh.done.addCallback(self.set)
            neigh.done.addErrback(log.err, "Updating neighbours failed.")
            reactor.spawnProcess(neigh, self.command[0], self.command)
            return neigh.done
        except:
            log.err(None, "Updating neighbours failed.")

    def set(self, mappings):
        self._ip_to_mac, self._mac_to_ip = mappings

    def find_ip_addresses(self, address):
        """Return MAC addresses related to the address given.

        :param address: An `EUI` (MAC address).
        :return: A set of `IPAddress`.
        """
        if isinstance(address, EUI):
            if address in self._mac_to_ip:
                return self._mac_to_ip[address]
            else:
                return set()
        else:
            raise TypeError(
                "Not a netaddr.IPAddress or netaddr.EUI: %r"
                % (address,))

    def find_ip_address(self, address):
        """Return the first neighbour for the given address, or `None`.

        :param address: An `EUI` (MAC address).
        :return: An `IPAddress`, or `None`.
        """
        related = self.find_ip_addresses(address)
        if len(related) >= 1:
            return min(related)
        else:
            return None

    def find_mac_addresses(self, address):
        """Return addresses related to the address given.

        :param address: An `IPAddress`.
        :return: A set of `EUI` (MAC addresses).
        """
        if isinstance(address, IPAddress):
            if address in self._ip_to_mac:
                return self._ip_to_mac[address]
            else:
                return set()
        else:
            raise TypeError(
                "Not a netaddr.IPAddress or netaddr.EUI: %r"
                % (address,))

    def find_mac_address(self, address):
        """Return the first neighbour for the given address, or `None`.

        :param address: An `IPAddress`.
        :return: An `EUI`, or `None`.
        """
        related = self.find_mac_addresses(address)
        if len(related) >= 1:
            return min(related)
        else:
            return None
