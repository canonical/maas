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
from xmlrpclib import Fault

import fixtures
from provisioningserver import cobblerclient
from provisioningserver.testing.fakecobbler import fake_token
from testtools.content import text_content
from testtools.deferredruntest import (
    assert_fails_with,
    AsynchronousDeferredRunTest,
    AsynchronousDeferredRunTestForBrokenTwisted,
    )
from testtools.testcase import (
    ExpectedException,
    TestCase,
    )
from twisted.internet import defer
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import Clock


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
    def __init__(self, fake_token=None):
        self.fake_token = fake_token
        self.calls = []
        self.return_values = None

    def set_return_values(self, values):
        """Set predetermined value to return on following call(s).

        If any return value is an `Exception`, it will be raised instead.
        """
        self.return_values = values

    def callRemote(self, method, *args):
        if method == 'login':
            return defer.succeed(self.fake_token)

        self.calls.append((method, ) + args)
        if self.return_values:
            value = self.return_values.pop(0)
        else:
            value = None
        if isinstance(value, Exception):
            return defer.fail(value)
        else:
            return defer.succeed(value)


class DeadProxy(RecordingFakeProxy):
    """Fake proxy that returns nothing. Useful for timeout testing."""

    def callRemote(self, method, *args):
        return defer.Deferred()


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
        fake_token = kwargs.pop('fake_token')
        proxy_class = kwargs.pop('fake_proxy', RecordingFakeProxy)
        if proxy_class is None:
            proxy_class = RecordingFakeProxy

        self.fake_proxy = proxy_class(fake_token)
        super(RecordingSession, self).__init__(*args, **kwargs)

    def _make_twisted_proxy(self):
        return self.fake_proxy


def make_url_user_password():
    """Produce arbitrary API URL, username, and password."""
    return (
        'http://api.example.com/%d' % pick_number(),
        'username%d' % pick_number(),
        'password%d' % pick_number(),
        )


def make_recording_session(session_args=None, token=None,
                           fake_proxy=RecordingFakeProxy):
    """Create a `RecordingSession`."""
    if session_args is None:
        session_args = make_url_user_password()
    if token is None:
        token = fake_token()
    return RecordingSession(
        *session_args, fake_token=token, fake_proxy=fake_proxy)


class TestCobblerSession(TestCase):
    """Test session management against a fake XMLRPC session."""

    # Use a slightly longer timeout so that we can run these tests
    # against a real Cobbler.
    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    def test_initializes_but_does_not_authenticate_on_creation(self):
        url, user, password = make_url_user_password()
        session = make_recording_session(
            token=fake_token(user, 'not-yet-authenticated'))
        self.assertEqual(None, session.token)

    @inlineCallbacks
    def test_authenticate_authenticates_initially(self):
        token = fake_token('authenticated')
        session = make_recording_session(token=token)
        self.assertEqual(None, session.token)
        yield session._authenticate()
        self.assertEqual(token, session.token)

    @inlineCallbacks
    def test_state_cookie_stays_constant_during_normal_use(self):
        session = make_recording_session()
        state = session.record_state()
        self.assertEqual(state, session.record_state())
        yield session.call("some_method")
        self.assertEqual(state, session.record_state())

    @inlineCallbacks
    def test_authentication_changes_state_cookie(self):
        session = make_recording_session()
        old_cookie = session.record_state()
        yield session._authenticate()
        self.assertNotEqual(old_cookie, session.record_state())

    @inlineCallbacks
    def test_authenticate_backs_off_from_overwriting_concurrent_auth(self):
        session = make_recording_session()
        # Two requests are made concurrently.
        cookie_before_request_1 = session.record_state()
        cookie_before_request_2 = session.record_state()
        # Request 1 comes back with an authentication failure, and its
        # callback refreshes the session's auth token.
        yield session._authenticate(cookie_before_request_1)
        token_for_retrying_request_1 = session.token
        # Request 2 also comes back an authentication failure, and its
        # callback also asks the session to ensure that it is
        # authenticated.
        yield session._authenticate(cookie_before_request_2)
        token_for_retrying_request_2 = session.token

        # The double authentication does not confuse the session; both
        # callbacks get the same auth token for their retries.
        self.assertEqual(
            token_for_retrying_request_1, token_for_retrying_request_2)
        # The token they get is a new token, not the one they started
        # with.
        self.assertNotEqual(cookie_before_request_1, session.token)
        self.assertNotEqual(cookie_before_request_2, session.token)

    @inlineCallbacks
    def test_substitute_token_substitutes_only_placeholder(self):
        session = make_recording_session(token=fake_token('for-subst'))
        yield session._authenticate()
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
            session.token,
            arbitrary_string,
            None,
            ]
        self.assertEqual(
            outputs, apply_to_all(session._substitute_token, inputs))

    @inlineCallbacks
    def test_call_calls_xmlrpc(self):
        session = make_recording_session()
        return_value = 'returnval-%d' % pick_number()
        method = 'method_%d' % pick_number()
        arg = 'arg-%d' % pick_number()
        session.proxy.set_return_values([return_value])
        actual_return_value = yield session.call(method, arg)
        self.assertEqual(return_value, actual_return_value)
        self.assertEqual([(method, arg)], session.proxy.calls)

    @inlineCallbacks
    def test_call_reauthenticates_and_retries_on_auth_failure(self):
        # If a call triggers an authentication error, call()
        # re-authenticates and then re-issues the call.
        session = make_recording_session()
        yield session._authenticate()
        successful_return_value = pick_number()
        session.proxy.set_return_values([
            make_auth_failure(),
            successful_return_value,
            ])
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
        self.assertEqual(successful_return_value, ultimate_return_value)

    @inlineCallbacks
    def test_call_reauthentication_compares_against_original_cookie(self):
        # When a call triggers an authentication error, authenticate()
        # is called just once, with the state cookie from before the
        # call.  This ensures that it will always notice a concurrent
        # re-authentication that it needs to back off from.
        session = make_recording_session()
        yield session._authenticate()
        authenticate_cookies = []

        def fake_authenticate(previous_state):
            authenticate_cookies.append(previous_state)

        session._authenticate = fake_authenticate
        session.proxy.set_return_values([make_auth_failure()])
        state_before_call = session.record_state()
        yield session.call(
            "fail", cobblerclient.CobblerSession.token_placeholder)
        self.assertEqual([state_before_call], authenticate_cookies)

    @inlineCallbacks
    def test_call_raises_repeated_auth_failure(self):
        session = make_recording_session()
        yield session._authenticate()
        failures = [
            # Initial operation fails: not authenticated.
            make_auth_failure(),
            # But retry still raises authentication failure.
            make_auth_failure(),
            ]
        session.proxy.set_return_values(failures)
        with ExpectedException(failures[-1].__class__, failures[-1].message):
            return_value = yield session.call(
                'double_fail', cobblerclient.CobblerSession.token_placeholder)
            self.addDetail('return_value', text_content(repr(return_value)))

    @inlineCallbacks
    def test_call_raises_general_failure(self):
        session = make_recording_session()
        yield session._authenticate()
        failure = Exception("Memory error.  Where did I put it?")
        session.proxy.set_return_values([failure])
        with ExpectedException(Exception, failure.message):
            return_value = yield session.call('failing_method')
            self.addDetail('return_value', text_content(repr(return_value)))

    @inlineCallbacks
    def test_call_authenticates_immediately_if_unauthenticated(self):
        # If there is no auth token, and authentication is required,
        # call() authenticates right away rather than waiting for the
        # first call attempt to fail.
        session = make_recording_session()
        session.token = None
        session.proxy.set_return_values([pick_number()])
        yield session.call(
            'authenticate_me_first',
            cobblerclient.CobblerSession.token_placeholder)
        self.assertNotEqual(None, session.token)
        self.assertEqual(
            [('authenticate_me_first', session.token)], session.proxy.calls)


class TestConnectionTimeouts(TestCase, fixtures.TestWithFixtures):
    """Tests for connection timeouts on `CobblerSession`."""

    run_tests_with = AsynchronousDeferredRunTestForBrokenTwisted

    def test__with_timeout_cancels(self):
        # Winding a clock reactor past the timeout value should cancel
        # the original Deferred.
        clock = Clock()
        session = make_recording_session()
        d = session._with_timeout(defer.Deferred(), 1, clock)
        clock.advance(2)
        return assert_fails_with(d, defer.CancelledError)

    def test__with_timeout_not_cancelled_with_success(self):
        # Winding a clock reactor past the timeout of a *called*
        # (defer.succeed() is pre-fired) Deferred should not trigger a
        # cancellation.
        clock = Clock()
        session = make_recording_session()
        d = session._with_timeout(defer.succeed("frobnicle"), 1, clock)
        clock.advance(2)

        def result(value):
            self.assertEqual(value, "frobnicle")
            self.assertEqual([], clock.getDelayedCalls())

        return d.addCallback(result)

    def test__with_timeout_not_cancelled_unnecessarily(self):
        # Winding a clock reactor forwards but not past the timeout
        # should result in no cancellation.
        clock = Clock()
        session = make_recording_session()
        d = session._with_timeout(defer.Deferred(), 5, clock)
        clock.advance(1)
        self.assertFalse(d.called)

    def test__issue_call_times_out(self):
        clock = Clock()
        patch = fixtures.MonkeyPatch(
            "provisioningserver.cobblerclient.default_reactor", clock)
        self.useFixture(patch)

        session = make_recording_session(fake_proxy=DeadProxy)
        d = session._issue_call("login", "foo")
        clock.advance(cobblerclient.DEFAULT_TIMEOUT + 1)
        return assert_fails_with(d, defer.CancelledError)


class CobblerObject(TestCase):
    """Tests for the `CobblerObject` classes."""

    def test_name_method_inserts_type_name(self):
        self.assertEqual(
            'foo_system_bar',
            cobblerclient.CobblerSystem._name_method('foo_%s_bar'))

    def test_name_method_appends_s_for_plural(self):
        self.assertEqual(
            'x_systems_y',
            cobblerclient.CobblerSystem._name_method('x_%s_y', plural=True))

    def test_new_checks_required_attributes(self):
        # CobblerObject.new asserts that all required attributes for a
        # type of object are provided.
        session = make_recording_session()
        with ExpectedException(AssertionError):
            yield cobblerclient.CobblerSystem.new(
                session, 'incomplete_system', {})
