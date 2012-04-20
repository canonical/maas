# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

"""Tests for the fake Cobbler API."""

__metaclass__ = type
__all__ = []

from maastesting.testcase import TestCase
from provisioningserver.cobblercatcher import ProvisioningError
from provisioningserver.cobblerclient import CobblerRepo
from provisioningserver.testing.factory import CobblerFakeFactory
from provisioningserver.testing.fakecobbler import (
    FakeCobbler,
    log_in_to_fake_cobbler,
    )
from testtools.content import text_content
from testtools.deferredruntest import AsynchronousDeferredRunTest
from testtools.testcase import ExpectedException
from twisted.internet.defer import inlineCallbacks


class TestFakeCobbler(TestCase, CobblerFakeFactory):
    """Test `FakeCobbler`.

    These tests should also pass if run against a real (clean) Cobbler.
    """
    # Use a longer timeout so that we can run these tests against a real
    # Cobbler.
    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    @inlineCallbacks
    def test_login_failure_raises_failure(self):
        cobbler = FakeCobbler(passwords={'moi': 'potahto'})
        with ExpectedException(ProvisioningError):
            return_value = yield log_in_to_fake_cobbler(
                user='moi', password='potayto', fake_cobbler=cobbler)
            self.addDetail('return_value', text_content(repr(return_value)))

    @inlineCallbacks
    def test_expired_token_triggers_retry(self):
        session = yield log_in_to_fake_cobbler()
        # When an auth token expires, the server just forgets about it.
        old_token = session.token
        session.fake_proxy.fake_cobbler.fake_retire_token(old_token)

        # Use of the token will now fail with an "invalid token"
        # error.  The Cobbler client notices this, re-authenticates, and
        # re-runs the method.
        yield self.fake_cobbler_object(session, CobblerRepo)

        # The re-authentication results in a fresh token.
        self.assertNotEqual(old_token, session.token)

    @inlineCallbacks
    def test_valid_token_does_not_raise_auth_error(self):
        session = yield log_in_to_fake_cobbler()
        old_token = session.token
        yield self.fake_cobbler_object(session, CobblerRepo)
        self.assertEqual(old_token, session.token)
