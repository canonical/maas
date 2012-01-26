# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    print_function,
    unicode_literals,
    )

"""Tests for `CobblerSession`."""

__metaclass__ = type
__all__ = []

from random import Random
from unittest import TestCase
from xmlrpclib import Fault

from provisioningserver import cobblerclient
from provisioningserver.testing.fakecobbler import fake_token
from testtools.content import text_content
from testtools.deferredruntest import AsynchronousDeferredRunTest
from testtools.testcase import ExpectedException
from twisted.internet.defer import (
    inlineCallbacks,
    returnValue,
    )


randomizer = Random()


def pick_number():
    """Pick an arbitrary number."""
    return randomizer.randint(0, 10 ** 9)


def apply_to_all(function, args):
    """List the results of `function(arg)` for each `arg` in `args`."""
    return list(map(function, args))


class FakeAuthFailure(Fault):
    """Imitated Cobbler authentication failure."""

    def __init__(self, token):
        super(FakeAuthFailure, self).__init__(1, "invalid token: %s" % token)


def make_auth_failure(broken_token=None):
    """Mimick a Cobbler authentication failure."""
    if broken_token is None:
        broken_token = fake_token()
    return FakeAuthFailure(broken_token)


class RecordingFakeProxy:
    """Simple fake Twisted XMLRPC proxy.

    Records XMLRPC calls, and returns predetermined values.
    """
    def __init__(self):
        self.calls = []
        self.return_values = None

    def set_return_values(self, values):
        """Set predetermined value to return on following call(s).

        If any return value is an `Exception`, it will be raised instead.
        """
        self.return_values = values

    @inlineCallbacks
    def callRemote(self, method, *args):
        self.calls.append((method, ) + args)
        if self.return_values:
            value = self.return_values.pop(0)
        else:
            value = None
        if isinstance(value, Exception):
            raise value
        else:
            value = yield value
            returnValue(value)


class RecordingSession(cobblerclient.CobblerSession):
    """A `CobblerSession` instrumented to run against a `RecordingFakeProxy`.

    :ivar fake_token: Auth token that login will pretend to receive.
    """

    def __init__(self, *args, **kwargs):
        """Create and instrument a session.

        In addition to the arguments for `CobblerSession.__init__`, pass a
        keyword argument `fake_proxy` to set a test double that the session
        will use for its proxy; and `fake_token` to provide a login token
        that the session should pretend it gets from the server on login.
        """
        self.fake_proxy = RecordingFakeProxy()
        self.fake_token = kwargs.pop('fake_token')
        super(RecordingSession, self).__init__(*args, **kwargs)

    def _make_twisted_proxy(self):
        return self.fake_proxy

    def _login(self):
        self.token = self.fake_token


class TestCobblerSession(TestCase):
    """Test session management against a fake XMLRPC session."""

    run_tests_with = AsynchronousDeferredRunTest.make_factory()

    def make_url_user_password(self):
        """Produce arbitrary API URL, username, and password."""
        return (
            'http://api.example.com/%d' % pick_number(),
            'username%d' % pick_number(),
            'password%d' % pick_number(),
            )

    def make_recording_session(self, session_args=None, token=None):
        """Create a `RecordingSession`."""
        if session_args is None:
            session_args = self.make_url_user_password()
        if token is None:
            token = fake_token()
        return RecordingSession(*session_args, fake_token=token)

    def test_initializes_but_does_not_authenticate_on_creation(self):
        url, user, password = self.make_url_user_password()
        session = self.make_recording_session(
            token=fake_token(user, 'not-yet-authenticated'))
        self.assertEqual(None, session.token)

    def test_authenticate_authenticates_initially(self):
        token = fake_token('authenticated')
        session = self.make_recording_session(token=token)
        self.assertEqual(None, session.token)
        session.authenticate()
        self.assertEqual(token, session.token)

    @inlineCallbacks
    def test_state_cookie_stays_constant_during_normal_use(self):
        session = self.make_recording_session()
        state = session.record_state()
        self.assertEqual(state, session.record_state())
        yield session.call("some_method")
        self.assertEqual(state, session.record_state())

    def test_authentication_changes_state_cookie(self):
        session = self.make_recording_session()
        old_cookie = session.record_state()
        session.authenticate()
        self.assertNotEqual(old_cookie, session.record_state())

    def test_authenticate_backs_off_from_overwriting_concurrent_auth(self):
        session = self.make_recording_session()
        # Two requests are made concurrently.
        cookie_before_request_1 = session.record_state()
        cookie_before_request_2 = session.record_state()
        # Request 1 comes back with an authentication failure, and its
        # callback refreshes the session's auth token.
        session.authenticate(cookie_before_request_1)
        token_for_retrying_request_1 = session.token
        # Request 2 also comes back an authentication failure, and its
        # callback also asks the session to ensure that it is
        # authenticated.
        session.authenticate(cookie_before_request_2)
        token_for_retrying_request_2 = session.token

        # The double authentication does not confuse the session; both
        # callbacks get the same auth token for their retries.
        self.assertEqual(
            token_for_retrying_request_1, token_for_retrying_request_2)
        # The token they get is a new token, not the one they started
        # with.
        self.assertNotEqual(cookie_before_request_1, session.token)
        self.assertNotEqual(cookie_before_request_2, session.token)

    def test_substitute_token_substitutes_only_placeholder(self):
        token = fake_token('for-substitution')
        session = self.make_recording_session(token=token)
        session.authenticate()
        arbitrary_number = pick_number()
        arbitrary_string = 'string-%d' % pick_number()
        inputs = [
            arbitrary_number,
            cobblerclient.CobblerSession.token_placeholder,
            arbitrary_string,
            None,
            ]
        outputs = [
            arbitrary_number,
            token,
            arbitrary_string,
            None,
            ]
        self.assertEqual(
            outputs, apply_to_all(session.substitute_token, inputs))

    @inlineCallbacks
    def test_call_calls_xmlrpc(self):
        session = self.make_recording_session()
        return_value = 'returnval-%d' % pick_number()
        method = 'method_%d' % pick_number()
        arg = 'arg-%d' % pick_number()
        session.proxy.set_return_values([return_value])
        actual_return_value = yield session.call(method, arg)
        self.assertEqual(return_value, actual_return_value)
        self.assertEqual([(method, arg)], session.proxy.calls)

    @inlineCallbacks
    def test_call_reauthenticates_and_retries_on_auth_failure(self):
        session = self.make_recording_session()
        session.proxy.set_return_values([make_auth_failure(), 555])
        session.proxy.calls = []
        old_token = session.token
        ultimate_return_value = yield session.call(
            "failing_method", cobblerclient.CobblerSession.token_placeholder)
        new_token = session.token
        self.assertEqual(
            [
                # Initial call to failing_method: auth failure.
                ('failing_method', old_token),
                # But call() re-authenticates, and retries.
                ('failing_method', new_token),
            ],
            session.proxy.calls)
        self.assertEqual(555, ultimate_return_value)

    @inlineCallbacks
    def test_call_raises_repeated_auth_failure(self):
        session = self.make_recording_session()
        failures = [
            # Initial operation fails: not authenticated.
            make_auth_failure(),
            # But retry still raises authentication failure.
            make_auth_failure(),
            ]
        session.proxy.set_return_values(failures)
        with ExpectedException(failures[-1].__class__, failures[-1].message):
            return_value = yield session.call('double_fail')
            self.addDetail('return_value', text_content(repr(return_value)))

    @inlineCallbacks
    def test_call_raises_general_failure(self):
        session = self.make_recording_session()
        failure = Exception("Memory error.  Where did I put it?")
        session.proxy.set_return_values([failure])
        with ExpectedException(Exception, failure.message):
            return_value = yield session.call('failing_method')
            self.addDetail('return_value', text_content(repr(return_value)))


class CobblerObject(TestCase):
    """Tests for the `CobblerObject` classes."""

    def test_name_method_inserts_type_name(self):
        self.assertEqual(
            'foo_system_bar',
            cobblerclient.CobblerSystem.name_method('foo_%s_bar'))

    def test_name_method_appends_s_for_plural(self):
        self.assertEqual(
            'x_systems_y',
            cobblerclient.CobblerSystem.name_method('x_%s_y', plural=True))
