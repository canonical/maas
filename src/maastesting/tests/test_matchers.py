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
    MockCallsMatch,
    MockNotCalled,
    )
from maastesting.testcase import MAASTestCase
from mock import (
    call,
    Mock,
    sentinel,
    )
from testtools.matchers import (
    MatchesStructure,
    Mismatch,
    )


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

    # Some matchers return a private MismatchDecorator object, which
    # does not descend from Mismatch, so we check the contract instead.
    is_mismatch = MatchesStructure(
        describe=IsCallable(),
        get_details=IsCallable(),
    )

    def assertMismatch(self, result, message):
        self.assertThat(result, self.is_mismatch)
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


class TestMockCallsMatch(MAASTestCase, MockTestMixin):

    def test_returns_none_when_matches(self):
        mock = Mock()
        mock(1, 2, frob=5, nob=6)

        matcher = MockCallsMatch(call(1, 2, frob=5, nob=6))
        result = matcher.match(mock)
        self.assertIsNone(result)

    def test_returns_none_when_multiple_calls(self):
        mock = Mock()
        mock(1, 2, frob=5, nob=6)
        mock(1, 2, frob=5, nob=6)

        matcher = MockCallsMatch(
            call(1, 2, frob=5, nob=6),
            call(1, 2, frob=5, nob=6))
        result = matcher.match(mock)
        self.assertIsNone(result)

    def test_returns_mismatch_when_calls_do_not_match(self):
        mock = Mock()
        mock(1, 2, a=5)
        mock(3, 4, a=5)

        matcher = MockCallsMatch(
            call(1, 2, a=5), call(3, 4, a="bogus"))
        result = matcher.match(mock)
        self.assertMismatch(result, "calls do not match")

    def test_has_useful_string_representation(self):
        matcher = MockCallsMatch(
            call(1, 2, a=3), call(4, 5, a=6))
        self.assertEqual(
            "MockCallsMatch([call(1, 2, a=3), call(4, 5, a=6)])",
            matcher.__str__())


class TestMockNotCalled(MAASTestCase, MockTestMixin):

    def test_returns_none_mock_has_not_been_called(self):
        mock = Mock()
        matcher = MockNotCalled()
        result = matcher.match(mock)
        self.assertIsNone(result)

    def test_returns_mismatch_when_mock_has_been_called(self):
        mock = Mock()
        mock(1, 2, a=5)

        matcher = MockNotCalled()
        result = matcher.match(mock)
        self.assertMismatch(result, "mock has been called")

    def test_has_useful_string_representation(self):
        matcher = MockNotCalled()
        self.assertEqual("MockNotCalled", matcher.__str__())
