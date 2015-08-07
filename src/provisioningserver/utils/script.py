# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for adding sub-commands to the MAAS management commands."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'ActionScript',
    'AtomicWriteScript',
    'MainScript',
    ]

from argparse import ArgumentParser
from os import fdopen
import signal
from subprocess import CalledProcessError
import sys

from provisioningserver.utils.fs import (
    atomic_delete,
    atomic_write,
)


class ActionScript:
    """A command-line script that follows a command+verb pattern."""

    def __init__(self, description):
        super(ActionScript, self).__init__()
        # See http://docs.python.org/release/2.7/library/argparse.html.
        self.parser = ArgumentParser(description=description)
        self.subparsers = self.parser.add_subparsers(title="actions")

    @staticmethod
    def setup():
        # Ensure stdout and stderr are line-bufferred.
        sys.stdout = fdopen(sys.stdout.fileno(), "ab", 1)
        sys.stderr = fdopen(sys.stderr.fileno(), "ab", 1)
        # Run the SIGINT handler on SIGTERM; `svc -d` sends SIGTERM.
        signal.signal(signal.SIGTERM, signal.default_int_handler)

    def register(self, name, handler, *args, **kwargs):
        """Register an action for the given name.

        :param name: The name of the action.
        :param handler: An object, a module for example, that has `run` and
            `add_arguments` callables. The docstring of the `run` callable is
            used as the help text for the newly registered action.
        :param args: Additional positional arguments for the subparser_.
        :param kwargs: Additional named arguments for the subparser_.

        .. _subparser:
          http://docs.python.org/
            release/2.7/library/argparse.html#sub-commands
        """
        parser = self.subparsers.add_parser(
            name, *args, help=handler.run.__doc__, **kwargs)
        parser.set_defaults(handler=handler)
        handler.add_arguments(parser)
        return parser

    def execute(self, argv=None):
        """Execute this action.

        This is intended for in-process invocation of an action, though it may
        still raise L{SystemExit}. The L{__call__} method is intended for when
        this object is executed as a script proper.
        """
        args = self.parser.parse_args(argv)
        args.handler.run(args)

    def __call__(self, argv=None):
        try:
            self.setup()
            self.execute(argv)
        except CalledProcessError as error:
            # Print error.cmd and error.output too?
            raise SystemExit(error.returncode)
        except KeyboardInterrupt:
            raise SystemExit(1)
        else:
            raise SystemExit(0)


class MainScript(ActionScript):
    """An `ActionScript` denoting the main script in an application."""


class AtomicWriteScript:
    """Wrap the atomic_write function turning it into an ActionScript.

    To use:
    >>> main = MainScript(atomic_write.__doc__)
    >>> main.register("myscriptname", AtomicWriteScript)
    >>> main()
    """

    @staticmethod
    def add_arguments(parser):
        """Initialise options for writing files atomically.

        :param parser: An instance of :class:`ArgumentParser`.
        """
        parser.add_argument(
            "--no-overwrite", action="store_true", required=False,
            default=False, help="Don't overwrite file if it exists")
        parser.add_argument(
            "--filename", action="store", required=True, help=(
                "The name of the file in which to store contents of stdin"))
        parser.add_argument(
            "--mode", action="store", required=False, default=None, help=(
                "They permissions to set on the file. If not set "
                "will be r/w only to owner"))

    @staticmethod
    def run(args):
        """Take content from stdin and write it atomically to a file."""
        content = sys.stdin.read()
        if args.mode is not None:
            mode = int(args.mode, 8)
        else:
            mode = 0o600
        atomic_write(
            content, args.filename, overwrite=not args.no_overwrite,
            mode=mode)


class AtomicDeleteScript:
    """Wrap the atomic_delete function turning it into an ActionScript.

    To use:
    >>> main = MainScript(atomic_delete.__doc__)
    >>> main.register("myscriptname", AtomicDeleteScript)
    >>> main()
    """

    @staticmethod
    def add_arguments(parser):
        """Initialise options for deleting files atomically.

        :param parser: An instance of :class:`ArgumentParser`.
        """
        parser.add_argument(
            "--filename", action="store", required=True, help=(
                "The name of the file in which to delete."))

    @staticmethod
    def run(args):
        """Delete the file atomically."""
        atomic_delete(args.filename)
