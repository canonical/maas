# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for text processing utilities."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from textwrap import dedent

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.utils.text import (
    make_bullet_list,
    normalise_whitespace,
    )


class TestNormaliseWhitespace(MAASTestCase):

    def test__preserves_text_without_whitespace(self):
        word = factory.make_name('word')
        self.assertEqual(word, normalise_whitespace(word))

    def test__eliminates_leading_space(self):
        self.assertEqual('word', normalise_whitespace(' word'))

    def test__eliminates_trailing_space(self):
        self.assertEqual('word', normalise_whitespace('word '))

    def test__replaces_any_whitespace_sequence_with_single_space(self):
        self.assertEqual(
            'one two three',
            normalise_whitespace('one   two\t\nthree'))

    def test__treats_punctuation_as_non_space(self):
        punctuation = '.?;:!'
        self.assertEqual(punctuation, normalise_whitespace(punctuation))


class TestMakeBulletList(MAASTestCase):

    def test__returns_empty_string_when_there_are_no_messages(self):
        self.assertEqual("", make_bullet_list([]))

    def test__wraps_at_72_columns(self):
        lines = make_bullet_list([" -" * 50]).splitlines()
        self.assertEqual(72, max(len(line) for line in lines))

    def test__fills_and_formats(self):
        messages = [
            """Lorem ipsum dolor sit amet, consectetur adipiscing elit.
            Maecenas a lorem pellentesque, dapibus lorem ut, blandit ex.""",
            """Nulla tristique quam sed suscipit cursus""",
            """Integer euismod viverra ipsum, id placerat ante interdum vitae.
            Mauris fermentum ut nisi vitae tincidunt. Maecenas posuere lacus
            vel est dignissim vehicula. Vestibulum tristique, massa non
            facilisis mattis, nisi lacus lacinia neque, nec convallis risus
            turpis id metus. Aenean semper sapien sed volutpat volutpat.""",
        ]
        bullet_list = make_bullet_list(messages)
        bullet_list_expected = dedent("""\
        * Lorem ipsum dolor sit amet, consectetur adipiscing elit.
          Maecenas a lorem pellentesque, dapibus lorem ut, blandit ex.
        * Nulla tristique quam sed suscipit cursus
        * Integer euismod viverra ipsum, id placerat ante interdum vitae.
          Mauris fermentum ut nisi vitae tincidunt. Maecenas posuere lacus
          vel est dignissim vehicula. Vestibulum tristique, massa non
          facilisis mattis, nisi lacus lacinia neque, nec convallis risus
          turpis id metus. Aenean semper sapien sed volutpat volutpat.""")
        self.assertEqual(bullet_list_expected, bullet_list)
