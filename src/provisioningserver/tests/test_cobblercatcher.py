# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for conversion of Cobbler exceptions to `ProvisioningError`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from abc import (
    ABCMeta,
    abstractmethod,
    )
from unittest import skipIf
from xmlrpclib import Fault

from maastesting.factory import factory
from provisioningserver.cobblercatcher import (
    convert_cobbler_exception,
    divine_fault_code,
    extract_text,
    ProvisioningError,
    )
from provisioningserver.cobblerclient import CobblerSystem
from provisioningserver.enum import PSERV_FAULT
from provisioningserver.testing.fakecobbler import (
    fake_auth_failure_string,
    fake_token,
    make_fake_cobbler_session,
    )
from provisioningserver.testing.realcobbler import RealCobbler
from provisioningserver.utils import deferred
from testtools import TestCase
from testtools.deferredruntest import AsynchronousDeferredRunTest
from twisted.internet.defer import inlineCallbacks


class TestExceptionConversionWithFakes(TestCase):
    """Tests for handling of Cobbler errors by cobblercatcher.

    Can be targeted to real or fake Cobbler.
    """

    def test_recognizes_auth_expiry(self):
        original_fault = Fault(1, fake_auth_failure_string(fake_token()))
        converted_fault = convert_cobbler_exception(original_fault)
        self.assertEqual(
            PSERV_FAULT.COBBLER_AUTH_ERROR, converted_fault.faultCode)

    def test_extract_text_leaves_unrecognized_message_intact(self):
        text = factory.getRandomString()
        self.assertEqual(text, extract_text(text))

    def test_extract_text_strips_CX(self):
        text = factory.getRandomString()
        self.assertEqual(
            text,
            extract_text("<class 'cobbler.cexceptions.CX'>:'%s'" % text))

    def test_divine_fault_code_recognizes_errors(self):
        errors = {
            "login failed (%s)": PSERV_FAULT.COBBLER_AUTH_FAILED,
            "invalid token: %s": PSERV_FAULT.COBBLER_AUTH_ERROR,
            "invalid profile name: %s": PSERV_FAULT.NO_SUCH_PROFILE,
            "Huh? %s. Aaaaargh!": PSERV_FAULT.GENERIC_COBBLER_ERROR,
        }
        random = factory.getRandomString()
        self.assertEqual(
            errors, {
                text: divine_fault_code(text % random)
                for text in errors.keys()})

    def test_convert_cobbler_exception_passes_through_other_faults(self):
        original_fault = Fault(1234, "Error while talking to Cobbler")
        converted_fault = convert_cobbler_exception(original_fault)
        self.assertEqual(
            (PSERV_FAULT.NO_COBBLER, original_fault.faultString),
            (converted_fault.faultCode, converted_fault.faultString))

    def test_convert_cobbler_exception_converts_to_provisioning_error(self):
        self.assertIsInstance(
            convert_cobbler_exception(Fault(1, "Kaboom")), ProvisioningError)

    def test_convert_cobbler_exception_checks_against_double_conversion(self):
        self.assertRaises(
            AssertionError,
            convert_cobbler_exception,
            ProvisioningError(1, "Ayiieee!"))


class FaultFinder:
    """Context manager: catch and store a :class:`Fault` exception.

    :ivar fault: The Fault this context manager caught.  This attribute will
        not exist if no Fault occurred.
    """

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.fault = exc_val
        return isinstance(exc_val, Fault)


class ExceptionConversionTests:
    """Tests for exception handling; run against a Cobbler (real or fake)."""

    __metaclass__ = ABCMeta

    @abstractmethod
    def get_cobbler_session(self):
        """Override: provide a (real or fake) :class:`CobblerSession`.

        :return: A :class:`Deferred` which in turn will return a
            :class:`CobblerSession`.
        """

    @inlineCallbacks
    def test_bad_token_means_token_expired(self):
        session = yield self.get_cobbler_session()
        session.token = factory.getRandomString()
        arbitrary_id = factory.getRandomString()

        faultfinder = FaultFinder()
        with faultfinder:
            yield session._issue_call(
                'xapi_object_edit', 'repo', 'repo-%s' % arbitrary_id,
                'edit', {'mirror': 'on-the-wall'}, session.token)

        self.assertEqual(
            PSERV_FAULT.COBBLER_AUTH_ERROR, faultfinder.fault.faultCode)

    @inlineCallbacks
    def test_bad_profile_name_is_distinct_error(self):
        session = yield self.get_cobbler_session()
        arbitrary_id = factory.getRandomString()

        faultfinder = FaultFinder()
        with faultfinder:
            yield CobblerSystem.new(
                session, 'system-%s' % arbitrary_id,
                {'profile': 'profile-%s' % arbitrary_id})

        self.assertEqual(
            PSERV_FAULT.NO_SUCH_PROFILE, faultfinder.fault.faultCode)


class TestExceptionConversionWithFakeCobbler(ExceptionConversionTests,
                                             TestCase):
    """Run `ExceptionConversionTests` against a fake Cobbler instance.

    All tests from `ExceptionConversionTests` are included here through
    inheritance.
    """

    run_tests_with = AsynchronousDeferredRunTest

    @deferred
    def get_cobbler_session(self):
        return make_fake_cobbler_session()


class TestExceptionConversionWithRealCobbler(ExceptionConversionTests,
                                             TestCase):
    """Run `ExceptionConversionTests` against a real Cobbler instance.

    Activate this by setting the PSERV_TEST_COBBLER_URL environment variable
    to point to a real Cobbler instance.

    All tests from `ExceptionConversionTests` are included here through
    inheritance.
    """

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    real_cobbler = RealCobbler()

    @real_cobbler.skip_unless_available
    @deferred
    def get_cobbler_session(self):
        return self.real_cobbler.get_session()
