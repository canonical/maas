# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :py:mod:`provisioningserver.rpc.exceptions`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maastesting.testcase import MAASTestCase
from provisioningserver.rpc.exceptions import MultipleFailures
from twisted.python.failure import Failure


class TestMultipleFailures(MAASTestCase):

    def test__with_no_failures(self):
        exc = MultipleFailures()
        self.assertSequenceEqual([], exc.args)

    def test__with_single_failure(self):
        errors = [AssertionError()]
        failures = [Failure(error) for error in errors]
        exc = MultipleFailures(*failures)
        self.assertSequenceEqual(failures, exc.args)

    def test__with_multiple_failures(self):
        errors = [AssertionError(), ZeroDivisionError()]
        failures = [Failure(error) for error in errors]
        exc = MultipleFailures(*failures)
        self.assertSequenceEqual(failures, exc.args)
