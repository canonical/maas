# -*- coding: utf-8 -*-
# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `provisioningserver.utils.introspect` module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import re

from maastesting.factory import factory
from maastesting.fixtures import CaptureStandardIO
from maastesting.matchers import (
    MockCalledOnceWith,
    Provides,
)
from maastesting.testcase import MAASTestCase
from mock import sentinel
from provisioningserver.utils.introspect import (
    Help,
    IntrospectionShell,
    IntrospectionShellFactory,
    IntrospectionShellService,
    serverFromString,
)
from testtools.matchers import (
    ContainsDict,
    Equals,
    Is,
    IsInstance,
    MatchesDict,
    MatchesStructure,
)
from twisted.application.internet import StreamServerEndpointService
from twisted.conch.insults import insults
from twisted.internet import (
    endpoints,
    reactor,
)
from twisted.internet.interfaces import IProtocolFactory


class TestServerFromString(MAASTestCase):
    """Tests for `serverFromString`."""

    def test__calls_through_to_twisteds_serverFromString(self):
        # Most of the time serverFromString() is a call-through to Twisted's
        # own serverFromString() function.
        twisted_serverFromString = self.patch(endpoints, "serverFromString")
        twisted_serverFromString.return_value = sentinel.server
        description = factory.make_name("description")
        self.assertThat(serverFromString(description), Is(sentinel.server))
        self.assertThat(
            twisted_serverFromString,
            MockCalledOnceWith(reactor, description))

    def test__raises_nice_error_when_description_cannot_be_parsed(self):
        # This is serverFromString()'s raison d'être: discarding the awful
        # errors that Twisted's serverFromString() raises and raising
        # something more user-friendly instead.
        description = factory.make_name("nonsense")
        error = self.assertRaises(ValueError, serverFromString, description)
        self.assertDocTestMatches(
            "Could not understand server description 'nonsense-...'. "
            "Try something like '...",
            unicode(error))

    def test__unicode_server_descriptions_are_converted_to_byte_strings(self):
        # Twisted's serverFromString() wants a byte string, so
        # serverFromString() ensures that's what we have.
        twisted_serverFromString = self.patch(endpoints, "serverFromString")
        description = factory.make_name("description")
        self.assertThat(description, IsInstance(unicode))
        serverFromString(description)
        [_, description_to_twisted] = twisted_serverFromString.call_args[0]
        self.assertThat(description_to_twisted, IsInstance(bytes))

    def test__non_string_server_descriptions_are_rejected(self):
        error = self.assertRaises(TypeError, serverFromString, sentinel.desc)
        self.assertThat(unicode(error), Equals(
            "Cannot safely convert sentinel.desc to a byte string."))


class TestHelp(MAASTestCase):
    """Tests for `Help`."""

    def test__has_nice_repr(self):
        help_repr = repr(Help())
        self.expectThat(help_repr, Equals(
            "Type help(object) for help about object."))
        # It has to be a byte string sadly.
        self.expectThat(help_repr, IsInstance(bytes))

    def test__returns_help_on_thing_when_invoked(self):
        with CaptureStandardIO() as stdio:
            Help()(Help)  # Check the help on itself.
        self.assertDocTestMatches(
            """\
            Help on class Help in module provisioningserver.utils.introspect:

            class Help(...)
            |  Define the builtin 'help'.
            ...


            """,
            stdio.getOutput())
        self.expectThat(stdio.getError(), Equals(""))

    def test__will_not_enter_interactive_mode(self):
        # The normal help() built-in will enter an interactive mode when
        # invoked without arguments. However, this stalls the Twisted reactor,
        # and thus breaks the introspection shell.
        with CaptureStandardIO() as stdio:
            Help()()  # Attempt to enter interactive mode.
        self.expectThat(stdio.getOutput().strip(), Equals(
            "Interactive help has been disabled. "
            "Type help(object) for help about object."))
        self.expectThat(stdio.getError(), Equals(""))


class TestIntrospectionShell(MAASTestCase):
    """Tests for `IntrospectionShell`."""

    def test__ensures_that_help_is_in_default_namespace(self):
        shell = IntrospectionShell()
        self.assertThat(
            shell.namespace, MatchesDict({
                "help": IsInstance(Help),
            }))

    def test__ensures_that_help_is_added_to_namespace(self):
        shell = IntrospectionShell(namespace={"foo": sentinel.bar})
        self.assertThat(
            shell.namespace, MatchesDict({
                "foo": Is(sentinel.bar),
                "help": IsInstance(Help),
            }))

    def test__ensures_that_help_is_not_clobbered(self):
        shell = IntrospectionShell(namespace={"help": sentinel.help})
        self.assertThat(
            shell.namespace, MatchesDict({
                "help": Is(sentinel.help),
            }))

    def test__welcomeMessage_is_friendly_and_useful(self):
        shell = IntrospectionShell(namespace={"help": sentinel.help})
        shell_factory = self.patch(shell, "factory")
        shell_factory.location = factory.make_name("location")

        expected = """\
        Welcome to MAAS's Introspection Shell.

        This is the %s.
        """
        expected %= shell_factory.location.upper()

        # It's definitely ASCII...
        observed = shell.welcomeMessage().decode("ascii")
        # but contains ANSI codes. Remove those before matching the content.
        observed = re.sub(r'\x1b[[]\d+m', r'', observed)

        self.assertDocTestMatches(expected, observed)


class TestIntrospectionShellFactory(MAASTestCase):
    """Tests for `IntrospectionShellFactory`."""

    def test__provides_IProtocolFactory(self):
        shell_factory = IntrospectionShellFactory(
            sentinel.location, sentinel.namespace)
        self.assertThat(shell_factory, Provides(IProtocolFactory))

    def test__builds_ServerProtocol(self):
        shell_factory = IntrospectionShellFactory(
            sentinel.location, sentinel.namespace)
        server_protocol = shell_factory.buildProtocol(sentinel.addr)
        self.assertThat(server_protocol, IsInstance(insults.ServerProtocol))
        self.assertThat(server_protocol, MatchesStructure(
            factory=Is(shell_factory),
            protocolFactory=Is(IntrospectionShell),
            protocolArgs=Equals((sentinel.namespace,)),
            protocolKwArgs=Equals({}),
        ))

    def test__ServerProtocol_builds_IntrospectionShell(self):
        location = factory.make_name("location")
        namespace = {factory.make_name("key"): factory.make_name("value")}
        shell_factory = IntrospectionShellFactory(location, namespace)
        server_protocol = shell_factory.buildProtocol(sentinel.addr)
        self.patch(server_protocol, "write")
        server_protocol.connectionMade()
        shell = server_protocol.terminalProtocol
        self.assertThat(shell, IsInstance(IntrospectionShell))
        self.assertThat(shell, MatchesStructure(
            factory=Is(shell_factory),
            terminal=Is(server_protocol),
            namespace=ContainsDict({
                key: Equals(value)
                for key, value in namespace.viewitems()
            }),
        ))


class TestIntrospectionShellService(MAASTestCase):
    """Tests for `IntrospectionShellService`."""

    def test__creates_factory(self):
        service = IntrospectionShellService(
            sentinel.location, sentinel.endpoint, sentinel.namespace)
        self.assertThat(service, IsInstance(StreamServerEndpointService))
        self.assertThat(service, MatchesStructure(
            endpoint=Is(sentinel.endpoint),
            factory=IsInstance(IntrospectionShellFactory),
        ))
        self.assertThat(service.factory, MatchesStructure(
            namespace=Is(sentinel.namespace),
            location=Is(sentinel.location),
        ))
