# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasserver.websockets.handlers.machine import MachineHandler
from maastesting.perftest import perf_test, profile


@perf_test(db_only=True)
def test_perf_list_machines_Websocket_endpoint(admin):
    ws_handler = MachineHandler(admin, {}, None)

    with profile("test_perf_list_machines_Websocket_endpoint"):
        ws_handler.list({})
