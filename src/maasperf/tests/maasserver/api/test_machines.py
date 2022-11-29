# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from django.urls import reverse
from piston3.emitters import Emitter
from piston3.handler import typemapper

from maasserver.api.machines import MachinesHandler
from maastesting.http import make_HttpRequest


class DummyEmitter(Emitter):
    def render(self, request):
        self.construct()


def test_perf_list_machines_MachineHandler_api_endpoint(
    perf, admin_api_client
):
    with perf.record("test_perf_list_machines_MachineHandler_api_endpoint"):
        admin_api_client.get(reverse("machines_handler"))


def test_perf_list_machines_MachinesHander_direct_call(perf, admin):
    handler = MachinesHandler()
    request = make_HttpRequest()
    request.user = admin

    with perf.record("test_perf_list_machines_MachinesHander_direct_call"):
        emitter = DummyEmitter(
            handler.read(request),
            typemapper,
            handler,
            handler.fields,
            anonymous=False,
        )
        emitter.render(request)


def test_perf_list_machines_MachinesHander_only_objects(perf, admin):
    handler = MachinesHandler()
    request = make_HttpRequest()
    request.user = admin

    with perf.record("test_perf_list_machines_MachinesHander_only_objects"):
        list(handler.read(request))
