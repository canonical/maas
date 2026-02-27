# Copyright 2022-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
from django.contrib.auth.models import User
from django.urls import reverse
from piston3.emitters import Emitter
from piston3.handler import typemapper

from maasserver.api.machines import MachinesHandler
from maasserver.models import Machine
from maasserver.models.user import get_auth_tokens
from maasserver.testing.testclient import MAASSensibleOAuthClient
from maastesting.http import make_HttpRequest


class DummyEmitter(Emitter):
    def render(self, request):
        self.construct()


def test_perf_list_machines_MachineHandler_api_endpoint(
    perf, maasdb, mock_maas_env, openfga_server
):
    admin = User.objects.filter(is_superuser=True).first()
    if admin is None:
        raise Exception("No superuser found in the database.")
    client = MAASSensibleOAuthClient(
        user=admin, token=get_auth_tokens(admin)[0]
    )

    machine_count = Machine.objects.all().count()

    with perf.record("test_perf_list_machines_MachineHandler_api_endpoint"):
        retrieved_machines = client.get(reverse("machines_handler"))
        assert machine_count == len(retrieved_machines.json())


def test_perf_list_machines_MachinesHander_direct_call(
    perf, maasdb, mock_maas_env, openfga_server
):
    admin = User.objects.filter(is_superuser=True).first()
    if admin is None:
        raise Exception("No superuser found in the database.")

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


def test_perf_list_machines_MachinesHander_only_objects(
    perf, maasdb, mock_maas_env, openfga_server
):
    admin = User.objects.filter(is_superuser=True).first()
    if admin is None:
        raise Exception("No superuser found in the database.")

    machine_count = Machine.objects.all().count()

    handler = MachinesHandler()
    request = make_HttpRequest()
    request.user = admin

    with perf.record("test_perf_list_machines_MachinesHander_only_objects"):
        retrieved_machines = list(handler.read(request))
        assert machine_count == len(retrieved_machines)
