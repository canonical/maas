# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Miscellaneous test doubles.

See http://www.martinfowler.com/bliki/TestDouble.html for the nomenclature
used.
"""


class StubContext:
    """A stub context manager.

    :ivar entered: A boolean indicating if the context has been entered.
    :ivar exited: A boolean indicating if the context has been exited.
    :ivar unused: A boolean indicating if the context has yet to be used
        (i.e. it has been neither entered nor exited).
    :ivar active: A boolean indicating if the context is currently active
        (i.e. it has been entered but not exited).
    :ivar unused: A boolean indicating if the context has been used
        (i.e. it has been both entered and exited).
    :ivar exc_info: The ``exc_info`` tuple passed into ``__exit__``.
    """

    def __init__(self):
        super().__init__()
        self.entered = False
        self.exited = False

    @property
    def unused(self):
        return not self.entered and not self.exited

    @property
    def active(self):
        return self.entered and not self.exited

    @property
    def used(self):
        return self.entered and self.exited

    def __enter__(self):
        self.entered = True

    def __exit__(self, *exc_info):
        self.exc_info = exc_info
        self.exited = True
