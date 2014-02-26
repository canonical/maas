# Copyright 2012 Canonical Ltd.  This software is licensed under the
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
    'IsCallable',
    'MockAnyCall',
    'MockCalledOnceWith',
    'MockCalledWith',
    'Provides',
    ]

from testtools.matchers import (
    Matcher,
    MatchesPredicate,
    Mismatch,
    )


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


class MockCalledWith:
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
            return Mismatch(e.message)

        return None


class MockCalledOnceWith(MockCalledWith):
    """Matches if the matchee Mock was called once with the provided args.
    
    Use of Mock.assert_called_once_with is discouraged as it passes if you typo
    the function name.
    """

    def match(self, mock):
        try:
            mock.assert_called_once_with(*self.args, **self.kwargs)
        except AssertionError as e:
            return Mismatch(e.message)

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
            return Mismatch(e.message)

        return None
