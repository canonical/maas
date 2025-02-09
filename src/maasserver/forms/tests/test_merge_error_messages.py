# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `merge_error_messages`."""

from maasserver.forms import MAX_MESSAGES, merge_error_messages
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestMergeErrorMessages(MAASServerTestCase):
    def test_merge_error_messages_returns_summary_message(self):
        summary = factory.make_name("summary")
        errors = [factory.make_name("error") for _ in range(2)]
        result = merge_error_messages(summary, errors, 5)
        self.assertEqual(
            "{} ({})".format(summary, " \u2014 ".join(errors)), result
        )

    def test_merge_error_messages_includes_limited_number_of_msgs(self):
        summary = factory.make_name("summary")
        errors = [factory.make_name("error") for _ in range(MAX_MESSAGES + 2)]
        result = merge_error_messages(summary, errors)
        self.assertEqual(
            "%s (%s and 2 more errors)"
            % (summary, " \u2014 ".join(errors[:MAX_MESSAGES])),
            result,
        )

    def test_merge_error_messages_with_one_more_error(self):
        summary = factory.make_name("summary")
        errors = [factory.make_name("error") for _ in range(MAX_MESSAGES + 1)]
        result = merge_error_messages(summary, errors)
        self.assertEqual(
            "%s (%s and 1 more error)"
            % (summary, " \u2014 ".join(errors[:MAX_MESSAGES])),
            result,
        )
