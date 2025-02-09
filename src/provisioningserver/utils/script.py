# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for adding sub-commands to the MAAS management commands."""

from argparse import ArgumentParser, RawDescriptionHelpFormatter
import io
import signal
from subprocess import CalledProcessError
import sys


class ActionScriptError(ValueError):
    """Exception which should be printed to `stderr` if raised."""

    def __init__(self, message, returncode=1):
        self.returncode = returncode
        super().__init__(message)


class ActionScript:
    """A command-line script that follows a command+verb pattern."""

    def __init__(self, description):
        super().__init__()
        # See http://docs.python.org/release/2.7/library/argparse.html.
        self.parser = ArgumentParser(description=description)
        self.subparsers = self.parser.add_subparsers(title="actions")

    @staticmethod
    def setup():
        # Run the SIGINT handler on SIGTERM; `svc -d` sends SIGTERM.
        signal.signal(signal.SIGTERM, signal.default_int_handler)
        # Ensure stdout and stderr are line-bufferred.
        if not sys.stdout.line_buffering:
            sys.stdout.flush()
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, sys.stdout.encoding, line_buffering=True
            )
        if not sys.stderr.line_buffering:
            sys.stderr.flush()
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, sys.stderr.encoding, line_buffering=True
            )

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
            name,
            *args,
            help=handler.run.__doc__,
            formatter_class=RawDescriptionHelpFormatter,
            **kwargs,
        )
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
        if getattr(args, "handler", None) is None:
            self.parser.error("Choose a sub-command.")
        else:
            args.handler.run(args)

    def __call__(self, argv=None):
        try:
            self.setup()
            self.execute(argv)
        except ActionScriptError as error:
            print(str(error), file=sys.stderr)
            raise SystemExit(error.returncode)  # noqa: B904
        except CalledProcessError as error:
            # Print error.cmd and error.output too?
            raise SystemExit(error.returncode)  # noqa: B904
        except KeyboardInterrupt:
            raise SystemExit(1)  # noqa: B904
        else:
            raise SystemExit(0)


class MainScript(ActionScript):
    """An `ActionScript` denoting the main script in an application."""
