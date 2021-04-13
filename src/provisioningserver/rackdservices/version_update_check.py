# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Service to periodically check for version updates."""


import dataclasses
from datetime import timedelta

from twisted.application.internet import TimerService
from twisted.internet.defer import inlineCallbacks, returnValue

from provisioningserver.enum import CONTROLLER_INSTALL_TYPE
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.rpc.region import UpdateControllerState
from provisioningserver.utils.deb import get_deb_versions_info
from provisioningserver.utils.snap import (
    get_snap_versions_info,
    running_in_snap,
)
from provisioningserver.utils.twisted import pause


class VersionUpdateCheckService(TimerService):
    """Periodically check and report version updates."""

    check_interval = timedelta(minutes=5).total_seconds()

    def __init__(self, clientService):
        super().__init__(self.check_interval, self._run_check)
        self.clientService = clientService

    @inlineCallbacks
    def _run_check(self):
        client = yield self._getRPCClient()
        yield client(
            UpdateControllerState,
            system_id=client.localIdent,
            scope="versions",
            state=self._get_versions_state(),
        )

    def _get_versions_state(self):
        state = {}

        versions_info = None
        install_type = None
        if running_in_snap():
            versions_info = get_snap_versions_info()
            install_type = CONTROLLER_INSTALL_TYPE.SNAP
        else:
            install_type = CONTROLLER_INSTALL_TYPE.DEB
            versions_info = get_deb_versions_info()
        if versions_info:
            state[install_type] = dataclasses.asdict(versions_info)
        return state

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
