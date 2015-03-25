# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""testtools custom matchers"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'GreaterThanOrEqual',
    'HasAttribute',
    'IsCallable',
    'IsCallableMock',
    'IsFiredDeferred',
    'IsUnfiredDeferred',
    'LessThanOrEqual',
    'MockAnyCall',
    'MockCalledOnceWith',
    'MockCalledWith',
    'MockCallsMatch',
    'MockNotCalled',
    'Provides',
    ]

from functools import partial

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
    )
from twisted.internet import defer


class IsCallable(Matcher):
    """Matches if the matchee is callable."""

    def match(self, something):
        if not callable(something):
            return Mismatch("%r is not callable" % (something,))

    def __str__(self):
        return self.__class__.__name__


class Provides(MatchesPredicate):
    """Match if the given interface is provided."""

    def __init__(self, iface):
        super(Provides, self).__init__(
            iface.providedBy, "%%r does not provide %s" % iface.getName())


class HasAttribute(Matcher):
    """Match if the given attribute is available."""

    def __init__(self, attribute):
        super(HasAttribute, self).__init__()
        self.attribute = attribute

    def match(self, something):
        try:
            getattr(something, self.attribute)
        except AttributeError:
            return Mismatch(
                "%r does not have a %r attribute" % (
                    something, self.attribute))

    def __str__(self):
        return "%s(%r)" % (self.__class__.__name__, self.attribute)


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
        return "%s(args=%r, kwargs=%r)" % (
            self.__class__.__name__, self.args, self.kwargs)

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
        return "%s(%r)" % (
            self.__class__.__name__, self.calls)

    def match(self, mock):

        matcher = MatchesAll(
            IsCallableMock(),
            Annotate(
                "calls do not match",
                AfterPreprocessing(
                    get_mock_calls,
                    Equals(self.calls)),
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
                AfterPreprocessing(
                    get_mock_calls,
                    HasLength(0)),
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
            return Mismatch("%r is not a Deferred" % (thing,))
        if not thing.called:
            return Mismatch("%r has not been called" % (thing,))
        return None


class IsUnfiredDeferred(Matcher):
    """Matches if the subject is an unfired `Deferred`."""

    def __str__(self):
        return self.__class__.__name__

    def match(self, thing):
        if not isinstance(thing, defer.Deferred):
            return Mismatch("%r is not a Deferred" % (thing,))
        if thing.called:
            return Mismatch(
                "%r has been called (result=%r)" % (thing, thing.result))
        return None


class MatchesPartialCall(Matcher):

    def __init__(self, func, *args, **keywords):
        super(MatchesPartialCall, self).__init__()
        self.expected = partial(func, *args, **keywords)

    def match(self, observed):
        matcher = MatchesAll(
            IsInstance(partial),
            MatchesStructure.fromExample(
                self.expected, "func", "args", "keywords"),
            first_only=True,
        )
        return matcher.match(observed)


def GreaterThanOrEqual(value):
    return MatchesAny(GreaterThan(value), Equals(value))


def LessThanOrEqual(value):
    return MatchesAny(LessThan(value), Equals(value))
