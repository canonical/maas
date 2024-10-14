# Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.timestampedmodel`"""


from django.utils import timezone

from maasserver.websockets.base import DATETIME_FORMAT
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)
from maastesting.testcase import MAASTestCase


class TestTimeStampedModelHandler(MAASTestCase):
    def test_has_abstract_set_to_true(self):
        handler = TimestampedModelHandler(None, {}, None)
        self.assertTrue(handler._meta.abstract)

    def test_adds_created_and_updated_to_non_changeable(self):
        handler = TimestampedModelHandler(None, {}, None)
        self.assertEqual(["created", "updated"], handler._meta.non_changeable)

    def test_doesnt_overwrite_other_non_changeable_fields(self):
        class TestHandler(TimestampedModelHandler):
            class Meta:
                non_changeable = ["other", "extra"]

        handler = TestHandler(None, {}, None)
        self.assertEqual(
            ["other", "extra", "created", "updated"],
            handler._meta.non_changeable,
        )

    def test_dehydrate_created_converts_datetime_to_string(self):
        now = timezone.now()
        handler = TimestampedModelHandler(None, {}, None)
        self.assertEqual(
            now.strftime(DATETIME_FORMAT),
            handler.dehydrate_created(now),
        )

    def test_dehydrate_updated_converts_datetime_to_string(self):
        now = timezone.now()
        handler = TimestampedModelHandler(None, {}, None)
        self.assertEqual(
            now.strftime(DATETIME_FORMAT),
            handler.dehydrate_updated(now),
        )
