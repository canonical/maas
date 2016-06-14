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

    @transactional
    def recordInterfacesIntoDatabase(self, interfaces):
        """Record the interfaces information."""
        region_controller = RegionController.objects.get_running_controller()
        region_controller.update_interfaces(interfaces)
