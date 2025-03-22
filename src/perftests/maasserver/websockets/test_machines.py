# Copyright 2022-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
import math

from maasserver.models import Machine
from maasserver.websockets.handlers.machine import MachineHandler


def test_perf_list_machines_Websocket_endpoint(perf, admin, maasdb):
    # This should test the websocket calls that are used to load
    # the machine listing page on the initial page load.
    machine_count = Machine.objects.all().count()
    expected_pages = math.ceil(machine_count / 50)
    num_pages = 0
    with perf.record("test_perf_list_machines_Websocket_endpoint"):
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
        response = ws_handler.list(params)
        num_pages = response["num_pages"]
    assert num_pages == expected_pages


def test_perf_list_machines_Websocket_endpoint_all(perf, admin, maasdb):
    # How long would it take to list all the machines using the
    # websocket without any pagination.
    machine_count = Machine.objects.all().count()
    with perf.record("test_perf_list_machines_Websocket_endpoint_all"):
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
        response = ws_handler.list(params)
    assert response["count"] == machine_count
