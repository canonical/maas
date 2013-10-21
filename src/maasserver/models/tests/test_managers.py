# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver model managers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.testing.testcase import MAASServerTestCase
from maasserver.tests.models import (
    BulkManagerParentTestModel,
    BulkManagerTestModel,
    )
from maastesting.djangotestcase import TestModelMixin


class BulkManagerTest(TestModelMixin, MAASServerTestCase):

    app = 'maasserver.tests'

    def test_manager_iterator_uses_cache(self):
        parents = set()
        for i in range(3):
            parents.add(BulkManagerParentTestModel.objects.create())
        for i in range(10):
            for parent in parents:
                BulkManagerTestModel.objects.create(parent=parent)
        parents = BulkManagerParentTestModel.objects.all().prefetch_related(
            'bulkmanagertestmodel_set')
        # Only two queries are used to fetch all the objects:
        # One to fetch the parents, one to fetch the childrens (the query from
        # the prefetch_related statement).
        # Even if we call iterator() on the related objects, the cache is
        # used because BulkManagerTestModel has a manager based on
        # BulkManager.
        self.assertNumQueries(
            2,
            lambda: [list(parent.bulkmanagertestmodel_set.iterator())
                     for parent in parents])
