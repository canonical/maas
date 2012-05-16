# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maastesting.scenarios`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import unittest

from maastesting.scenarios import WithScenarios
from maastesting.testcase import TestCase


class TestWithScenarios(TestCase):

    def test_scenarios_applied(self):
        # Scenarios are applied correctly when a test is called via __call__()
        # instead of run().

        events = []

        class Test(WithScenarios, unittest.TestCase):

            scenarios = [
                ("one", dict(token="one")),
                ("two", dict(token="two")),
                ]

            def test(self):
                events.append(self.token)

        test = Test("test")
        test.__call__()

        self.assertEqual(["one", "two"], events)

    def test_scenarios_applied_by_call(self):
        # Scenarios are applied by __call__() when it is called first, and not
        # by run().

        events = []

        class Test(WithScenarios, unittest.TestCase):

            scenarios = [
                ("one", dict(token="one")),
                ("two", dict(token="two")),
                ]

            def test(self):
                events.append(self.token)

            def run(self, result=None):
                # Call-up right past WithScenarios.run() to show that it is
                # not responsible for applying scenarios, and __call__() is.
                super(WithScenarios, self).run(result)

        test = Test("test")
        test.__call__()

        self.assertEqual(["one", "two"], events)
