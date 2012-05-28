# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for testing helpers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maastesting.testcase import TestCase
from maastesting.utils import extract_word_list


class TestFunctions(TestCase):

    def test_extract_word_list(self):
        expected = {
            "one 2": ["one", "2"],
            ", one ; 2": ["one", "2"],
            "one,2": ["one", "2"],
            "one;2": ["one", "2"],
            "\none\t 2;": ["one", "2"],
            "\none-two\t 3;": ["one-two", "3"],
            }
        observed = {
            string: extract_word_list(string)
            for string in expected
            }
        self.assertEqual(expected, observed)
