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
    'ContainsAll',
    'IsCallable',
    ]

from testtools.matchers import (
    Contains,
    Matcher,
    MatchesAll,
    Mismatch,
    )


def ContainsAll(items):
    """Matches if the matchee contains all the provided items."""
# XXX: rvb 2012-04-30 bug=991743:  This matcher has been submitted
# upstream.  If it gets included in the next version of testtools, this code
# should be removed.
    return MatchesAll(*[Contains(item) for item in items], first_only=False)


class IsCallable(Matcher):
    """Matches if the matchee is callable."""

    def match(self, something):
        if not callable(something):
            return Mismatch("%r is not callable" % (something,))

    def __str__(self):
        return self.__class__.__name__
