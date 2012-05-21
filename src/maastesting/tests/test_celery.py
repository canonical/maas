# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test matchers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import random

from celery import current_app
from celery.decorators import task
from celery.result import EagerResult
from maastesting.celery import CeleryFixture
from maastesting.testcase import TestCase
from testresources import FixtureResource


@task()
def task_add(x, y):
    return x + y


@task()
def task_exception(x, y):
    raise RuntimeError()


class TestCeleryFixture(TestCase):
    """Tests `CeleryFixture`."""

    resources = (
        ("celery", FixtureResource(CeleryFixture())),
        )

    def test_celery_config(self):
        self.assertTrue(current_app.conf.CELERY_ALWAYS_EAGER)
        self.assertTrue(current_app.conf.CELERY_EAGER_PROPAGATES_EXCEPTIONS)

    def test_celery_eagerresult_contains_result(self):
       # The result is an instance of EagerResult and it contains the actual
        # result.
        x = random.randrange(100)
        y = random.randrange(100)
        result = task_add.delay(x, y)
        self.assertIsInstance(result, EagerResult)
        self.assertEqual(x + y, result.result)

    def test_celery_exception_raised(self):
        self.assertRaises(RuntimeError, task_exception.delay, 1, 2)
