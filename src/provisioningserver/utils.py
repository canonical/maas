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
    "xmlrpc_export",
    ]

from argparse import ArgumentParser
from functools import wraps
import os
from os import fdopen
from pipes import quote
import signal
from subprocess import CalledProcessError
import sys
import tempfile
from time import time

from provisioningserver.config import Config
import tempita
from twisted.internet.defer import maybeDeferred
from zope.interface.interface import Method


def deferred(func):
    """Decorates a function to ensure that it always returns a `Deferred`.

    This also serves a secondary documentation purpose; functions decorated
    with this are readily identifiable as asynchronous.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        return maybeDeferred(func, *args, **kwargs)
    return wrapper


def xmlrpc_export(iface):
    """Class decorator to alias methods of a class with an "xmlrpc_" prefix.

    For each method defined in the given interface, the concrete method in the
    decorated class is copied to a new name of "xmlrpc_%(original_name)s". In
    combination with :class:`XMLRPC`, and the rest of the Twisted stack, this
    has the effect of exposing the method via XML-RPC.

    The decorated class must implement `iface`.
    """
    def decorate(cls):
        assert iface.implementedBy(cls), (
            "%s does not implement %s" % (cls.__name__, iface.__name__))
        for name in iface:
            element = iface[name]
            if isinstance(element, Method):
                method = getattr(cls, name)
                setattr(cls, "xmlrpc_%s" % name, method)
        return cls
    return decorate


def atomic_write(content, filename):
    """Write the given `content` into the file `filename` in an atomic
    fashion.
    """
    # Write the file to a temporary place (next to the target destination,
    # to ensure that it is on the same filesystem).
    directory = os.path.dirname(filename)
    temp_fd, temp_file = tempfile.mkstemp(
        dir=directory, suffix=".tmp",
        prefix=".%s." % os.path.basename(filename))
    with os.fdopen(temp_fd, "wb") as f:
        f.write(content)
    # Rename the temporary file to `filename`, that operation is atomic on
    # POSIX systems.
    os.rename(temp_file, filename)


def incremental_write(content, filename):
    """Write the given `content` into the file `filename` and
    increment the modification time by 1 sec.
    """
    old_mtime = None
    if os.path.exists(filename):
        old_mtime = os.stat(filename).st_mtime
    atomic_write(content, filename)
    increment_age(filename, old_mtime=old_mtime)


def increment_age(filename, old_mtime=None, delta=1000):
    """Increment the modification time by 1 sec compared to the given
    `old_mtime`.

    This function is used to manage the modification time of files
    for which we need to see an increment in the modification time
    each time the file is modified.  This is the case for DNS zone
    files which only get properly reloaded if BIND sees that the
    modification time is > to the time it has in its database.

    Since the resolution of the modification time is one second,
    we want to manually set the modification time in the past
    the first time the file is written and increment the mod
    time by 1 manually each time the file gets written again.

    We also want to be careful not to set the modification time in
    the future (mostly because BIND doesn't deal with that well).

    Finally, note that the access time is set to the same value as
    the modification time.
    """
    now = time()
    if old_mtime is None:
        # Set modification time in the past to have room for
        # sub-second modifications.
        new_mtime = now - delta
    else:
        # If the modification time can be incremented by 1 sec
        # without being in the future, do it.  Otherwise we give
        # up and set it to 'now'.
        if old_mtime + 1 <= now:
            new_mtime = old_mtime + 1
        else:
            new_mtime = old_mtime
    os.utime(filename, (new_mtime, new_mtime))


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
    `/etc/maas/pserv.yaml`.
    """

    def __init__(self, description):
        super(MainScript, self).__init__(description)
        self.parser.add_argument(
            "-c", "--config-file", metavar="FILENAME",
            help="Configuration file to load [%(default)s].",
            default=Config.DEFAULT_FILENAME)
