# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Command-related classes."""

__all__ = ["Command", "CommandError"]

from abc import ABCMeta, abstractmethod


class Command(metaclass=ABCMeta):
    """A base class for composing commands.

    This adheres to the expectations of `register`.
    """

    def __init__(self, parser):
        super(Command, self).__init__()
        self.parser = parser

    @abstractmethod
    def __call__(self, options):
        """Execute this command."""


CommandError = SystemExit
