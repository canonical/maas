# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test related classes and functions for maas and its applications."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'TestCase',
    'TestModelTestCase',
    ]

import unittest

from django.conf import settings
from django.core.management import call_command
from django.db.models import loading
import django.test
import testresources
import testtools


class TestCase(testtools.TestCase, django.test.TestCase):
    """`TestCase` for Metal as a Service.

    Supports test resources and fixtures.
    """

    # testresources.ResourcedTestCase does something similar to this class
    # (with respect to setUpResources and tearDownResources) but it explicitly
    # up-calls to unittest.TestCase instead of using super() even though it is
    # not guaranteed that the next class in the inheritance chain is
    # unittest.TestCase.

    resources = ()

    def setUp(self):
        super(TestCase, self).setUp()
        self.setUpResources()

    def setUpResources(self):
        testresources.setUpResources(
            self, self.resources, testresources._get_result())

    def tearDown(self):
        self.tearDownResources()
        super(TestCase, self).tearDown()

    def tearDownResources(self):
        testresources.tearDownResources(
            self, self.resources, testresources._get_result())

    # Django's implementation for this seems to be broken and was
    # probably only added to support compatibility with python 2.6.
    assertItemsEqual = unittest.TestCase.assertItemsEqual


class TestModelTestCase(TestCase):
    """A custom test case that adds support for test-only models.

    For instance, if you want to have a model object used solely for testing
    in your application 'myapp1' you would create a test case that uses
    TestModelTestCase as its base class and:
    - initialize self.app with 'myapp1.tests'
    - define the models used for testing in myapp1.tests.models

    This way the models defined in myapp1.tests.models will be available in
    this test case (and this test case only).
    """

    # Set the appropriate application to be loaded.
    app = None

    def _pre_setup(self):
        # Add the models to the db.
        self._original_installed_apps = list(settings.INSTALLED_APPS)
        assert self.app is not None, "TestCase.app must be defined!"
        settings.INSTALLED_APPS.append(self.app)
        loading.cache.loaded = False
        call_command('syncdb', interactive=False, verbosity=0)
        super(TestModelTestCase, self)._pre_setup()

    def _post_teardown(self):
        super(TestModelTestCase, self)._post_teardown()
        # Restore the settings.
        settings.INSTALLED_APPS = self._original_installed_apps
        loading.cache.loaded = False
