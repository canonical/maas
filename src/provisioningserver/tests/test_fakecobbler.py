# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    print_function,
    unicode_literals,
    )

"""Tests for the fake Cobbler API."""

__metaclass__ = type
__all__ = []

from unittest import TestCase

from provisioningserver.cobblerclient import (
    CobblerSession,
    CobblerSystem,
    )
from provisioningserver.testing.fakecobbler import (
    FakeCobbler,
    FakeTwistedProxy,
    )
from testtools.deferredruntest import AsynchronousDeferredRunTest
from twisted.internet.defer import inlineCallbacks


class FakeCobblerSession(CobblerSession):
    """A `CobblerSession` instrumented not to use real XMLRPC."""

    def __init__(self, url, user, password, fake_cobbler=None):
        self.fake_proxy = FakeTwistedProxy(fake_cobbler=fake_cobbler)
        super(FakeCobblerSession, self).__init__(url, user, password)

    def _make_twisted_proxy(self):
        return self.fake_proxy

    def _login(self):
        self.token = self.proxy.fake_cobbler.login(self.user, self.password)


def fake_cobbler_session(url=None, user=None, password=None,
                         fake_cobbler=None):
    """Fake a CobblerSession."""
    session = FakeCobblerSession(
        url, user, password, fake_cobbler=fake_cobbler)
    session.authenticate()
    return session


class TestFakeCobbler(TestCase):
    """Test `FakeCobbler`.

    These tests should also pass if run against a real (clean) Cobbler.
    """

    run_tests_with = AsynchronousDeferredRunTest.make_factory()

    def test_login_failure_raises_failure(self):
        cobbler = FakeCobbler(passwords={'moi': 'potahto'})
        self.assertRaises(
            Exception,
            fake_cobbler_session,
            user='moi', password='potayto', fake_cobbler=cobbler)

    @inlineCallbacks
    def test_expired_token_triggers_retry(self):
        cobbler = FakeCobbler(passwords={'user': 'pw'})
        session = fake_cobbler_session(
            user='user', password='pw', fake_cobbler=cobbler)
        # When an auth token expires, the server just forgets about it.
        old_token = session.token
        del cobbler.tokens[session.token]

        # Use of the token will now fail with an "invalid token"
        # error.  The Cobbler client notices this, re-authenticates, and
        # re-runs the method.
        yield CobblerSystem.new(session)

        # The re-authentication results in a fresh token.
        self.assertNotEqual(old_token, session.token)

    @inlineCallbacks
    def test_valid_token_does_not_raise_auth_error(self):
        cobbler = FakeCobbler(passwords={'user': 'password'})
        session = fake_cobbler_session(
            user='user', password='password', fake_cobbler=cobbler)
        old_token = session.token
        yield CobblerSystem.new(session)
        self.assertEqual(old_token, session.token)
