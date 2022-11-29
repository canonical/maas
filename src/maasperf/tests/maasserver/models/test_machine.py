# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from django.db import transaction
import pytest

from maasserver.models import Machine


@pytest.mark.allow_transactions
def test_perf_create_machines(perf, factory):
    # TODO use create machines script
    with perf.record("test_perf_create_machines"):
        for _ in range(30):
            factory.make_Machine()
        transaction.commit()


@pytest.mark.usefixtures("maasdb")
def test_perf_list_machines(perf):
    with perf.record("test_perf_list_machines"):
        list(Machine.objects.all())
