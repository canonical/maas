# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import math
from urllib.parse import parse_qs, urlparse

from sqlalchemy import func, select

from maasapiserver.v3.api.models.requests.query import MAX_PAGE_SIZE
from maasapiserver.v3.constants import V3_API_PREFIX
from maasserver.enum import NODE_TYPE
from maasservicelayer.db.tables import NodeTable


async def get_machine_count(conn):
    stmt = (
        select(func.count())
        .select_from(NodeTable)
        .where(NodeTable.c.node_type == NODE_TYPE.MACHINE)
    )
    result = await conn.execute(stmt)
    return result.scalar()


async def test_perf_list_machines_APIv3_endpoint(
    perf,
    authenticated_admin_api_client_v3,
    db_connection,
):
    api_client = authenticated_admin_api_client_v3
    # This should test the APIv3 calls that are used to load
    # the machine listing page on the initial page load.
    machine_count = await get_machine_count(db_connection)

    expected_items = machine_count if machine_count < 50 else 50
    response = None
    with perf.record("test_perf_list_machines_APIv3_endpoint"):
        # Extracted from a clean load of labmaas with empty local
        # storage
        params = {
            "size": 50,
        }

        response = await api_client.get(
            f"{V3_API_PREFIX}/machines", params=params
        )

    assert response.status_code == 200
    assert len(response.json()["items"]) == expected_items


async def test_perf_list_machines_APIv3_endpoint_all(
    perf,
    authenticated_admin_api_client_v3,
    db_connection,
):
    api_client = authenticated_admin_api_client_v3
    # How long would it take to list all the machines using the
    # APIv3 without any pagination.
    machine_count = await get_machine_count(db_connection)
    machine_pages = math.ceil(machine_count / MAX_PAGE_SIZE)
    responses = [None] * machine_pages
    with perf.record("test_perf_list_machines_APIv3_endpoint_all"):
        # Extracted from a clean load of labmaas with empty local
        # storage
        token = None
        for page in range(machine_pages):
            params = {
                "size": MAX_PAGE_SIZE,
            }
            if token:
                params["token"] = token
            response = await api_client.get(
                f"{V3_API_PREFIX}/machines", params=params
            )
            responses[page] = response
            if next_page := response.json()["next"]:
                token = parse_qs(urlparse(next_page).query)["token"][0]
            else:
                token = None
    assert token is None
    assert all([r.status_code == 200 for r in responses])
    assert sum([len(r.json()["items"]) for r in responses]) == machine_count


async def test_perf_list_machines_APIv3_endpoint_all_local_filtering(
    perf,
    authenticated_admin_api_client_v3,
    db_connection,
):
    api_client = authenticated_admin_api_client_v3
    # How long would it take to list all the machines using the
    # APIv3 without any pagination and filter them locally
    machine_count = await get_machine_count(db_connection)
    machine_pages = math.ceil(machine_count / MAX_PAGE_SIZE)
    responses = [None] * machine_pages
    filtered_responses = [None] * machine_pages
    with perf.record(
        "test_perf_list_machines_APIv3_endpoint_all_local_filtering"
    ):
        # Extracted from a clean load of labmaas with empty local
        # storage
        token = None
        for page in range(machine_pages):
            params = {
                "size": MAX_PAGE_SIZE,
            }
            if token:
                params["token"] = token
            response = await api_client.get(
                f"{V3_API_PREFIX}/machines", params=params
            )
            responses[page] = response
            filtered_response = [
                machine
                for machine in response.json()["items"]
                if machine["cpu_count"] == 1 and machine["memory_MiB"] == 1024
            ]
            filtered_responses[page] = filtered_response
            if next_page := response.json()["next"]:
                token = parse_qs(urlparse(next_page).query)["token"][0]
            else:
                token = None
    assert token is None
    assert all([r.status_code == 200 for r in responses])
    assert sum([len(r.json()["items"]) for r in responses]) == machine_count
    assert sum([len(r) for r in filtered_responses]) == machine_count // 10


async def test_perf_list_machines_APIv3_endpoint_all_pci_devices(
    perf,
    authenticated_admin_api_client_v3,
    db_connection,
):
    api_client = authenticated_admin_api_client_v3
    # How long would it take to list all the machines' pci devices using the
    # APIv3 without any pagination and filter them locally
    machine_count = await get_machine_count(db_connection)
    machine_pages = math.ceil(machine_count / MAX_PAGE_SIZE)
    responses = [None] * machine_pages
    filtered_devices = [None] * machine_pages
    with perf.record("test_perf_list_machines_APIv3_endpoint_all_pci_devices"):
        # Extracted from a clean load of labmaas with empty local
        # storage
        token = None
        for page in range(machine_pages):
            params = {
                "size": MAX_PAGE_SIZE,
            }
            if token:
                params["token"] = token
            response = await api_client.get(
                f"{V3_API_PREFIX}/machines", params=params
            )
            responses[page] = response
            devices = []
            for machine in response.json()["items"]:
                devices_response = await api_client.get(
                    f"{V3_API_PREFIX}/machines/{machine['system_id']}/pci_devices"
                )
                # there is exactly one device with vendor_id and product_id
                # equal to "cafe" for each machine
                device = next(
                    (
                        device
                        for device in devices_response.json()["items"]
                        if device["vendor_id"] == "cafe"
                        and device["product_id"] == "cafe"
                    )
                )
                devices.append(device)
            filtered_devices[page] = devices

            if next_page := response.json()["next"]:
                token = parse_qs(urlparse(next_page).query)["token"][0]
            else:
                token = None
    assert token is None
    assert all([r.status_code == 200 for r in responses])
    assert sum([len(r.json()["items"]) for r in responses]) == machine_count
    assert sum([len(r) for r in filtered_devices]) == machine_count
