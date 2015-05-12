# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Twisted service that periodically uploads DHCP leases to the region."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "convert_leases_to_mappings",
    "convert_mappings_to_leases",
    "LeaseUploadService",
    ]


from provisioningserver.dhcp.leases import (
    check_lease_changes,
    record_lease_state,
)
from provisioningserver.logger import get_maas_logger
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.rpc.region import UpdateLeases
from provisioningserver.utils.twisted import (
    pause,
    retries,
)
from twisted.application.internet import TimerService
from twisted.internet.defer import inlineCallbacks
from twisted.internet.threads import deferToThread
from twisted.python import log


maaslog = get_maas_logger("lease_upload_service")


def convert_mappings_to_leases(mappings):
    """Convert AMP mappings to record_lease_state() leases.

    Take mappings, as used by UpdateLeases, and turn into leases
    as used by record_lease_state().
    """
    return {
        mapping["ip"]: mapping["mac"]
        for mapping in mappings
    }


def convert_leases_to_mappings(leases):
    """Convert record_lease_state() leases into UpdateLeases mappings.

    Take the leases dict, as returned by record_lease_state(), and
    turn it into a mappings list suitable for transportation in
    the UpdateLeases AMP command.
    """
    return [
        {"ip": ip, "mac": leases[ip]}
        for ip in leases
        ]


class LeaseUploadService(TimerService, object):
    """Twisted service to periodically upload DHCP leases to the region.

    :param client_service: A `ClusterClientService` instance for talking
        to the region controller.
    :param reactor: An `IReactor` instance.
    """

    check_interval = 60  # In seconds.

    def __init__(self, client_service, reactor, cluster_uuid):
        # Call self.try_upload() every self.check_interval.
        super(LeaseUploadService, self).__init__(
            self.check_interval, self.try_upload)
        self.clock = reactor
        self.client_service = client_service
        self.uuid = cluster_uuid
        maaslog.info("LeaseUploadService starting.")

    def try_upload(self):
        """Wrap upload attempts in something that catches Failures.

        Log the full error to the Twisted log, and a concise error to
        the maas log.
        """
        def upload_failure(failure):
            log.err(failure)
            maaslog.error(
                "Failed to upload leases: %s", failure.getErrorMessage())

        return self._get_client_and_start_upload().addErrback(upload_failure)

    @inlineCallbacks
    def _get_client_and_start_upload(self):
        # Retry a few times, since this service usually comes up before
        # the RPC service.
        for elapsed, remaining, wait in retries(15, 5, self.clock):
            try:
                client = self.client_service.getClient()
                break
            except NoConnectionsAvailable:
                yield pause(wait, clock=self.clock)
        else:
            maaslog.error(
                "Failed to connect to region controller, cannot upload leases")
            return
        yield self._start_upload(client)

    @inlineCallbacks
    def _start_upload(self, client):
        maaslog.debug("Scanning DHCP leases...")
        updated_lease_info = yield deferToThread(check_lease_changes)
        if updated_lease_info is None:
            maaslog.debug("No leases changed since last scan")
        else:
            timestamp, leases = updated_lease_info
            record_lease_state(timestamp, leases)
            mappings = convert_leases_to_mappings(leases)
            maaslog.info(
                "Uploading %d DHCP leases to region controller.",
                len(mappings))
            yield client(
                UpdateLeases, uuid=self.uuid, mappings=mappings)
            maaslog.debug("Lease upload complete.")
