# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for forms helpers."""

from maasserver.testing.factory import factory
from maasserver.utils.forms import compose_invalid_choice_text
from maastesting.testcase import MAASTestCase


class TestComposeInvalidChoiceText(MAASTestCase):
    def test_map_enum_includes_all_enum_values(self):
        choices = [
            (factory.make_name("key"), factory.make_name("value"))
            for _ in range(2)
        ]
        msg = compose_invalid_choice_text(factory.make_name(), choices)
        for key, _ in choices:
            self.assertIn(f"'{key}'", msg)
