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
    "deferred",
    "ShellTemplate",
    "xmlrpc_export",
    ]

from argparse import ArgumentParser
from functools import wraps
from os import fdopen
from pipes import quote
import signal
from subprocess import CalledProcessError
import sys

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

    def __call__(self, argv=None):
        try:
            self.setup()
            args = self.parser.parse_args(argv)
            args.handler.run(args)
        except CalledProcessError, error:
            # Print error.cmd and error.output too?
            raise SystemExit(error.returncode)
        except KeyboardInterrupt:
            pass
