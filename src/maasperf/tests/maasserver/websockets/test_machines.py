# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasserver.models import Machine
from maasserver.websockets.handlers.machine import MachineHandler
from maastesting.perftest import perf_test, profile


@perf_test(db_only=True)
def test_perf_list_machines_Websocket_endpoint(admin):
    # This should test the websocket calls that are used to load
    # the machine listing page on the initial page load.
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


@perf_test(db_only=True)
def test_perf_list_machines_Websocket_endpoint_all(admin):
    # How long would it take to list all the machines using the
    # websocket without any pagination.
    machine_count = Machine.objects.all().count()
    with profile("test_perf_list_machines_Websocket_endpoint_all"):
        ws_handler = MachineHandler(admin, {}, None)
        # Extracted from a clean load of labmaas with empty local
        # storage
        params = {
            "filter": {},
            "page_number": 1,
            "page_size": machine_count + 1,
            "sort_direction": "descending",
            "sort_key": "hostname",
        }
        ws_handler.list(params)
