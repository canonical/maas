# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maastesting.perftest import perf_test


@perf_test(5, db_only=True, allowed_drift=1, commit_transaction=True)
def test_perf_create_machines():
    from maasserver.testing.factory import factory

    # TODO use create machines script
    for _ in range(30):
        factory.make_Machine()


@perf_test(10, db_only=True, allowed_drift=2)
def test_perf_list_machines():
    from maasserver.models import Machine

    list(Machine.objects.all())
