from twisted.internet.defer import inlineCallbacks

from maasserver.models import ControllerInfo, RegionController
from maasserver.utils.threads import deferToDatabase
from provisioningserver.rackdservices.version_update_check import (
    VersionUpdateCheckService,
)


class RegionVersionUpdateCheckService(VersionUpdateCheckService):
    """Periodically check and update region versions."""

    @inlineCallbacks
    def process_versions_info(self, versions_info):
        yield deferToDatabase(self._process_version, versions_info)

    def _process_version(self, versions_info):
        region = RegionController.objects.get_running_controller()
        ControllerInfo.objects.set_versions_info(region, versions_info)
