# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""testtools custom matchers"""

from difflib import ndiff
import doctest
from functools import partial

from testtools import matchers
from testtools.content import Content, UTF8_TEXT
from testtools.matchers import (
    AfterPreprocessing,
    Annotate,
    Equals,
    GreaterThan,
    HasLength,
    IsInstance,
    LessThan,
    Matcher,
    MatchesAll,
    MatchesAny,
    MatchesPredicate,
    MatchesStructure,
    Mismatch,
    PathExists,
)
from twisted.internet import defer


class Matches:
    """Convert any matcher into an equality tester.

    This is useful when testing mock assertions. For example::

        process_batch = self.patch(a_module, "process_batch")
        process_all_in_batches([1, 2, 3, 4, 5, 6, 7, 8, 9])

        batch1 = [1, 3, 5, 7, 9]
        batch2 = [2, 4, 6, 8]

        batch1_in_any_order = AfterPreprocessing(sorted, Equals(batch1))
        batch2_in_any_order = AfterPreprocessing(sorted, Equals(batch2))

        self.assertThat(
            process_batch, MockCallsMatch(
                call(batch1_in_any_order),
                call(batch2_in_any_order),
            ))

    It does this by implementing ``__eq__``, so can be useful in other
    contexts::

        >>> batch2 == batch2_in_any_order
        True
        >>> batch1 == batch2_in_any_order
        False

    """

    def __init__(self, matcher):
        super().__init__()
        self.matcher = matcher

    def __eq__(self, other):
        return self.matcher.match(other) is None

    def __str__(self):
        return f"Matches {self.matcher}"

    def __repr__(self):
        return f"<Matches {self.matcher}>"


class IsCallable(Matcher):
    """Matches if the matchee is callable."""

    def match(self, something):
        if not callable(something):
            return Mismatch(f"{something!r} is not callable")

    def __str__(self):
        return self.__class__.__name__


class Provides(MatchesPredicate):
    """Match if the given interface is provided."""

    def __init__(self, iface):
        super().__init__(
            iface.providedBy, "%%r does not provide %s" % iface.getName()
        )


class HasAttribute(Matcher):
    """Match if the given attribute is available."""

    def __init__(self, attribute):
        super().__init__()
        self.attribute = attribute

    def match(self, something):
        try:
            getattr(something, self.attribute)
        except AttributeError:
            return Mismatch(
                f"{something!r} does not have a {self.attribute!r} attribute"
            )

    def __str__(self):
        return f"{self.__class__.__name__}({self.attribute!r})"


class IsCallableMock(Matcher):
    """Match if the subject looks like a mock that's callable.

    `mock.create_autospec` can return objects like functions and modules that
    are also callable mocks, but we can't use a simple ``isinstance`` test to
    ascertain that. Here we assume the presence of ``return_value`` and
    ``side_effect`` attributes means that we've found a callable mock. These
    attributes are defined in `mock.CallableMixin`.
    """

    def match(self, something):
        return MatchesAll(
            HasAttribute("return_value"),
            HasAttribute("side_effect"),
            IsCallable(),
        ).match(something)

    def __str__(self):
        return self.__class__.__name__


def get_mock_calls(mock):
    """Return a list of all calls made to the given `mock`.

    :type mock: :class:`Mock`
    """
    return mock.call_args_list


class MockCalledWith(Matcher):
    """Matches if the matchee Mock was called with the provided args.

    Use of Mock.assert_called_with is discouraged as it passes if you typo
    the function name.
    """

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __str__(self):
        return "{}(args={!r}, kwargs={!r})".format(
            self.__class__.__name__,
            self.args,
            self.kwargs,
        )

    def match(self, mock):
        try:
            mock.assert_called_with(*self.args, **self.kwargs)
        except AssertionError as e:
            return Mismatch(*e.args)

        return None


class MockCalledOnceWith(MockCalledWith):
    """Matches if the matchee `Mock` was called once, with the provided args.

    To pass the match, the mock must have been called exactly once, and with
    the given arguments.  Use `mock.ANY` for any parameters whose values don't
    matter for the match.

    Use this instead of `Mock.assert_called_once_with`, which just always
    passes blindly if you mis-spell the name.
    """

    def match(self, mock):
        try:
            mock.assert_called_once_with(*self.args, **self.kwargs)
        except AssertionError as e:
            return Mismatch(*e.args)

        return None


class MockCalledOnce(Matcher):
    """Matches if the matchee `Mock` was called once, with any arguments.

    The mock library does not have an equivalent.
    """

    def __str__(self):
        return self.__class__.__name__

    def match(self, mock):
        mismatch = IsCallableMock().match(mock)
        if mismatch is not None:
            return mismatch
        elif mock.call_count == 1:
            return None
        else:
            return Mismatch(
                "Expected to be called once. Called %d times."
                % mock.call_count
            )


class MockAnyCall(MockCalledWith):
    """Matches if the matchee Mock was called at any time with the provided
    args.

    Use of Mock.assert_any_call is discouraged as it passes if you typo
    the function name.
    """

    def match(self, mock):
        try:
            mock.assert_any_call(*self.args, **self.kwargs)
        except AssertionError as e:
            return Mismatch(*e.args)

        return None


class MockCallsMatch(Matcher):
    """Matches if the matchee Mock was called with exactly the given
    sequence of calls.

    :param calls: A sequence of :class:`mock.call`s that the matchee is
        expected to have been called with.

    The mock library does not have an equivalent.
    """

    def __init__(self, *calls):
        super(Matcher, self).__init__()
        self.calls = list(calls)

    def __str__(self):
        return f"{self.__class__.__name__}({self.calls!r})"

    def match(self, mock):
        matcher = MatchesAll(
            IsCallableMock(),
            Annotate(
                "calls do not match",
                AfterPreprocessing(get_mock_calls, Equals(self.calls)),
            ),
            first_only=True,
        )
        return matcher.match(mock)


class MockNotCalled(Matcher):
    """Matches if the matchee Mock was not called.

    The mock library does not have an equivalent.
    """

    def __str__(self):
        return self.__class__.__name__

    def match(self, mock):
        matcher = MatchesAll(
            IsCallableMock(),
            Annotate(
                "mock has been called",
                AfterPreprocessing(get_mock_calls, HasLength(0)),
            ),
            first_only=True,
        )
        return matcher.match(mock)


class IsFiredDeferred(Matcher):
    """Matches if the subject is a fired `Deferred`."""

    def __str__(self):
        return self.__class__.__name__

    def match(self, thing):
        if not isinstance(thing, defer.Deferred):
            return Mismatch(f"{thing!r} is not a Deferred")
        if not thing.called:
            return Mismatch(f"{thing!r} has not been called")
        return None


class IsUnfiredDeferred(Matcher):
    """Matches if the subject is an unfired `Deferred`."""

    def __str__(self):
        return self.__class__.__name__

    def match(self, thing):
        if not isinstance(thing, defer.Deferred):
            return Mismatch(f"{thing!r} is not a Deferred")
        if thing.called:
            return Mismatch(
                f"{thing!r} has been called (result={thing.result!r})"
            )
        return None


class MatchesPartialCall(Matcher):
    def __init__(self, func, *args, **keywords):
        super().__init__()
        if len(keywords) > 0:
            self.expected = partial(func, *args, **keywords)
        else:
            self.expected = partial(func, *args)

    def match(self, observed):
        matcher = MatchesAll(
            IsInstance(partial),
            MatchesStructure.fromExample(
                self.expected, "func", "args", "keywords"
            ),
            first_only=True,
        )
        return matcher.match(observed)


def GreaterThanOrEqual(value):
    return MatchesAny(GreaterThan(value), Equals(value))


def LessThanOrEqual(value):
    return MatchesAny(LessThan(value), Equals(value))


class DocTestMatches(matchers.DocTestMatches):
    """See if a string matches a doctest example.

    This differs from testtools' matcher in that it, by default, normalises
    white-space and allows the use of ellipsis. See `doctest` for details.
    """

    DEFAULT_FLAGS = doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE

    def __init__(self, example, flags=DEFAULT_FLAGS):
        super().__init__(example, flags)


class FileContains(Matcher):
    """Matches if the given file has the specified contents.

    This differs from testtools' matcher in that it is strict about binary and
    text; a comparison of text must be done with an encoding.
    """

    def __init__(self, contents=None, matcher=None, encoding=None):
        """Construct a ``FileContains`` matcher.

        Can be used in a basic mode where the file contents are compared for
        equality against the expected file contents (by passing ``contents``).
        Can also be used in a more advanced way where the file contents are
        matched against an arbitrary matcher (by passing ``matcher`` instead).

        :param contents: If specified, match the contents of the file with
            these contents.
        :param matcher: If specified, match the contents of the file against
            this matcher.
        :param encoding: If specified, the file is read in text mode with the
            given encoding; ``contents`` should be a Unicode string, or
            ``matcher`` should expect to compare against one. If ``encoding``
            is not specified or is ``None``, the comparison is done byte-wise;
            ``contents`` should be a byte string, or ``matcher`` should expect
            to compare against one.
        """
        if contents is None and matcher is None:
            raise AssertionError(
                "Must provide one of `contents` or `matcher`."
            )
        if contents is not None and matcher is not None:
            raise AssertionError(
                "Must provide either `contents` or `matcher`, not both."
            )
        if matcher is None:
            self.matcher = Equals(contents)
        else:
            self.matcher = matcher
        self.encoding = encoding

    def match(self, path):
        mismatch = PathExists().match(path)
        if mismatch is not None:
            return mismatch
        if self.encoding is None:
            # Binary match.
            with open(path, "rb") as fd:
                actual_contents = fd.read()
        else:
            # Text/Unicode match.
            with open(path, encoding=self.encoding) as fd:
                actual_contents = fd.read()
        return self.matcher.match(actual_contents)

    def __str__(self):
        if self.encoding is None:
            return (
                "File at path exists and its contents (unencoded; raw) "
                "match %s" % (self.matcher,)
            )
        else:
            return (
                "File at path exists and its contents (encoded as %s) "
                "match %s" % (self.encoding, self.matcher)
            )


class TextEquals(Matcher):
    """Compares two blocks of text for equality.

    This differs from `Equals` in that is calculates an `ndiff` between the
    two which will be included in the test results, making this especially
    appropriate for longer pieces of text.
    """

    def __init__(self, expected):
        super().__init__()
        self.expected = expected

    def match(self, observed):
        if observed != self.expected:
            diff = self._diff(self.expected, observed)
            return Mismatch(
                "Observed text does not match expectations; see diff.",
                {"diff": Content(UTF8_TEXT, lambda: map(str.encode, diff))},
            )

    @staticmethod
    def _diff(expected, observed):
        # ndiff works better when lines consistently end with newlines.
        a = str(expected).splitlines(keepends=False)
        a = list(line + "\n" for line in a)
        b = str(observed).splitlines(keepends=False)
        b = list(line + "\n" for line in b)

        yield "--- expected\n"
        yield "+++ observed\n"
        yield from ndiff(a, b)


# The matchee is a non-empty string. In addition a string containing only
# whitespace will not match.
IsNonEmptyString = MatchesAll(
    MatchesPredicate(
        (lambda observed: isinstance(observed, str)), "%r is not a string"
    ),
    MatchesPredicate((lambda observed: len(observed) != 0), "%r is empty"),
    MatchesPredicate(
        (lambda observed: not observed.isspace()), "%r is whitespace"
    ),
    first_only=True,
)


class ContainedBy(Matcher):
    """Test if the matchee is in the given container."""

    def __init__(self, haystack):
        super().__init__()
        self.haystack = haystack

    def __str__(self):
        return f"{self.__class__.__name__}({self.haystack!r})"

    def match(self, needle):
        if needle not in self.haystack:
            return Mismatch(f"{needle!r} not in {self.haystack!r}")
