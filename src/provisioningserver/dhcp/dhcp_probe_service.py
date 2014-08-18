# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Periodic DHCP probing service."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "PeriodicDHCPProbeService",
    ]


from provisioningserver.dhcp import detect
from provisioningserver.logger.log import get_maas_logger
from twisted.application.internet import TimerService
from twisted.internet.defer import inlineCallbacks


maaslog = get_maas_logger("probe_dhcp")


class PeriodicDHCPProbeService(TimerService, object):
    """Service to probe for DHCP servers on this cluster's network.

    Built on top of Twisted's `TimerService`.

    :param client_service: A `ClusterClientService` instance for talking
        to the region controller.
    :param reactor: An `IReactor` instance.
    :param cluster_uuid: This cluster's UUID.
    """

    check_interval = 60  # 1 minute.

    def __init__(self, reactor):
        # Call self.check() every self.check_interval.
        super(PeriodicDHCPProbeService, self).__init__(
            self.check_interval, self.probe_dhcp)
        self.clock = reactor

    @inlineCallbacks
    def probe_dhcp(self):
        maaslog.debug("Running periodic DHCP probe.")
        yield detect.periodic_probe_task()
        maaslog.debug("Finished periodic DHCP probe.")
