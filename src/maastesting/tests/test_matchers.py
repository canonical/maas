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
from maastesting.matchers import (
    IsCallable,
    MockAnyCall,
    MockCalledOnceWith,
    MockCalledWith,
    )
from maastesting.testcase import MAASTestCase
from mock import (
    Mock,
    sentinel,
    )
from testtools.matchers import Mismatch


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


class MockTestMixin:

    def assertMismatch(self, result, message):
        self.assertIsInstance(result, Mismatch)
        self.assertIn(message, result.describe())


class TestMockCalledWith(MAASTestCase, MockTestMixin):

    def test_returns_none_when_matches(self):
        mock = Mock()
        mock(1, 2, frob=5, nob=6)

        matcher = MockCalledWith(1, 2, frob=5, nob=6)
        result = matcher.match(mock)
        self.assertIsNone(result)

    def test_returns_mismatch_when_does_not_match(self):
        mock = Mock()
        mock(1, 2, a=5)

        matcher = MockCalledWith(9, 2, a=5)
        result = matcher.match(mock)
        self.assertMismatch(result, "Expected call:")

    def test_str(self):
        matcher = MockCalledWith(1, a=2)
        self.assertEqual(
            "MockCalledWith(args=(1,), kwargs={'a': 2})", matcher.__str__())


class TestMockCalledOnceWith(MAASTestCase, MockTestMixin):

    def test_returns_none_when_matches(self):
        mock = Mock()
        mock(1, 2, frob=5, nob=6)

        matcher = MockCalledOnceWith(1, 2, frob=5, nob=6)
        result = matcher.match(mock)
        self.assertIsNone(result)

    def test_returns_mismatch_when_multiple_calls(self):
        mock = Mock()
        mock(1, 2, frob=5, nob=6)
        mock(1, 2, frob=5, nob=6)

        matcher = MockCalledOnceWith(1, 2, frob=5, nob=6)
        result = matcher.match(mock)
        self.assertMismatch(result, "Expected to be called once")

    def test_returns_mismatch_when_single_call_does_not_match(self):
        mock = Mock()
        mock(1, 2, a=5)

        matcher = MockCalledOnceWith(9, 2, a=5)
        result = matcher.match(mock)
        self.assertMismatch(result, "Expected call:")

    def test_str(self):
        matcher = MockCalledOnceWith(1, a=2)
        self.assertEqual(
            "MockCalledOnceWith(args=(1,), kwargs={'a': 2})",
            matcher.__str__())


class TestMockAnyCall(MAASTestCase, MockTestMixin):

    def test_returns_none_when_matches(self):
        mock = Mock()
        mock(1, 2, frob=5, nob=6)

        matcher = MockAnyCall(1, 2, frob=5, nob=6)
        result = matcher.match(mock)
        self.assertIsNone(result)

    def test_returns_none_when_multiple_calls(self):
        mock = Mock()
        mock(1, 2, frob=5, nob=6)
        mock(1, 2, frob=5, nob=6)

        matcher = MockAnyCall(1, 2, frob=5, nob=6)
        result = matcher.match(mock)
        self.assertIsNone(result)

    def test_returns_mismatch_when_call_does_not_match(self):
        mock = Mock()
        mock(1, 2, a=5)

        matcher = MockAnyCall(1, 2, frob=5, nob=6)
        result = matcher.match(mock)
        self.assertMismatch(result, "call not found")
