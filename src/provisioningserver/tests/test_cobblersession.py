# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

"""Tests for `CobblerSession`."""

__metaclass__ = type
__all__ = []

from random import Random
import re
from xmlrpclib import Fault

import fixtures
from maastesting.factory import factory
from provisioningserver import cobblerclient
from provisioningserver.cobblercatcher import ProvisioningError
from provisioningserver.enum import PSERV_FAULT
from provisioningserver.testing.fakecobbler import (
    fake_auth_failure_string,
    fake_object_not_found_string,
    fake_token,
    )
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
from twisted.internet.error import DNSLookupError
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
        super(FakeAuthFailure, self).__init__(
            1, fake_auth_failure_string(token))


def make_auth_failure():
    """Mimick a Cobbler authentication failure."""
    return FakeAuthFailure(fake_token())


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
        """Override for CobblerSession's proxy factory."""
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

    def test_looks_like_object_not_found_for_regular_exception(self):
        self.assertFalse(
            cobblerclient.looks_like_object_not_found(RuntimeError("Error")))

    def test_looks_like_object_not_found_for_other_Fault(self):
        self.assertFalse(
            cobblerclient.looks_like_object_not_found(
                Fault(1, "Missing sprocket")))

    def test_looks_like_object_not_found_recognizes_object_not_found(self):
        error = Fault(1, fake_object_not_found_string("distro", "bob"))
        self.assertTrue(
            cobblerclient.looks_like_object_not_found(error))

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
        with ExpectedException(ProvisioningError, failures[-1].message):
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

    @inlineCallbacks
    def test_dns_lookup_exception_handled(self):
        url = factory.getRandomString()
        session_args = (
            'http://%s/%d' % (url, pick_number()),
            factory.getRandomString(),  # username.
            factory.getRandomString(),  # password.
            )
        session = make_recording_session(session_args=session_args)
        failure = DNSLookupError(factory.getRandomString())
        session.proxy.set_return_values([failure])
        expected_exception = ProvisioningError(
            faultCode=PSERV_FAULT.COBBLER_DNS_LOOKUP_ERROR,
            faultString=url.lower())
        expected_exception_re = re.escape(unicode(expected_exception))
        with ExpectedException(ProvisioningError, expected_exception_re):
            yield session.call('failing_method')


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


class TestCobblerObject(TestCase):
    """Tests for the `CobblerObject` classes."""

    run_tests_with = AsynchronousDeferredRunTest

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

    @inlineCallbacks
    def test_new_attempts_edit_before_creating_new(self):
        # CobblerObject.new always attempts an extended edit operation on the
        # given object first, following by an add should the object not yet
        # exist.
        session = make_recording_session()
        not_found_string = fake_object_not_found_string("system", "carcass")
        not_found = Fault(1, not_found_string)
        session.proxy.set_return_values([not_found, True])
        yield cobblerclient.CobblerSystem.new(
            session, "carcass", {"profile": "heartwork"})
        expected_calls = [
            # First an edit is attempted...
            ("xapi_object_edit", "system", "carcass", "edit",
             {"name": "carcass", "profile": "heartwork"},
             session.token),
            # Followed by an add.
            ("xapi_object_edit", "system", "carcass", "add",
             {"name": "carcass", "profile": "heartwork"},
             session.token),
            ]
        self.assertEqual(expected_calls, session.proxy.calls)

    @inlineCallbacks
    def test_modify(self):
        session = make_recording_session()
        session.proxy.set_return_values([True])
        distro = cobblerclient.CobblerDistro(session, "fred")
        yield distro.modify({"kernel": "sanders"})
        expected_call = (
            "xapi_object_edit", "distro", distro.name, "edit",
            {"kernel": "sanders"}, session.token)
        self.assertEqual([expected_call], session.proxy.calls)

    @inlineCallbacks
    def test_modify_only_permits_certain_attributes(self):
        session = make_recording_session()
        distro = cobblerclient.CobblerDistro(session, "fred")
        expected = ExpectedException(
            AssertionError, "Unknown attribute for distro: machine")
        with expected:
            yield distro.modify({"machine": "head"})

    @inlineCallbacks
    def test_get_values_returns_only_known_attributes(self):
        session = make_recording_session()
        # Create a new CobblerDistro. The True return value means the faked
        # call to xapi_object_edit was successful.
        session.proxy.set_return_values([True])
        distro = yield cobblerclient.CobblerDistro.new(
            session, name="fred", attributes={
                "initrd": "an_initrd", "kernel": "a_kernel"})
        # Fake that Cobbler holds the following attributes about the distro
        # just created.
        values_stored = {
            "initrd": "an_initrd",
            "kernel": "a_kernel",
            "likes": "cabbage",
            "name": "fred",
            }
        session.proxy.set_return_values([values_stored])
        # However, CobblerObject.get_values() only returns attributes that are
        # in known_attributes.
        values_observed = yield distro.get_values()
        self.assertIn("initrd", values_observed)
        self.assertNotIn("likes", values_observed)

    @inlineCallbacks
    def test_get_all_values_returns_only_known_attributes(self):
        session = make_recording_session()
        # Create some new CobblerDistros. The True return values mean the
        # faked calls to xapi_object_edit were successful.
        session.proxy.set_return_values([True])
        yield cobblerclient.CobblerDistro.new(
            session, name="alice", attributes={
                "initrd": "an_initrd", "kernel": "a_kernel"})
        # Fake that Cobbler holds the following attributes about the distros
        # just created.
        values_stored = [
            {"initrd": "an_initrd",
             "kernel": "a_kernel",
             "likes": "cabbage",
             "name": "alice"},
            ]
        session.proxy.set_return_values([values_stored])
        # However, CobblerObject.get_all_values() only returns attributes that
        # are in known_attributes.
        values_observed = yield (
            cobblerclient.CobblerDistro.get_all_values(session))
        values_observed_for_alice = values_observed["alice"]
        self.assertIn("initrd", values_observed_for_alice)
        self.assertNotIn("likes", values_observed_for_alice)

    def test_known_attributes(self):
        # known_attributes, a class attribute, is always a frozenset.
        self.assertIsInstance(
            cobblerclient.CobblerObject.known_attributes,
            frozenset)
        self.assertIsInstance(
            cobblerclient.CobblerProfile.known_attributes,
            frozenset)

    def test_required_attributes(self):
        # required_attributes, a class attribute, is always a frozenset.
        self.assertIsInstance(
            cobblerclient.CobblerObject.required_attributes,
            frozenset)
        self.assertIsInstance(
            cobblerclient.CobblerDistro.required_attributes,
            frozenset)

    def test_modification_attributes(self):
        # modification_attributes, a class attribute, is always a frozenset.
        self.assertIsInstance(
            cobblerclient.CobblerObject.modification_attributes,
            frozenset)
        self.assertIsInstance(
            cobblerclient.CobblerDistro.modification_attributes,
            frozenset)
