# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for text processing utilities."""


from itertools import repeat
import string

import hypothesis
import hypothesis.strategies
from testtools.matchers import Equals

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.utils.text import (
    make_gecos_field,
    normalise_to_comma_list,
    normalise_whitespace,
    split_string_list,
)


class TestNormaliseWhitespace(MAASTestCase):
    def test_preserves_text_without_whitespace(self):
        word = factory.make_name("word")
        self.assertEqual(word, normalise_whitespace(word))

    def test_eliminates_leading_space(self):
        self.assertEqual("word", normalise_whitespace(" word"))

    def test_eliminates_trailing_space(self):
        self.assertEqual("word", normalise_whitespace("word "))

    def test_replaces_any_whitespace_sequence_with_single_space(self):
        self.assertEqual(
            "one two three", normalise_whitespace("one   two\t\nthree")
        )

    def test_treats_punctuation_as_non_space(self):
        punctuation = ".?;:!"
        self.assertEqual(punctuation, normalise_whitespace(punctuation))


class TestNormaliseToCommaList(MAASTestCase):
    """Tests for `normalise_to_comma_list`."""

    delimiters = hypothesis.strategies.text(
        string.whitespace + ",", min_size=1, max_size=10
    )

    @hypothesis.given(delimiters)
    def test_normalises_space_or_comma_list_to_comma_list(self, delimiter):
        words = [factory.make_name("word") for _ in range(5)]
        string = delimiter.join(words)
        self.assertThat(
            normalise_to_comma_list(string), Equals(", ".join(words))
        )

    @hypothesis.given(delimiters)
    def test_normalises_nothing_but_delimiter_to_empty(self, delimiter):
        self.assertThat(normalise_to_comma_list(delimiter), Equals(""))

    @hypothesis.given(delimiters)
    def test_eliminates_empty_words(self, delimiter):
        word = factory.make_name("word")
        self.assertThat(
            normalise_to_comma_list(delimiter + word + delimiter), Equals(word)
        )


class TestNormalizeToCommaListScenarios(MAASTestCase):
    """Tests for `normalize_to_comma_list`."""

    scenarios = (
        ("empty string", {"test_input": "", "unquoted": "", "quoted": ""}),
        (
            "one token",
            {"test_input": "foo", "unquoted": "foo", "quoted": '"foo"'},
        ),
        (
            "two tokens with space",
            {
                "test_input": "foo bar",
                "unquoted": "foo, bar",
                "quoted": '"foo", "bar"',
            },
        ),
        (
            "two tokens with comma",
            {
                "test_input": "foo, bar",
                "unquoted": "foo, bar",
                "quoted": '"foo", "bar"',
            },
        ),
        (
            "extra spaces",
            {
                "test_input": "  foo   bar  ",
                "unquoted": "foo, bar",
                "quoted": '"foo", "bar"',
            },
        ),
        (
            "extra spaces with comma",
            {
                "test_input": "  foo ,  bar  ",
                "unquoted": "foo, bar",
                "quoted": '"foo", "bar"',
            },
        ),
    )

    def test_scenarios(self):
        unquoted = normalise_to_comma_list(self.test_input)
        self.expectThat(unquoted, Equals(self.unquoted))
        quoted = normalise_to_comma_list(self.test_input, quoted=True)
        self.expectThat(quoted, Equals(self.quoted))


class TestSplitStringList(MAASTestCase):
    """Tests for `split_string_list`."""

    delimiters = hypothesis.strategies.text(
        string.whitespace + ",", min_size=1, max_size=10
    )

    @hypothesis.given(delimiters)
    def test_splits_at_delimiters(self, delimiter):
        words = [factory.make_name("word") for _ in range(5)]
        string = delimiter.join(words)
        self.assertThat(list(split_string_list(string)), Equals(words))

    @hypothesis.given(delimiters)
    def test_normalises_nothing_but_delimiter_to_empty_list(self, delimiter):
        self.assertThat(list(split_string_list(delimiter)), Equals([]))

    @hypothesis.given(delimiters)
    def test_eliminates_empty_words(self, delimiter):
        word = factory.make_name("word")
        self.assertThat(
            list(split_string_list(delimiter + word + delimiter)),
            Equals([word]),
        )


class TestMakeGecosField(MAASTestCase):
    """Tests for `make_gecos_field`."""

    def test_returns_basic_gecos_field_without_input(self):
        self.assertThat(make_gecos_field(), Equals(",,,,"))

    def test_includes_full_name(self):
        self.assertThat(
            make_gecos_field(fullname="Bernard Bierkeller"),
            Equals("Bernard Bierkeller,,,,"),
        )

    def test_includes_room_number(self):
        room = factory.make_name("room")
        self.assertThat(make_gecos_field(room=room), Equals(",%s,,," % room))

    def test_includes_work_telephone_number(self):
        worktel = factory.make_name("worktel")
        self.assertThat(
            make_gecos_field(worktel=worktel), Equals(",,%s,," % worktel)
        )

    def test_includes_home_telephone_number(self):
        hometel = factory.make_name("hometel")
        self.assertThat(
            make_gecos_field(hometel=hometel), Equals(",,,%s," % hometel)
        )

    def test_includes_other_information(self):
        other = factory.make_name("other")
        self.assertThat(
            make_gecos_field(other=other), Equals(",,,,%s" % other)
        )

    def test_cleans_all_fields(self):
        broken = "colon : comma , non-ascii £ white-space \n\t  "
        fixed = "colon _ comma _ non-ascii ? white-space"
        self.assertThat(
            make_gecos_field(broken, broken, broken, broken, broken),
            Equals(",".join(repeat(fixed, 5))),
        )
