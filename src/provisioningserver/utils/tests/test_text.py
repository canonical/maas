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

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.utils.text import normalise_whitespace


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
