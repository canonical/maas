# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""testtools custom matchers"""

import doctest

from testtools import matchers
from testtools.matchers import (
    AfterPreprocessing,
    Annotate,
    Equals,
    HasLength,
    Matcher,
    MatchesAll,
    MatchesPredicate,
    Mismatch,
)


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


class DocTestMatches(matchers.DocTestMatches):
    """See if a string matches a doctest example.

    This differs from testtools' matcher in that it, by default, normalises
    white-space and allows the use of ellipsis. See `doctest` for details.
    """

    DEFAULT_FLAGS = doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE

    def __init__(self, example, flags=DEFAULT_FLAGS):
        super().__init__(example, flags)


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
