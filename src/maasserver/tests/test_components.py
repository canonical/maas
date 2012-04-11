# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver components module."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []


import random

from maasserver import components
from maasserver.components import (
    COMPONENT,
    discard_persistent_error,
    get_persistent_errors,
    persistent_errors,
    register_persistent_error,
    )
from maasserver.testing.enum import map_enum
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase


def simple_error_display(error):
    return str(error)


def get_random_component():
    random.choice(map_enum(COMPONENT).values())


class PersistentErrorsUtilitiesTest(TestCase):

    def setUp(self):
        super(PersistentErrorsUtilitiesTest, self).setUp()
        self._PERSISTENT_ERRORS = {}
        self.patch(components, '_PERSISTENT_ERRORS', self._PERSISTENT_ERRORS)
        self.patch(components, '_display_fault', simple_error_display)

    def test_register_persistent_error_registers_error(self):
        error = Exception(factory.getRandomString())
        component = get_random_component()
        register_persistent_error(component, error)
        self.assertItemsEqual(
            {component: simple_error_display(error)}, self._PERSISTENT_ERRORS)

    def test_register_persistent_error_stores_last_error(self):
        error = Exception(factory.getRandomString())
        error2 = Exception(factory.getRandomString())
        component = get_random_component()
        register_persistent_error(component, error)
        register_persistent_error(component, error2)
        self.assertItemsEqual(
            {component: simple_error_display(error2)}, self._PERSISTENT_ERRORS)

    def test_discard_persistent_error_discards_error(self):
        error = Exception(factory.getRandomString())
        component = get_random_component()
        register_persistent_error(component, error)
        discard_persistent_error(component)
        self.assertItemsEqual({}, self._PERSISTENT_ERRORS)

    def test_discard_persistent_error_can_be_called_many_times(self):
        error = Exception(factory.getRandomString())
        component = get_random_component()
        register_persistent_error(component, error)
        discard_persistent_error(component)
        discard_persistent_error(component)
        self.assertItemsEqual({}, self._PERSISTENT_ERRORS)

    def get_persistent_errors_returns_text_for_error_codes(self):
        errors, components = [], []
        for i in range(3):
            error = Exception(factory.getRandomString())
            component = get_random_component()
            register_persistent_error(component, error)
            errors.append(error)
            components.append(component)
        self.assertItemsEqual(errors, get_persistent_errors())

    def test_error_sensor_registers_error_if_exception_raised(self):
        error = NotImplementedError(factory.getRandomString())
        component = get_random_component()

        @persistent_errors(NotImplementedError, component)
        def test_method():
            raise error

        self.assertRaises(NotImplementedError, test_method)
        self.assertItemsEqual(
            [simple_error_display(error)], get_persistent_errors())

    def test_error_sensor_registers_does_not_register_unknown_error(self):
        component = get_random_component()

        @persistent_errors(NotImplementedError, component)
        def test_method():
            raise ValueError()

        self.assertRaises(ValueError, test_method)
        self.assertItemsEqual([], get_persistent_errors())

    def test_error_sensor_discards_error_if_method_runs_successfully(self):
        error = Exception(factory.getRandomString())
        component = get_random_component()
        register_persistent_error(component, error)

        @persistent_errors(NotImplementedError, component)
        def test_method():
            pass

        self.assertItemsEqual(
            [simple_error_display(error)], get_persistent_errors())
        test_method()
        self.assertItemsEqual([], get_persistent_errors())

    def test_error_sensor_does_not_discard_error_if_unknown_exception(self):
        error = Exception(factory.getRandomString())
        component = get_random_component()
        register_persistent_error(component, error)

        @persistent_errors(NotImplementedError, component)
        def test_method():
            raise ValueError()

        self.assertItemsEqual(
            [simple_error_display(error)], get_persistent_errors())
        try:
            test_method()
        except ValueError:
            pass
        self.assertItemsEqual(
            [simple_error_display(error)], get_persistent_errors())
