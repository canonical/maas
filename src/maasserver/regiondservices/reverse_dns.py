# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Reverse DNS service."""

from typing import List

from twisted.application.service import Service
from twisted.internet import defer

from maasserver.listener import PostgresListenerService
from maasserver.models import RDNS, RegionController
from maasserver.utils.threads import deferToDatabase
from provisioningserver.logger import LegacyLogger
from provisioningserver.utils.network import reverseResolve
from provisioningserver.utils.twisted import suppress

log = LegacyLogger()


class ReverseDNSService(Service):
    """Service to resolve and cache reverse DNS names for neighbour entries."""

    def __init__(self, postgresListener: PostgresListenerService = None):
        super().__init__()
        self.listener = postgresListener
        # We will cache a reference to the region model object so we don't
        # need to look it up every time a DNS entry changes.
        self.region = None

    @defer.inlineCallbacks
    def startService(self):
        super().startService()
        self.region = yield deferToDatabase(
            RegionController.objects.get_running_controller
        )
        if self.listener is not None:
            self.listener.register("neighbour", self.consumeNeighbourEvent)

    def stopService(self):
        if self.listener is not None:
            self.listener.unregister("neighbour", self.consumeNeighbourEvent)
        return super().stopService()

    def set_rdns_entry(self, ip: str, results: List[str]):
        """Set the reverse-DNS entry for the specified IP address.

        Must run in a thread where database access is permitted.

        :param ip: the IP address to update.
        :param results: a non-empty list of hostnames for the specified IP,
            in "preferred" order.
        """
        RDNS.objects.set_current_entry(ip, results, self.region)

    def delete_rdns_entry(self, ip: str):
        """Delete the reverse-DNS entry for the specified IP address.

        Must run in a thread where database access is permitted.

        :param ip: the IP address to delete.
        """
        RDNS.objects.delete_current_entry(ip, self.region)

    @defer.inlineCallbacks
    def consumeNeighbourEvent(self, action: str = None, cidr: str = None):
        """Given an event from the postgresListener, resolve RDNS for an IP.

        This method is called when an observed neighbour is changed.

        :param action: one of {'create', 'update', 'delete'}
        :param cidr: the 'ip' field in the neighbour table, after PostgreSQL
            casts it to a string. It will end up looking like "x.x.x.x/32"
            or "yyyy:yyyy::yyyy/128".
        """
        ip = cidr.split("/")[0]  # Strip off the "/<prefixlen>".
        if action in ("create", "update"):
            # XXX mpontillo 2016-10-19: We might consider throttling this on
            # a per-IP-address basis, both because multiple racks can observe
            # the same IP address, and because an IP address might repeatedly
            # go back-and-forth between two MACs in the case of a duplicate IP
            # address.
            results = yield reverseResolve(ip).addErrback(
                suppress, defer.TimeoutError, instead=None
            )
            if results is not None:
                if len(results) > 0:
                    yield deferToDatabase(self.set_rdns_entry, ip, results)
                else:
                    yield deferToDatabase(self.delete_rdns_entry, ip)
            else:
                # A return of 'None' indicates a timeout or other possibly-
                # temporary failure, so take no action.
                pass
        elif action == "delete":
            yield deferToDatabase(self.delete_rdns_entry, ip)
        else:
            log.msg(
                "Unsupported event from listener: action=%r, cidr=%r"
                % (action, cidr),
                system="reverse-dns",
            )
