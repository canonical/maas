# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Service to periodically check for version updates."""


from abc import abstractmethod
import dataclasses
from datetime import timedelta

from twisted.internet.defer import inlineCallbacks, returnValue

from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.rpc.region import UpdateControllerState
from provisioningserver.utils.deb import get_deb_versions_info
from provisioningserver.utils.services import SingleInstanceService
from provisioningserver.utils.snap import get_snap_versions_info
from provisioningserver.utils.twisted import pause


class VersionUpdateCheckService(SingleInstanceService):
    """Periodically check and process version updates."""

    LOCK_NAME = SERVICE_NAME = "version-update-check"
    INTERVAL = timedelta(minutes=5)

    @inlineCallbacks
    def do_action(self):
        versions_info = self._get_versions_info()
        if versions_info:
            yield self.process_versions_info(versions_info)

    @abstractmethod
    def process_versions_info(self, versions_info):
        """Procecss version information. Must be defined by subclasses."""

    def _get_versions_info(self):
        versions_info = get_snap_versions_info()
        if not versions_info:
            versions_info = get_deb_versions_info()
        return versions_info


class RackVersionUpdateCheckService(VersionUpdateCheckService):
    def __init__(self, clientService, clock=None):
        super().__init__(clock=clock)
        self.clientService = clientService

    @inlineCallbacks
    def process_versions_info(self, versions_info):
        client = yield self._getRPCClient()
        yield client(
            UpdateControllerState,
            system_id=client.localIdent,
            scope="versions",
            state=self._get_state(versions_info),
        )

    def _get_state(self, versions_info):
        return {versions_info.install_type: dataclasses.asdict(versions_info)}

    @inlineCallbacks
    def _getRPCClient(self):
        while self.running:
            try:
                client = yield self.clientService.getClientNow()
            except NoConnectionsAvailable:
                yield pause(1.0)
                continue
            else:
                returnValue(client)
