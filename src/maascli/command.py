# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Command-related classes."""

from abc import ABCMeta, abstractmethod


class Command(metaclass=ABCMeta):
    """A base class for composing commands.

    This adheres to the expectations of `register`.
    """

    # Whether to include the command in help output.
    #
    # Note that passing help=argparse.SUPPRESS doesn't work for subparsers,
    # only for command arguments
    hidden = False

    def __init__(self, parser):
        super().__init__()
        self.parser = parser

    @abstractmethod
    def __call__(self, options):
        """Execute this command."""


CommandError = SystemExit
