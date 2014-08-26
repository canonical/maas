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


from datetime import timedelta

from provisioningserver.auth import get_recorded_api_credentials
from provisioningserver.cluster_config import get_maas_url
from provisioningserver.dhcp import detect
from provisioningserver.logger.log import get_maas_logger
from twisted.application.internet import TimerService
from twisted.internet.defer import inlineCallbacks
from twisted.internet.threads import deferToThread


maaslog = get_maas_logger("dhcp.probe")


class PeriodicDHCPProbeService(TimerService, object):
    """Service to probe for DHCP servers on this cluster's network.

    Built on top of Twisted's `TimerService`.

    :param reactor: An `IReactor` instance.
    :param cluster_uuid: This cluster's UUID.
    """

    check_interval = timedelta(minutes=1).total_seconds()

    def __init__(self, reactor, cluster_uuid):
        # Call self.check() every self.check_interval.
        super(PeriodicDHCPProbeService, self).__init__(
            self.check_interval, self.try_probe_dhcp)
        self.clock = reactor
        self.uuid = cluster_uuid

    def _probe_dhcp(self, knowledge):
        """Probe for DHCP servers."""
        return deferToThread(detect.periodic_probe_task, knowledge)

    @inlineCallbacks
    def try_probe_dhcp(self):
        # Items that the server must have sent us before we can do
        # this.
        knowledge = {
            'api_credentials': get_recorded_api_credentials(),
            'maas_url': get_maas_url(),
            'nodegroup_uuid': self.uuid,
        }

        if None in knowledge.values():
            # The MAAS server hasn't sent us enough information for
            # us to do this yet.  Leave it for another time.
            maaslog.info(
                "Not probing for rogue DHCP servers; not all "
                "required knowledge received from server yet.  "
                "Missing: %s" % ', '.join(sorted(
                    name for name, value in knowledge.items()
                    if value is None)))
            return
        else:
            maaslog.debug("Running periodic DHCP probe.")
            try:
                d = self._probe_dhcp(knowledge)
                yield d
                maaslog.debug("Finished periodic DHCP probe.")
            except Exception as error:
                maaslog.error(
                    "Unable to probe for rogue DHCP servers: %s"
                    % unicode(error))
