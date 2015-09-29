# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
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
    GreaterThanOrEqual,
    HasAttribute,
    IsCallable,
    IsCallableMock,
    IsFiredDeferred,
    IsUnfiredDeferred,
    LessThanOrEqual,
    MockAnyCall,
    MockCalledOnce,
    MockCalledOnceWith,
    MockCalledWith,
    MockCallsMatch,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase
from mock import (
    call,
    create_autospec,
    Mock,
    NonCallableMock,
    sentinel,
)
from testtools.matchers import (
    MatchesStructure,
    Mismatch,
)
from twisted.internet import defer


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


class TestMockCalledOnce(MAASTestCase, MockTestMixin):

    def test_returns_none_when_matches(self):
        mock = Mock()
        mock(1, 2, frob=5, nob=6)

        matcher = MockCalledOnce()
        result = matcher.match(mock)
        self.assertIsNone(result)

    def test_returns_mismatch_when_multiple_calls(self):
        mock = Mock()
        mock(1, 2, frob=5, nob=6)
        mock(1, 2, frob=5, nob=6)

        matcher = MockCalledOnce()
        result = matcher.match(mock)
        self.assertMismatch(
            result, "Expected to be called once. Called 2 times.")

    def test_returns_mismatch_when_zero_calls(self):
        mock = Mock()

        matcher = MockCalledOnce()
        result = matcher.match(mock)
        self.assertMismatch(
            result, "Expected to be called once. Called 0 times.")

    def test_str(self):
        matcher = MockCalledOnce()
        self.assertEqual(
            "MockCalledOnce",
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


class TestHasAttribute(MAASTestCase, MockTestMixin):

    def test__returns_none_if_attribute_exists(self):
        attribute = factory.make_string(3, prefix="attr")
        setattr(self, attribute, factory.make_name("value"))
        matcher = HasAttribute(attribute)
        result = matcher.match(self)
        self.assertIsNone(result)

    def test__returns_mismatch_if_attribute_does_not_exist(self):
        attribute = factory.make_string(3, prefix="attr")
        matcher = HasAttribute(attribute)
        result = matcher.match(self)
        self.assertMismatch(
            result, " does not have a %r attribute" % attribute)


class TestIsCallableMock(MAASTestCase, MockTestMixin):

    def test__returns_none_when_its_a_callable_mock(self):
        mock = Mock()
        matcher = IsCallableMock()
        result = matcher.match(mock)
        self.assertIsNone(result)

    def test__returns_none_when_its_a_callable_autospec(self):
        mock = create_autospec(lambda: None)
        matcher = IsCallableMock()
        result = matcher.match(mock)
        self.assertIsNone(result)

    def test__returns_mismatch_when_its_a_non_callable_mock(self):
        mock = NonCallableMock()
        matcher = IsCallableMock()
        result = matcher.match(mock)
        self.assertMismatch(
            result, " is not callable")

    def test__returns_mismatch_when_its_a_non_callable_autospec(self):
        mock = create_autospec(None)
        matcher = IsCallableMock()
        result = matcher.match(mock)
        self.assertMismatch(
            result, " is not callable")

    def test__returns_mismatch_when_its_a_non_callable_object(self):
        matcher = IsCallableMock()
        result = matcher.match(object())
        self.assertMismatch(
            result, " is not callable")


class TestIsFiredDeferred(MAASTestCase, MockTestMixin):

    def test__matches_fired_deferred(self):
        d = defer.Deferred()
        d.callback(None)
        self.assertThat(d, IsFiredDeferred())

    def test__does_not_match_unfired_deferred(self):
        d = defer.Deferred()
        self.assertMismatch(
            IsFiredDeferred().match(d),
            " has not been called")

    def test__does_not_match_non_deferred(self):
        self.assertMismatch(
            IsFiredDeferred().match(object()),
            " is not a Deferred")


class TestIsUnfiredDeferred(MAASTestCase, MockTestMixin):

    def test__matches_unfired_deferred(self):
        d = defer.Deferred()
        self.assertThat(d, IsUnfiredDeferred())

    def test__does_not_match_fired_deferred(self):
        d = defer.Deferred()
        d.callback(None)
        self.assertMismatch(
            IsUnfiredDeferred().match(d),
            " has been called (result=None)")

    def test__does_not_match_non_deferred(self):
        self.assertMismatch(
            IsUnfiredDeferred().match(object()),
            " is not a Deferred")


class TestGreaterThanOrEqual(MAASTestCase, MockTestMixin):

    def test__matches_greater_than(self):
        self.assertThat(5, GreaterThanOrEqual(4))
        self.assertThat("bbb", GreaterThanOrEqual("aaa"))

    def test__matches_equal_to(self):
        self.assertThat(5, GreaterThanOrEqual(5))
        self.assertThat("bbb", GreaterThanOrEqual("bbb"))

    def test__does_not_match_less_than(self):
        self.assertMismatch(
            GreaterThanOrEqual(6).match(5), "Differences:")
        self.assertMismatch(
            GreaterThanOrEqual("ccc").match("bbb"), "Differences:")


class TestLessThanOrEqual(MAASTestCase, MockTestMixin):

    def test__matches_less_than(self):
        self.assertThat(5, LessThanOrEqual(6))
        self.assertThat("bbb", LessThanOrEqual("ccc"))

    def test__matches_equal_to(self):
        self.assertThat(5, LessThanOrEqual(5))
        self.assertThat("bbb", LessThanOrEqual("bbb"))

    def test__does_not_match_greater_than(self):
        self.assertMismatch(
            LessThanOrEqual(4).match(5), "Differences:")
        self.assertMismatch(
            LessThanOrEqual("aaa").match("bbb"), "Differences:")
