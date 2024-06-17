# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import math

from django.contrib.auth.hashers import make_password
from django.db import transaction
import pytest

from maasapiserver.client import APIServerClient
from maasapiserver.v3.api.models.requests.query import MAX_PAGE_SIZE
from maasserver.models import Machine


@pytest.mark.allow_transactions
def test_perf_list_machines_APIv3_endpoint(perf, maas_user, maasapiserver):
    maas_user.password = make_password("test", hasher="pbkdf2_sha256")
    maas_user.save()
    transaction.commit()
    api_client = APIServerClient("", version=3)
    resp = api_client.post(
        "auth/login", data={"username": maas_user.username, "password": "test"}
    )
    token = resp.json()["access_token"]
    headers = {"Authorization": "bearer " + token}

    # This should test the APIv3 calls that are used to load
    # the machine listing page on the initial page load.
    machine_count = Machine.objects.all().count()
    expected_items = machine_count if machine_count < 50 else 50
    response = None
    with perf.record("test_perf_list_machines_APIv3_endpoint"):
        # Extracted from a clean load of labmaas with empty local
        # storage
        params = {
            "page": 1,
            "size": 50,
        }

        response = api_client.get("machines", headers=headers, params=params)

    assert response.ok
    assert len(response.json()["items"]) == expected_items


@pytest.mark.allow_transactions
def test_perf_list_machines_APIv3_endpoint_all(perf, maas_user, maasapiserver):
    maas_user.password = make_password("test", hasher="pbkdf2_sha256")
    maas_user.save()
    transaction.commit()
    api_client = APIServerClient("", version=3)
    resp = api_client.post(
        "auth/login", data={"username": maas_user.username, "password": "test"}
    )
    token = resp.json()["access_token"]
    headers = {"Authorization": "bearer " + token}

    # How long would it take to list all the machines using the
    # APIv3 without any pagination.
    machine_count = Machine.objects.all().count()
    machine_pages = math.ceil(machine_count / MAX_PAGE_SIZE)
    responses = [None] * machine_pages
    with perf.record("test_perf_list_machines_APIv3_endpoint_all"):
        # Extracted from a clean load of labmaas with empty local
        # storage
        for page in range(1, machine_pages + 1):
            params = {
                "page": page,
                "size": MAX_PAGE_SIZE,
            }
            response = api_client.get(
                "machines", headers=headers, params=params
            )
            responses[page - 1] = response

    assert all([r.ok for r in responses])
    assert sum([len(r.json()["items"]) for r in responses]) == machine_count
