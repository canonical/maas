# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Miscellaneous test doubles.

See http://www.martinfowler.com/bliki/TestDouble.html for the nomenclature
used.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "StubContext",
]


class StubContext:
    """A stub context manager.

    :ivar entered: A boolean indicating if the context has been entered.
    :ivar exited: A boolean indicating if the context has been exited.
    :ivar active: A boolean indicating if the context is currently active
        (i.e. it has been entered but not exited).
    :ivar exc_info: The ``exc_info`` tuple passed into ``__exit__``.
    """

    entered = False
    exited = False

    @property
    def active(self):
        return self.entered and not self.exited

    def __enter__(self):
        self.entered = True

    def __exit__(self, *exc_info):
        self.exc_info = exc_info
        self.exited = True
