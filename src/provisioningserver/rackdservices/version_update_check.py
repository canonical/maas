# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Service to periodically check for version updates."""


import dataclasses
from datetime import timedelta

from twisted.application.internet import TimerService
from twisted.internet.defer import inlineCallbacks, returnValue

from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.rpc.region import UpdateControllerState
from provisioningserver.utils.snap import get_snap_versions_info
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
        # XXX eventually we'll also report versions for deb-based install
        yield client(
            UpdateControllerState,
            system_id=client.localIdent,
            scope="versions",
            state=self._get_versions_state(),
        )

    def _get_versions_state(self):
        state = {}

        snap_version = get_snap_versions_info()
        if snap_version:
            state["snap"] = dataclasses.asdict(snap_version)
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
