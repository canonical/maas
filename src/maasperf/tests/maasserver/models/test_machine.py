# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from django.db import transaction
import pytest

from maasserver.models import Machine


@pytest.mark.django_db
def test_perf_create_machines(perf, factory):
    # TODO use create machines script
    with perf.record("test_perf_create_machines"):
        with transaction.atomic():
            for _ in range(30):
                factory.make_Machine()


@pytest.mark.django_db
def test_perf_list_machines(perf):
    with perf.record("test_perf_list_machines"):
        list(Machine.objects.all())
