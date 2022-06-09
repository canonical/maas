# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from django.urls import reverse

from maasserver.api.machines import MachinesHandler
from maastesting.http import make_HttpRequest
from maastesting.perftest import perf_test


@perf_test()
def test_perf_list_machines_MachineHandler_api_endpoint(api_client):
    api_client.get(reverse("machines_handler"))


@perf_test(db_only=True)
def test_perf_list_machines_MachinesHander_direct_call(maas_user):
    handler = MachinesHandler()
    request = make_HttpRequest()
    request.user = maas_user
    handler.read(request)
