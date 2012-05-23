# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Celery tasks."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from testresources import FixtureResource

from maastesting.celery import CeleryFixture
from maastesting.testcase import TestCase
from provisioningserver.enum import POWER_TYPE
from provisioningserver.power.poweraction import PowerActionFail
from provisioningserver.tasks import power_on


class TaskTestCase(TestCase):

    def assertSuccess(self, task_result):
        self.assertEqual("SUCCESS", task_result.status)


class TestPowerTasks(TaskTestCase):

    resources = (
        ("celery", FixtureResource(CeleryFixture())),
        )

    def test_ether_wake_power_on_with_not_enough_template_args(self):
        # In eager test mode the assertion is raised immediately rather
        # than being stored in the AsyncResult, so we need to test for
        # that instead of using result.get().
        self.assertRaises(
            PowerActionFail, power_on.delay, POWER_TYPE.WAKE_ON_LAN)

    def test_ether_wake_power_on(self):
        mac = "AA:BB:CC:DD:EE:FF"
        result = power_on.delay(POWER_TYPE.WAKE_ON_LAN, mac=mac)
        self.assertSuccess(result)
