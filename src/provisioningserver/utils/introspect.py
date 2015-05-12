# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Twisted Application Plugin code for the MAAS Region."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "IntrospectionShellService",
    "serverFromString",
]

from twisted.application.internet import StreamServerEndpointService
from twisted.conch import manhole
from twisted.conch.insults import insults
from twisted.internet import (
    endpoints,
    reactor,
)
from twisted.internet.interfaces import IProtocolFactory
from zope.interface import implementer


def byteString(thing):
    """Convert `string` to a byte string."""
    if isinstance(thing, bytes):
        return thing
    elif isinstance(thing, unicode):
        return thing.encode("utf-8")
    else:
        raise TypeError(
            "Cannot safely convert %r to a byte string."
            % (thing,))


def serverFromString(description):
    """Parse `description` into an endpoint.

    Twisted's `endpoints.serverFromString` raises errors that are not
    particularly user-friendly, so we attempt something better here.
    """
    description = byteString(description)
    try:
        return endpoints.serverFromString(reactor, description)
    except ValueError:
        raise ValueError(
            "Could not understand server description %r. "
            "Try something like %r or %r." % (
                description, b"unix:/path/to/file:mode=660:lockfile=0",
                b"tcp:1234:interface=127.0.0.1"))


class Help(object):
    """Define the builtin 'help'.

    This is a wrapper around pydoc.help... with a twist, in that it disallows
    interactive use.
    """

    def __repr__(self):
        message = "Type help(object) for help about object."
        return message.encode("utf-8")

    def __call__(self, *args, **kwds):
        if len(args) == 0:
            message = "Interactive help has been disabled. %r" % self
            print(message.encode("utf-8"))
        else:
            from pydoc import help
            return help(*args, **kwds)


class IntrospectionShell(manhole.ColoredManhole):

    STYLE_BRIGHT_ON = '\x1b[1m'
    STYLE_OFF = '\x1b[0m'

    COLOUR_RED_ON = '\x1b[31m'
    COLOUR_MAGENTA_ON = '\x1b[35m'
    COLOUR_OFF = '\x1b[39m'

    def __init__(self, namespace=None):
        super(IntrospectionShell, self).__init__(namespace)
        self.ensureThereIsHelp()

    def ensureThereIsHelp(self):
        if self.namespace is None:
            self.namespace = {"help": Help()}
        elif "help" in self.namespace:
            pass  # Don't override.
        else:
            self.namespace["help"] = Help()

    def welcomeMessage(self):
        return "".join((
            self.STYLE_BRIGHT_ON,
            self.COLOUR_MAGENTA_ON,
            "Welcome to MAAS's Introspection Shell.",
            self.COLOUR_OFF,
            self.STYLE_OFF,
            "\n\n",
            self.STYLE_BRIGHT_ON,
            "This is the ",
            self.COLOUR_RED_ON,
            self.factory.location.upper(),
            self.COLOUR_OFF,
            ".",
            self.STYLE_OFF,
        ))

    def initializeScreen(self):
        """Override in order to provide welcome message."""
        self.terminal.reset()
        self.addOutput(b"\n")
        self.addOutput(self.welcomeMessage().encode("utf-8"))
        self.addOutput(b"\n")
        self.addOutput(b"\n")
        self.setInsertMode()
        self.drawInputLine()


@implementer(IProtocolFactory)
class IntrospectionShellFactory:

    def __init__(self, location, namespace):
        super(IntrospectionShellFactory, self).__init__()
        self.namespace = namespace
        self.location = location

    def buildProtocol(self, addr):
        proto = insults.ServerProtocol(
            IntrospectionShell, self.namespace)
        proto.factory = self
        return proto

    def doStart(self):
        """See `IProtocolFactory`."""

    def doStop(self):
        """See `IProtocolFactory`."""


class IntrospectionShellService(StreamServerEndpointService):

    def __init__(self, location, endpoint, namespace):
        factory = IntrospectionShellFactory(location, namespace=namespace)
        super(IntrospectionShellService, self).__init__(endpoint, factory)
