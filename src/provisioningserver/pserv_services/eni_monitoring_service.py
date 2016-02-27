# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""/etc/network/interfaces monitoring service."""

__all__ = [
    "ENIMonitoringService",
    ]


from datetime import timedelta

from provisioningserver.eni import (
    clear_current_interfaces_definition,
    get_interfaces_definition,
)
from provisioningserver.logger.log import get_maas_logger
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.rpc.region import UpdateInterfaces
from provisioningserver.utils.twisted import (
    pause,
    retries,
)
from twisted.application.internet import TimerService
from twisted.internet.defer import inlineCallbacks
from twisted.internet.threads import deferToThread


maaslog = get_maas_logger("eni.monitor")


class ENIMonitoringService(TimerService, object):
    """Service to monitor the interfaces definition on the rack controller.

    Parsed the "/etc/network/interfaces" and "ip addr show" to update the
    region controller anytime the interfaces definition changes.

    :param reactor: An `IReactor` instance.
    """

    check_interval = timedelta(seconds=30).total_seconds()

    def __init__(self, client_service, reactor):
        # Call self.try_update_interfaces() every self.check_interval.
        super(ENIMonitoringService, self).__init__(
            self.check_interval, self.tryUpdateInterfaces)
        self.clock = reactor
        self.client_service = client_service

    @inlineCallbacks
    def updateInterfaces(self):
        """Update the interface definition and send it to the region when it
        changes."""
        client = None
        for elapsed, remaining, wait in retries(15, 5, self.clock):
            try:
                client = self.client_service.getClient()
                break
            except NoConnectionsAvailable:
                yield pause(wait, self.clock)
        else:
            maaslog.error(
                "Can't update rack controllers interface definition, no RPC "
                "connection to region.")
            return

        interfaces, changed = yield deferToThread(get_interfaces_definition)
        if changed:
            try:
                yield client(
                    UpdateInterfaces,
                    system_id=client.localIdent,
                    interfaces=interfaces)
            except:
                # Failed to update the region. Clear the interface definition
                # so next time it will update the region.
                clear_current_interfaces_definition()
                raise

    @inlineCallbacks
    def tryUpdateInterfaces(self):
        try:
            yield self.updateInterfaces()
        except Exception as error:
            maaslog.error(
                "Failed to update region about the interface "
                "configuration: %s",
                str(error))
