# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver components module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


import random

from maasserver.components import (
    discard_persistent_error,
    get_persistent_error,
    get_persistent_errors,
    register_persistent_error,
)
from maasserver.enum import COMPONENT
from maasserver.models.component_error import ComponentError
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from provisioningserver.utils.enum import map_enum


def get_random_component():
    return random.choice(map_enum(COMPONENT).values())


class PersistentErrorsUtilitiesTest(MAASServerTestCase):

    def setUp(self):
        super(PersistentErrorsUtilitiesTest, self).setUp()

    def test_register_persistent_error_registers_error(self):
        error_message = factory.make_string()
        component = get_random_component()
        register_persistent_error(component, error_message)
        self.assertItemsEqual([error_message], get_persistent_errors())

    def test_register_persistent_error_stores_last_error(self):
        error_message = factory.make_string()
        error_message2 = factory.make_string()
        component = get_random_component()
        register_persistent_error(component, error_message)
        register_persistent_error(component, error_message2)
        self.assertItemsEqual(
            [error_message2], get_persistent_errors())

    def test_discard_persistent_error_discards_error(self):
        error_message = factory.make_string()
        component = get_random_component()
        register_persistent_error(component, error_message)
        discard_persistent_error(component)
        self.assertItemsEqual([], get_persistent_errors())

    def test_discard_persistent_error_can_be_called_many_times(self):
        error_message = factory.make_string()
        component = get_random_component()
        register_persistent_error(component, error_message)
        discard_persistent_error(component)
        discard_persistent_error(component)
        self.assertItemsEqual([], get_persistent_errors())

    def get_persistent_errors_returns_text_for_error_codes(self):
        errors, components = [], []
        for _ in range(3):
            error_message = factory.make_string()
            component = get_random_component()
            register_persistent_error(component, error_message)
            errors.append(error_message)
            components.append(component)
        self.assertItemsEqual(errors, get_persistent_errors())

    def test_get_persistent_error_returns_None_if_no_error(self):
        self.assertIsNone(get_persistent_error(factory.make_name('component')))

    def test_get_persistent_error_returns_component_error(self):
        component = factory.make_name('component')
        error = factory.make_name('error')
        register_persistent_error(component, error)
        self.assertEqual(error, get_persistent_error(component))

    def test_register_persistent_error_reuses_component_errors(self):
        """When registering a persistent error that already has an error
        recorded for that component, reuse the error instead of deleting and
        recreating it."""
        component = factory.make_name('component')
        error1 = factory.make_name('error')
        error2 = factory.make_name('error')
        register_persistent_error(component, error1)
        error = ComponentError.objects.get(component=component)
        self.assertEqual(error.error, error1)  # Should be our error
        error_id = error.id
        register_persistent_error(component, error2)
        error = ComponentError.objects.get(component=component)
        self.assertEqual(error.error, error2)  # Should update the message
        self.assertEqual(error.id, error_id)  # Should reuse the same id
