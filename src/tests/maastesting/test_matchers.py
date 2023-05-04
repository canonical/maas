# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test matchers."""


from string import whitespace
from textwrap import dedent
from unittest.mock import (
    call,
    create_autospec,
    Mock,
    NonCallableMock,
    sentinel,
)

from testtools.content import Content
from testtools.matchers import (
    AfterPreprocessing,
    Contains,
    ContainsDict,
    Equals,
    IsInstance,
    MatchesStructure,
    Mismatch,
)
from twisted.internet import defer

from maastesting import matchers
from maastesting.factory import factory
from maastesting.matchers import (
    ContainedBy,
    FileContains,
    GreaterThanOrEqual,
    HasAttribute,
    IsCallable,
    IsCallableMock,
    IsFiredDeferred,
    IsNonEmptyString,
    IsUnfiredDeferred,
    LessThanOrEqual,
    Matches,
    MockAnyCall,
    MockCalledOnce,
    MockCalledOnceWith,
    MockCalledWith,
    MockCallsMatch,
    MockNotCalled,
    TextEquals,
)
from maastesting.testcase import MAASTestCase


class TestMatches(MAASTestCase):
    def test_string_representation(self):
        matcher = AfterPreprocessing(set, Equals({1, 2, "three"}))
        self.assertThat(
            Matches(matcher),
            AfterPreprocessing(str, Equals("Matches " + str(matcher))),
        )

    def test_representation(self):
        matcher = AfterPreprocessing(set, Equals({1, 2, "three"}))
        self.assertThat(
            Matches(matcher),
            AfterPreprocessing(repr, Equals("<Matches " + str(matcher) + ">")),
        )

    def test_equality(self):
        matcher = AfterPreprocessing(set, Equals({1, 2, "three"}))
        self.assertEqual(Matches(matcher), [1, 2, "three"])
        self.assertEqual(Matches(matcher), (1, 2, "three"))
        self.assertEqual(Matches(matcher), dict.fromkeys((1, 2, "three")))
        self.assertNotEqual(Matches(matcher), (1, 2, 3))
        self.assertNotEqual(Matches(matcher), (1, 2, "three", 4))
        self.assertNotEqual(Matches(matcher), dict.fromkeys((2, "three")))


class TestIsCallable(MAASTestCase):
    def test_returns_none_when_matchee_is_callable(self):
        result = IsCallable().match(lambda: None)
        self.assertIsNone(result)

    def test_returns_mismatch_when_matchee_is_callable(self):
        result = IsCallable().match(1234)
        self.assertIsInstance(result, Mismatch)
        self.assertEqual("1234 is not callable", result.describe())

    def test_match_passes_through_to_callable_builtin(self):
        self.patch(matchers, "callable").return_value = True
        result = IsCallable().match(sentinel.function)
        matchers.callable.assert_called_once_with(sentinel.function)
        self.assertIsNone(result)

    def test_mismatch_passes_through_to_callable_builtin(self):
        self.patch(matchers, "callable").return_value = False
        result = IsCallable().match(sentinel.function)
        matchers.callable.assert_called_once_with(sentinel.function)
        self.assertIsInstance(result, Mismatch)
        self.assertEqual(
            "%r is not callable" % sentinel.function, result.describe()
        )


class MockTestMixin:
    # Some matchers return a private MismatchDecorator object, which
    # does not descend from Mismatch, so we check the contract instead.
    is_mismatch = MatchesStructure(
        describe=IsCallable(), get_details=IsCallable()
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
        self.assertMismatch(result, "expected call not found")

    def test_str(self):
        matcher = MockCalledWith(1, a=2)
        self.assertEqual(
            "MockCalledWith(args=(1,), kwargs={'a': 2})", matcher.__str__()
        )


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
        self.assertMismatch(
            result, "Expected 'mock' to be called once. Called 2 times."
        )

    def test_returns_mismatch_when_single_call_does_not_match(self):
        mock = Mock()
        mock(1, 2, a=5)

        matcher = MockCalledOnceWith(9, 2, a=5)
        result = matcher.match(mock)
        self.assertMismatch(result, "expected call not found")

    def test_str(self):
        matcher = MockCalledOnceWith(1, a=2)
        self.assertEqual(
            "MockCalledOnceWith(args=(1,), kwargs={'a': 2})", matcher.__str__()
        )


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
            result, "Expected to be called once. Called 2 times."
        )

    def test_returns_mismatch_when_zero_calls(self):
        mock = Mock()

        matcher = MockCalledOnce()
        result = matcher.match(mock)
        self.assertMismatch(
            result, "Expected to be called once. Called 0 times."
        )

    def test_str(self):
        matcher = MockCalledOnce()
        self.assertEqual("MockCalledOnce", matcher.__str__())


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
            call(1, 2, frob=5, nob=6), call(1, 2, frob=5, nob=6)
        )
        result = matcher.match(mock)
        self.assertIsNone(result)

    def test_returns_mismatch_when_calls_do_not_match(self):
        mock = Mock()
        mock(1, 2, a=5)
        mock(3, 4, a=5)

        matcher = MockCallsMatch(call(1, 2, a=5), call(3, 4, a="bogus"))
        result = matcher.match(mock)
        self.assertMismatch(result, "calls do not match")

    def test_has_useful_string_representation(self):
        matcher = MockCallsMatch(call(1, 2, a=3), call(4, 5, a=6))
        self.assertEqual(
            "MockCallsMatch([call(1, 2, a=3), call(4, 5, a=6)])",
            matcher.__str__(),
        )


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
    def test_returns_none_if_attribute_exists(self):
        attribute = factory.make_string(3, prefix="attr")
        setattr(self, attribute, factory.make_name("value"))
        matcher = HasAttribute(attribute)
        result = matcher.match(self)
        self.assertIsNone(result)

    def test_returns_mismatch_if_attribute_does_not_exist(self):
        attribute = factory.make_string(3, prefix="attr")
        matcher = HasAttribute(attribute)
        result = matcher.match(self)
        self.assertMismatch(
            result, " does not have a %r attribute" % attribute
        )


class TestIsCallableMock(MAASTestCase, MockTestMixin):
    def test_returns_none_when_its_a_callable_mock(self):
        mock = Mock()
        matcher = IsCallableMock()
        result = matcher.match(mock)
        self.assertIsNone(result)

    def test_returns_none_when_its_a_callable_autospec(self):
        mock = create_autospec(lambda: None)
        matcher = IsCallableMock()
        result = matcher.match(mock)
        self.assertIsNone(result)

    def test_returns_mismatch_when_its_a_non_callable_mock(self):
        mock = NonCallableMock()
        matcher = IsCallableMock()
        result = matcher.match(mock)
        self.assertMismatch(result, " is not callable")

    def test_returns_mismatch_when_its_a_non_callable_autospec(self):
        mock = create_autospec(None)
        matcher = IsCallableMock()
        result = matcher.match(mock)
        self.assertMismatch(result, " is not callable")

    def test_returns_mismatch_when_its_a_non_callable_object(self):
        matcher = IsCallableMock()
        result = matcher.match(object())
        self.assertMismatch(result, " is not callable")


class TestIsFiredDeferred(MAASTestCase, MockTestMixin):
    def test_matches_fired_deferred(self):
        d = defer.Deferred()
        d.callback(None)
        self.assertThat(d, IsFiredDeferred())

    def test_does_not_match_unfired_deferred(self):
        d = defer.Deferred()
        self.assertMismatch(IsFiredDeferred().match(d), " has not been called")

    def test_does_not_match_non_deferred(self):
        self.assertMismatch(
            IsFiredDeferred().match(object()), " is not a Deferred"
        )


class TestIsUnfiredDeferred(MAASTestCase, MockTestMixin):
    def test_matches_unfired_deferred(self):
        d = defer.Deferred()
        self.assertThat(d, IsUnfiredDeferred())

    def test_does_not_match_fired_deferred(self):
        d = defer.Deferred()
        d.callback(None)
        self.assertMismatch(
            IsUnfiredDeferred().match(d), " has been called (result=None)"
        )

    def test_does_not_match_non_deferred(self):
        self.assertMismatch(
            IsUnfiredDeferred().match(object()), " is not a Deferred"
        )


class TestGreaterThanOrEqual(MAASTestCase, MockTestMixin):
    def test_matches_greater_than(self):
        self.assertThat(5, GreaterThanOrEqual(4))
        self.assertThat("bbb", GreaterThanOrEqual("aaa"))

    def test_matches_equal_to(self):
        self.assertThat(5, GreaterThanOrEqual(5))
        self.assertThat("bbb", GreaterThanOrEqual("bbb"))

    def test_does_not_match_less_than(self):
        self.assertMismatch(GreaterThanOrEqual(6).match(5), "Differences:")
        self.assertMismatch(
            GreaterThanOrEqual("ccc").match("bbb"), "Differences:"
        )


class TestLessThanOrEqual(MAASTestCase, MockTestMixin):
    def test_matches_less_than(self):
        self.assertThat(5, LessThanOrEqual(6))
        self.assertThat("bbb", LessThanOrEqual("ccc"))

    def test_matches_equal_to(self):
        self.assertThat(5, LessThanOrEqual(5))
        self.assertThat("bbb", LessThanOrEqual("bbb"))

    def test_does_not_match_greater_than(self):
        self.assertMismatch(LessThanOrEqual(4).match(5), "Differences:")
        self.assertMismatch(
            LessThanOrEqual("aaa").match("bbb"), "Differences:"
        )


class TestFileContains(MAASTestCase, MockTestMixin):
    def test_does_not_match_if_file_does_not_exist(self):
        self.assertMismatch(
            FileContains("").match("/does/not/exist"),
            "/does/not/exist does not exist",
        )

    def test_cannot_supply_both_contents_and_matcher(self):
        self.assertRaises(AssertionError, FileContains, contents=1, matcher=2)

    def test_cannot_supply_neither_contents_nor_matcher(self):
        self.assertRaises(AssertionError, FileContains)

    def test_compares_in_binary_mode_when_encoding_not_supplied(self):
        contents = factory.make_bytes()  # bytes
        filename = self.make_file(contents=contents)
        self.assertThat(filename, FileContains(contents=contents))

    def test_compares_in_text_mode_when_encoding_supplied(self):
        contents = factory.make_string()  # text
        filename = self.make_file(contents=contents.encode("ascii"))
        self.assertThat(
            filename, FileContains(contents=contents, encoding="ascii")
        )

    def test_does_not_match_when_comparing_binary_to_text(self):
        contents = factory.make_string().encode("ascii")  # bytes
        filename = self.make_file(contents=contents)
        matcher = FileContains(contents=contents, encoding="ascii")
        self.assertMismatch(
            matcher.match(filename),
            "{!r} != {!r}".format(contents.decode("ascii"), contents),
        )

    def test_does_not_match_when_comparing_text_to_binary(self):
        contents = factory.make_string()  # text
        filename = self.make_file(contents=contents.encode("ascii"))
        matcher = FileContains(contents=contents)
        self.assertMismatch(
            matcher.match(filename),
            "{!r} != {!r}".format(contents.encode("ascii"), contents),
        )

    def test_compares_using_matcher_without_encoding(self):
        contents = factory.make_string()  # text
        filename = self.make_file(contents=contents.encode("ascii"))
        self.assertThat(
            filename,
            FileContains(matcher=Contains(contents[:5].encode("ascii"))),
        )

    def test_compares_using_matcher_with_encoding(self):
        contents = factory.make_string()  # text
        filename = self.make_file(contents=contents.encode("ascii"))
        self.assertThat(
            filename,
            FileContains(matcher=Contains(contents[:5]), encoding="ascii"),
        )

    def test_string_representation_explains_binary_match(self):
        contents_binary = factory.make_bytes()
        self.assertDocTestMatches(
            "File at path exists and its contents (unencoded; raw) "
            "match Equals(%r)" % (contents_binary,),
            FileContains(contents=contents_binary),
        )

    def test_string_representation_explains_text_match(self):
        encoding = factory.make_name("encoding")
        contents_text = factory.make_string()
        self.assertDocTestMatches(
            "File at path exists and its contents (encoded as %s) "
            "match Equals(%r)" % (encoding, contents_text),
            FileContains(contents=contents_text, encoding=encoding),
        )

    def test_string_representation_explains_binary_match_with_matcher(self):
        contents_binary = factory.make_bytes()
        contents_matcher = Contains(contents_binary)
        self.assertDocTestMatches(
            "File at path exists and its contents (unencoded; raw) "
            "match %s" % (contents_matcher,),
            FileContains(matcher=contents_matcher),
        )

    def test_string_representation_explains_text_match_with_matcher(self):
        encoding = factory.make_name("encoding")
        contents_text = factory.make_string()
        contents_matcher = Contains(contents_text)
        self.assertDocTestMatches(
            "File at path exists and its contents (encoded as %s) "
            "match %s" % (encoding, contents_matcher),
            FileContains(matcher=contents_matcher, encoding=encoding),
        )


class TestTextEquals(MAASTestCase, MockTestMixin):
    """Tests for the `TextEquals` matcher."""

    def test_matches_equal_strings(self):
        contents = factory.make_string()
        self.assertThat(contents, TextEquals(contents))

    def test_matches_equal_things(self):
        contents = object()
        self.assertThat(contents, TextEquals(contents))

    def test_describes_mismatch(self):
        self.assertMismatch(
            TextEquals("foo").match("bar"),
            "Observed text does not match expectations; see diff.",
        )

    def test_includes_diff_of_mismatch(self):
        expected = "A line of text that differs at the end."
        observed = "A line of text that differs at THE end."
        mismatch = TextEquals(expected).match(observed)
        details = mismatch.get_details()
        self.assertThat(details, ContainsDict({"diff": IsInstance(Content)}))
        self.assertThat(
            details["diff"].as_text(),
            Equals(
                dedent(
                    """\
        --- expected
        +++ observed
        - A line of text that differs at the end.
        ?                                ^^^
        + A line of text that differs at THE end.
        ?                                ^^^
        """
                )
            ),
        )

    def test_includes_diff_of_mismatch_multiple_lines(self):
        expected = "A line of text that differs\nat the end of the 2nd line."
        observed = "A line of text that differs\nat the end of the 2ND line."
        mismatch = TextEquals(expected).match(observed)
        details = mismatch.get_details()
        self.assertThat(details, ContainsDict({"diff": IsInstance(Content)}))
        self.assertThat(
            details["diff"].as_text(),
            Equals(
                dedent(
                    """\
        --- expected
        +++ observed
          A line of text that differs
        - at the end of the 2nd line.
        ?                    ^^
        + at the end of the 2ND line.
        ?                    ^^
        """
                )
            ),
        )

    def test_includes_diff_of_coerced_arguments(self):
        expected = "A tuple", "that differs", "here."
        observed = "A tuple", "that differs", "HERE."
        mismatch = TextEquals(expected).match(observed)
        details = mismatch.get_details()
        self.assertThat(details, ContainsDict({"diff": IsInstance(Content)}))
        self.assertThat(
            details["diff"].as_text(),
            Equals(
                dedent(
                    """\
        --- expected
        +++ observed
        - ('A tuple', 'that differs', 'here.')
        ?                              ^^^^
        + ('A tuple', 'that differs', 'HERE.')
        ?                              ^^^^
        """
                )
            ),
        )


class TestIsNonEmptyString(MAASTestCase, MockTestMixin):
    """Tests for the `IsNonEmptyString` matcher."""

    def test_matches_non_empty_string(self):
        self.assertThat("foo", IsNonEmptyString)

    def test_does_not_match_empty_string(self):
        self.assertMismatch(IsNonEmptyString.match(""), "'' is empty")

    def test_does_not_match_string_containing_only_whitespace(self):
        self.assertMismatch(
            IsNonEmptyString.match(whitespace), "%r is whitespace" % whitespace
        )

    def test_does_not_match_non_strings(self):
        self.assertMismatch(
            IsNonEmptyString.match(1234), "1234 is not a string"
        )


class TestContainedBy(MAASTestCase, MockTestMixin):
    """Tests for the `ContainedBy` matcher."""

    def test_matches_needle_in_haystack(self):
        self.assertThat("foo", ContainedBy({"foo", "bar"}))

    def test_does_not_match_needle_not_in_haystack(self):
        self.assertMismatch(ContainedBy([]).match("foo"), "'foo' not in []")
