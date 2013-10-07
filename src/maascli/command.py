# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Command-related classes."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'Command',
    'CommandError',
    ]

from abc import (
    ABCMeta,
    abstractmethod,
    )


class Command:
    """A base class for composing commands.

    This adheres to the expectations of `register`.
    """

    __metaclass__ = ABCMeta

    def __init__(self, parser):
        super(Command, self).__init__()
        self.parser = parser

    @abstractmethod
    def __call__(self, options):
        """Execute this command."""


CommandError = SystemExit
