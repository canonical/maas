# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for the provisioning server."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "ActionScript",
    "atomic_write",
    "deferred",
    "incremental_write",
    "MainScript",
    "parse_key_value_file",
    "ShellTemplate",
    ]

from argparse import ArgumentParser
import errno
from functools import wraps
import os
from os import fdopen
from pipes import quote
import signal
from subprocess import CalledProcessError
import sys
import tempfile
from time import time

from lockfile import FileLock
from provisioningserver.config import Config
import tempita
from twisted.internet.defer import maybeDeferred


def deferred(func):
    """Decorates a function to ensure that it always returns a `Deferred`.

    This also serves a secondary documentation purpose; functions decorated
    with this are readily identifiable as asynchronous.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        return maybeDeferred(func, *args, **kwargs)
    return wrapper


def _write_temp_file(content, filename):
    """Write the given `content` in a temporary file next to `filename`."""
    # Write the file to a temporary place (next to the target destination,
    # to ensure that it is on the same filesystem).
    directory = os.path.dirname(filename)
    temp_fd, temp_file = tempfile.mkstemp(
        dir=directory, suffix=".tmp",
        prefix=".%s." % os.path.basename(filename))
    with os.fdopen(temp_fd, "wb") as f:
        f.write(content)
    return temp_file


def atomic_write(content, filename, overwrite=True):
    """Write `content` into the file `filename` in an atomic fashion."""
    # If not overwrite: use filelock to gain an exclusive access to the
    # destination file.
    if not overwrite:
        lock = FileLock(filename)
        # Acquire an exclusive lock on this file.
        lock.acquire()
        try:
            if not os.path.isfile(filename):
                temp_file = _write_temp_file(content, filename)
                os.rename(temp_file, filename)
        finally:
            # Release the lock.
            lock.release()
    else:
        # Rename the temporary file to `filename`, that operation is atomic on
        # POSIX systems.
        temp_file = _write_temp_file(content, filename)
        os.rename(temp_file, filename)


def incremental_write(content, filename):
    """Write the given `content` into the file `filename` and
    increment the modification time by 1 sec.
    """
    old_mtime = get_mtime(filename)
    atomic_write(content, filename)
    new_mtime = pick_new_mtime(old_mtime)
    os.utime(filename, (new_mtime, new_mtime))


def get_mtime(filename):
    """Return a file's modification time, or None if it does not exist."""
    try:
        return os.stat(filename).st_mtime
    except OSError as e:
        if e.errno == errno.ENOENT:
            # File does not exist.  Be helpful, return None.
            return None
        else:
            # Other failure.  The caller will want to know.
            raise


def pick_new_mtime(old_mtime=None, starting_age=1000):
    """Choose a new modification time for a file that needs it updated.

    This function is used to manage the modification time of files
    for which we need to see an increment in the modification time
    each time the file is modified.  This is the case for DNS zone
    files which only get properly reloaded if BIND sees that the
    modification time is > to the time it has in its database.

    Modification time can have a resolution as low as one second in
    some relevant environments (we have observed this with ext3).
    To produce mtime changes regardless, we set a file's modification
    time in the past when it is first written, and
    increment it by 1 second on each subsequent write.

    However we also want to be careful not to set the modification time
    in the future, mostly because BIND does not deal with that very
    well.

    :param old_mtime: File's previous modification time, as a number
        with a unity of one second, or None if it did not previously
        exist.
    :param starting_age: If the file did not exist previously, set its
        modification time this many seconds in the past.
    """
    now = time()
    if old_mtime is None:
        # File is new.  Set modification time in the past to have room for
        # sub-second modifications.
        return now - starting_age
    elif old_mtime + 1 <= now:
        # There is room to increment the file's mtime by one second
        # without ending up in the future.
        return old_mtime + 1
    else:
        # We can't increase the file's modification time.  Give up and
        # return the previous modification time.
        return old_mtime


def split_lines(input, separator):
    """Split each item from `input` into a key/value pair."""
    return (line.split(separator, 1) for line in input if line.strip() != '')


def strip_pairs(input):
    """Strip whitespace of each key/value pair in input."""
    return ((key.strip(), value.strip()) for (key, value) in input)


def parse_key_value_file(file_name, separator=":"):
    """Parse a text file into a dict of key/value pairs.

    Use this for simple key:value or key=value files. There are no
    sections, as required for python's ConfigParse. Whitespace and empty
    lines are ignored.

    :param file_name: Name of file to parse.
    :param separator: The text that separates each key from its value.
    """
    with open(file_name, 'rb') as input:
        return dict(strip_pairs(split_lines(input, separator)))


class Safe:
    """An object that is safe to render as-is."""

    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return "<%s %r>" % (
            self.__class__.__name__, self.value)


class ShellTemplate(tempita.Template):
    """A Tempita template specialised for writing shell scripts.

    By default, substitutions will be escaped using `pipes.quote`, unless
    they're marked as safe. This can be done using Tempita's filter syntax::

      {{foobar|safe}}

    or as a plain Python expression::

      {{safe(foobar)}}

    """

    default_namespace = dict(
        tempita.Template.default_namespace,
        safe=Safe)

    def _repr(self, value, pos):
        """Shell-quote the value by default."""
        rep = super(ShellTemplate, self)._repr
        if isinstance(value, Safe):
            return rep(value.value, pos)
        else:
            return quote(rep(value, pos))


class ActionScript:
    """A command-line script that follows a command+verb pattern.

    It is probably worth replacing this with Commandant_ or something similar
    - just bzrlib.commands for example - in the future, so we don't have to
    maintain this.

    .. _Commandant: https://launchpad.net/commandant
    """

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
        except CalledProcessError, error:
            # Print error.cmd and error.output too?
            raise SystemExit(error.returncode)
        except KeyboardInterrupt:
            raise SystemExit(1)
        else:
            raise SystemExit(0)


class MainScript(ActionScript):
    """An `ActionScript` that always accepts a `--config-file` option.

    The `--config-file` option defaults to the value of
    `MAAS_PROVISIONING_SETTINGS` in the process's environment, otherwise
    `etc/maas/pserv.yaml` relative to the current directory or if that does
    not exist, `/etc/maas/pserv.yaml`.
    """

    def __init__(self, description):
        super(MainScript, self).__init__(description)
        self.parser.add_argument(
            "-c", "--config-file", metavar="FILENAME",
            help="Configuration file to load [%(default)s].",
            default=Config.DEFAULT_FILENAME)
