# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasserver.models import Machine
from maastesting.perftest import perf_test


@perf_test(commit_transaction=True, db_only=True)
def test_perf_create_machines(factory):
    # TODO use create machines script
    for _ in range(30):
        factory.make_Machine()


@perf_test(db_only=True)
def test_perf_list_machines():

    list(Machine.objects.all())
