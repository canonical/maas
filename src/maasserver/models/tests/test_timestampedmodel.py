# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timedelta
from random import randint

from django.db import transaction
from django.utils import timezone

from maasserver.models.timestampedmodel import now
from maasserver.testing.testcase import (
    MAASLegacyTransactionServerTestCase,
    MAASServerTestCase,
)
from maasserver.tests.models import (
    GenericTestModel,
    TimestampedModelTestModel,
    TimestampedOneToOneTestModel,
)


def make_time_in_the_recent_past():
    many_seconds_ago = timedelta(seconds=randint(1, 999999))
    return timezone.now() - many_seconds_ago


class TestTimestampedModel(MAASLegacyTransactionServerTestCase):
    apps = ["maasserver.tests"]

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
        self.assertEqual(created, obj.created)

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
        self.assertEqual(created, obj.created)
        self.assertEqual(created, obj.updated)

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

    def test_updated_allows_override(self):
        last_year = timezone.now() - timedelta(days=365)
        # Perform a write database operation.
        created = make_time_in_the_recent_past()
        updated = make_time_in_the_recent_past()
        obj = TimestampedModelTestModel(created=created, updated=updated)
        obj.save(_updated=last_year)
        # The created time should be set to last year, since the override value
        # was less than the creation date.
        self.assertEqual(last_year, obj.created)
        self.assertEqual(last_year, obj.updated)

    def test_created_allows_override(self):
        last_year = timezone.now() - timedelta(days=365)
        # Perform a write database operation.
        created = make_time_in_the_recent_past()
        updated = make_time_in_the_recent_past()
        obj = TimestampedModelTestModel(created=created, updated=updated)
        obj.save(_created=last_year)
        self.assertEqual(last_year, obj.created)
        self.assertEqual(created, obj.updated)

    def test_created_works_with_one_to_one_models(self):
        generic = GenericTestModel()
        generic.save()
        ts_1to1 = TimestampedOneToOneTestModel(generic=generic)
        ts_1to1.save()
        self.assertIsNotNone(ts_1to1.created)
        self.assertIsNotNone(ts_1to1.updated)


class TestUtilities(MAASServerTestCase):
    def test_now_returns_datetime(self):
        self.assertIsInstance(now(), datetime)
