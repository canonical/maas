# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

""":class:`TimestampedModel` tests."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from datetime import (
    datetime,
    timedelta,
)
from random import randint

from django.db import transaction
from maasserver.models.timestampedmodel import now
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.tests.models import TimestampedModelTestModel
from maastesting.djangotestcase import (
    DjangoTransactionTestCase,
    TestModelMixin,
)


def make_time_in_the_recent_past():
    many_seconds_ago = timedelta(seconds=randint(1, 999999))
    return datetime.now() - many_seconds_ago


class TimestampedModelTest(TestModelMixin, MAASServerTestCase):
    """Testing for the class `TimestampedModel`."""

    app = 'maasserver.tests'

    def test_created_populated_when_object_saved(self):
        obj = TimestampedModelTestModel()
        obj.save()
        self.assertIsNotNone(obj.created)

    def test_updated_populated_when_object_saved(self):
        obj = TimestampedModelTestModel()
        obj.save()
        self.assertIsNotNone(obj.updated)

    def test_updated_and_created_are_the_same_after_first_save(self):
        obj = TimestampedModelTestModel()
        obj.save()
        self.assertEqual(obj.created, obj.updated)

    def test_created_not_modified_by_subsequent_calls_to_save(self):
        obj = TimestampedModelTestModel()
        obj.save()
        old_created = obj.created
        obj.save()
        self.assertEqual(old_created, obj.created)

    def test_on_first_save_created_not_clobbered(self):
        created = make_time_in_the_recent_past()
        obj = TimestampedModelTestModel(created=created)
        obj.save()
        self.assertEquals(created, obj.created)

    def test_on_first_save_created_and_updated_same_if_created_set(self):
        created = make_time_in_the_recent_past()
        obj = TimestampedModelTestModel(created=created)
        obj.save()
        self.assertEqual(created, obj.created)
        self.assertEqual(created, obj.updated)

    def test_on_first_save_updated_set_same_as_created_even_if_set(self):
        created = make_time_in_the_recent_past()
        updated = make_time_in_the_recent_past()
        obj = TimestampedModelTestModel(created=created, updated=updated)
        obj.save()
        self.assertEquals(created, obj.created)
        self.assertEquals(created, obj.updated)


class TimestampedModelTransactionalTest(
        TestModelMixin, DjangoTransactionTestCase):

    app = 'maasserver.tests'

    def test_created_bracketed_by_before_and_after_time(self):
        before = now()
        obj = TimestampedModelTestModel()
        obj.save()
        transaction.commit()
        after = now()
        self.assertLessEqual(before, obj.created)
        self.assertGreaterEqual(after, obj.created)

    def test_updated_is_updated_when_object_saved(self):
        obj = TimestampedModelTestModel()
        obj.save()
        old_updated = obj.updated
        transaction.commit()
        obj.save()
        self.assertLessEqual(old_updated, obj.updated)


class UtilitiesTest(MAASServerTestCase):

    def test_now_returns_datetime(self):
        self.assertIsInstance(now(), datetime)

    def test_now_returns_same_datetime_inside_transaction(self):
        date_now = now()
        self.assertEqual(date_now, now())


class UtilitiesTransactionalTest(DjangoTransactionTestCase):

    def test_now_returns_transaction_time(self):
        date_now = now()
        # Perform a write database operation.
        obj = TimestampedModelTestModel()
        obj.save()
        transaction.commit()
        self.assertLessEqual(date_now, now())
