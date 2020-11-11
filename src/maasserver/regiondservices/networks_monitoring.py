# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Networks monitoring service for region controllers."""


from maasserver.models.node import RegionController
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.utils.services import NetworksMonitoringService


class RegionNetworksMonitoringService(NetworksMonitoringService):
    """Region service to monitor network interfaces for config changes.

    Arrange for this to run on the master regiond process only.
    """

    def getDiscoveryState(self):
        """Get interface monitoring state from the region."""
        return deferToDatabase(self.getInterfaceMonitoringStateFromDatabase)

    def recordInterfaces(self, interfaces, hints=None):
        """Record the interfaces information."""
        return deferToDatabase(
            self.recordInterfacesIntoDatabase, interfaces, hints
        )

    def reportNeighbours(self, neighbours):
        """Record the specified list of neighbours."""
        return deferToDatabase(self.recordNeighboursIntoDatabase, neighbours)

    def reportMDNSEntries(self, mdns):
        """Record the specified list of mDNS entries."""
        return deferToDatabase(self.recordMDNSEntriesIntoDatabase, mdns)

    @transactional
    def getInterfaceMonitoringStateFromDatabase(self):
        """Record the interfaces information."""
        region_controller = RegionController.objects.get_running_controller()
        return region_controller.get_discovery_state()

    @transactional
    def recordInterfacesIntoDatabase(self, interfaces, hints):
        """Record the interfaces information."""
        region_controller = RegionController.objects.get_running_controller()
        region_controller.update_interfaces(interfaces, hints)

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
