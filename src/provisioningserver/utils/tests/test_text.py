# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for text processing utilities."""

__all__ = []

import string
from textwrap import dedent

import hypothesis
import hypothesis.strategies
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.utils.text import (
    make_bullet_list,
    normalise_to_comma_list,
    normalise_whitespace,
    split_string_list,
)
from testtools.matchers import Equals


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


class TestNormaliseToCommaList(MAASTestCase):
    """Tests for `normalise_to_comma_list`."""

    delimiters = hypothesis.strategies.text(
        string.whitespace + ",", min_size=1, max_size=10)

    @hypothesis.given(delimiters)
    def test__normalises_space_or_comma_list_to_comma_list(self, delimiter):
        words = [factory.make_name("word") for _ in range(5)]
        string = delimiter.join(words)
        self.assertThat(
            normalise_to_comma_list(string),
            Equals(", ".join(words)))

    @hypothesis.given(delimiters)
    def test__normalises_nothing_but_delimiter_to_empty(self, delimiter):
        self.assertThat(
            normalise_to_comma_list(delimiter),
            Equals(""))

    @hypothesis.given(delimiters)
    def test__eliminates_empty_words(self, delimiter):
        word = factory.make_name("word")
        self.assertThat(
            normalise_to_comma_list(delimiter + word + delimiter),
            Equals(word))


class TestSplitStringList(MAASTestCase):
    """Tests for `split_string_list`."""

    delimiters = hypothesis.strategies.text(
        string.whitespace + ",", min_size=1, max_size=10)

    @hypothesis.given(delimiters)
    def test__splits_at_delimiters(self, delimiter):
        words = [factory.make_name("word") for _ in range(5)]
        string = delimiter.join(words)
        self.assertThat(
            list(split_string_list(string)),
            Equals(words))

    @hypothesis.given(delimiters)
    def test__normalises_nothing_but_delimiter_to_empty_list(self, delimiter):
        self.assertThat(
            list(split_string_list(delimiter)),
            Equals([]))

    @hypothesis.given(delimiters)
    def test__eliminates_empty_words(self, delimiter):
        word = factory.make_name("word")
        self.assertThat(
            list(split_string_list(delimiter + word + delimiter)),
            Equals([word]))
