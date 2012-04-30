# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test matchers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maastesting.factory import factory
from maastesting.matchers import ContainsAll
from maastesting.testcase import TestCase
from testtools.matchers import MismatchError


class TestContainsAll(TestCase):

    def test_ContainsAll_passes_if_all_elements_are_present(self):
        items = [factory.getRandomString() for i in range(3)]
        self.assertThat(items, ContainsAll([items[0], items[2]]))

    def test_ContainsAll_raises_if_one_element_is_missing(self):
        items = [factory.getRandomString() for i in range(3)]
        self.assertRaises(
            MismatchError,
            self.assertThat,
            items,
            ContainsAll([items[0], factory.getRandomString()]))
