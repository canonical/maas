# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test matchers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maastesting import matchers
from maastesting.factory import factory
from maastesting.matchers import (
    ContainsAll,
    IsCallable,
    )
from maastesting.testcase import MAASTestCase
from mock import sentinel
from testtools.matchers import (
    Mismatch,
    MismatchError,
    )


class TestContainsAll(MAASTestCase):

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


class TestIsCallable(MAASTestCase):

    def test_returns_none_when_matchee_is_callable(self):
        result = IsCallable().match(lambda: None)
        self.assertIs(None, result)

    def test_returns_mismatch_when_matchee_is_callable(self):
        result = IsCallable().match(1234)
        self.assertIsInstance(result, Mismatch)
        self.assertEqual(
            "1234 is not callable",
            result.describe())

    def test_match_passes_through_to_callable_builtin(self):
        self.patch(matchers, "callable").return_value = True
        result = IsCallable().match(sentinel.function)
        matchers.callable.assert_called_once_with(sentinel.function)
        self.assertIs(None, result)

    def test_mismatch_passes_through_to_callable_builtin(self):
        self.patch(matchers, "callable").return_value = False
        result = IsCallable().match(sentinel.function)
        matchers.callable.assert_called_once_with(sentinel.function)
        self.assertIsInstance(result, Mismatch)
        self.assertEqual(
            "%r is not callable" % sentinel.function,
            result.describe())
