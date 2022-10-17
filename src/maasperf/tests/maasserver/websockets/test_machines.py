# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasserver.websockets.handlers.machine import MachineHandler
from maastesting.perftest import perf_test, profile


@perf_test(db_only=True)
def test_perf_list_machines_Websocket_endpoint(admin):
    with profile("test_perf_list_machines_Websocket_endpoint"):
        ws_handler = MachineHandler(admin, {}, None)
        # Extracted from a clean load of labmaas with empty local
        # storage
        params = {
            "filter": {},
            "group_collapsed": [],
            "group_key": "status",
            "page_number": 1,
            "page_size": 50,
            "sort_direction": "descending",
            "sort_key": "hostname",
        }
        ws_handler.list(params)
