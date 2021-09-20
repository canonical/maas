# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver components module."""


import random

from maasserver.components import (
    discard_persistent_error,
    get_persistent_errors,
    register_persistent_error,
)
from maasserver.enum import COMPONENT
from maasserver.models import Notification
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from provisioningserver.utils.enum import map_enum


def get_random_component():
    return random.choice(list(map_enum(COMPONENT).values()))


class PersistentErrorsUtilitiesTest(MAASServerTestCase):
    def test_register_persistent_error_registers_error(self):
        error_message = factory.make_string()
        component = get_random_component()
        register_persistent_error(component, error_message)
        self.assertEqual([error_message], get_persistent_errors())

    def test_register_persistent_error_stores_last_error(self):
        error_message = factory.make_string()
        error_message2 = factory.make_string()
        component = get_random_component()
        register_persistent_error(component, error_message)
        register_persistent_error(component, error_message2)
        self.assertEqual([error_message2], get_persistent_errors())

    def test_discard_persistent_error_discards_error(self):
        error_message = factory.make_string()
        component = get_random_component()
        register_persistent_error(component, error_message)
        discard_persistent_error(component)
        self.assertEqual([], get_persistent_errors())

    def test_discard_persistent_error_can_be_called_many_times(self):
        error_message = factory.make_string()
        component = get_random_component()
        register_persistent_error(component, error_message)
        discard_persistent_error(component)
        discard_persistent_error(component)
        self.assertEqual([], get_persistent_errors())

    def get_persistent_errors_returns_text_for_error_codes(self):
        errors, components = [], []
        for _ in range(3):
            error_message = factory.make_string()
            component = get_random_component()
            register_persistent_error(component, error_message)
            errors.append(error_message)
            components.append(component)
        self.assertEqual(errors, get_persistent_errors())

    def test_register_persistent_error_reuses_component_errors(self):
        """When registering a persistent error that already has an error
        recorded for that component, reuse the error instead of deleting and
        recreating it."""
        component = factory.make_name("component")
        error1 = factory.make_name("error")
        error2 = factory.make_name("error")
        register_persistent_error(component, error1)
        notification = Notification.objects.get(ident=component)
        self.assertEqual(notification.render(), error1)
        notification_id = notification.id
        register_persistent_error(component, error2)
        notification = Notification.objects.get(ident=component)
        # The message is updated.
        self.assertEqual(notification.render(), error2)
        # The same notification row is used.
        self.assertEqual(notification.id, notification_id)
