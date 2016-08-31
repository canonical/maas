# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Networks monitoring service for region controllers."""

__all__ = [
    "RegionNetworksMonitoringService",
]

from maasserver.models.node import RegionController
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.utils.services import NetworksMonitoringService


class RegionNetworksMonitoringService(NetworksMonitoringService):
    """Region service to monitor network interfaces for config changes.

    Arrange for this to run on the master regiond process only.
    """

    def recordInterfaces(self, interfaces):
        """Record the interfaces information."""
        return deferToDatabase(self.recordInterfacesIntoDatabase, interfaces)

    def reportNeighbours(self, neighbours):
        """Record the specified list of neighbours."""
        return deferToDatabase(self.recordNeighboursIntoDatabase, neighbours)

    def reportMDNSEntries(self, mdns):
        """Record the specified list of mDNS entries."""
        return deferToDatabase(self.recordMDNSEntriesIntoDatabase, mdns)

    @transactional
    def recordInterfacesIntoDatabase(self, interfaces):
        """Record the interfaces information."""
        region_controller = RegionController.objects.get_running_controller()
        region_controller.update_interfaces(interfaces)

    @transactional
    def recordNeighboursIntoDatabase(self, neighbours):
        """Record the interfaces information."""
        region_controller = RegionController.objects.get_running_controller()
        region_controller.report_neighbours(neighbours)

    @transactional
    def recordMDNSEntriesIntoDatabase(self, mdns):
        """Record the mDNS entries."""
        region_controller = RegionController.objects.get_running_controller()
        region_controller.report_mdns_entries(mdns)
