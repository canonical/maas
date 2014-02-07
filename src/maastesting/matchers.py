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
