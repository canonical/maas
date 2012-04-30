# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver components module."""

from __future__ import (
    absolute_import,
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
    register_persistent_error,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
from maasserver.utils import map_enum


def simple_error_display(error):
    return str(error)


def get_random_component():
    random.choice(map_enum(COMPONENT).values())


class PersistentErrorsUtilitiesTest(TestCase):

    def setUp(self):
        super(PersistentErrorsUtilitiesTest, self).setUp()
        self._PERSISTENT_ERRORS = {}
        self.patch(components, '_PERSISTENT_ERRORS', self._PERSISTENT_ERRORS)

    def test_register_persistent_error_registers_error(self):
        error_message = factory.getRandomString()
        component = get_random_component()
        register_persistent_error(component, error_message)
        self.assertItemsEqual(
            {component: error_message}, self._PERSISTENT_ERRORS)

    def test_register_persistent_error_stores_last_error(self):
        error_message = factory.getRandomString()
        error_message2 = factory.getRandomString()
        component = get_random_component()
        register_persistent_error(component, error_message)
        register_persistent_error(component, error_message2)
        self.assertItemsEqual(
            {component: error_message2}, self._PERSISTENT_ERRORS)

    def test_discard_persistent_error_discards_error(self):
        error_message = factory.getRandomString()
        component = get_random_component()
        register_persistent_error(component, error_message)
        discard_persistent_error(component)
        self.assertItemsEqual({}, self._PERSISTENT_ERRORS)

    def test_discard_persistent_error_can_be_called_many_times(self):
        error_message = factory.getRandomString()
        component = get_random_component()
        register_persistent_error(component, error_message)
        discard_persistent_error(component)
        discard_persistent_error(component)
        self.assertItemsEqual({}, self._PERSISTENT_ERRORS)

    def get_persistent_errors_returns_text_for_error_codes(self):
        errors, components = [], []
        for i in range(3):
            error_message = factory.getRandomString()
            component = get_random_component()
            register_persistent_error(component, error_message)
            errors.append(error_message)
            components.append(component)
        self.assertItemsEqual(errors, get_persistent_errors())
