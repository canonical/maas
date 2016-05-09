# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test networks module."""

__all__ = [
    ]

from unittest.mock import sentinel

from maastesting.testcase import MAASTestCase
from provisioningserver import networks


class TestGetInterfacesDefinition(MAASTestCase):
    """Tests for `get_interfaces_definition`."""

    def test__sets_global_when_None(self):
        networks._current_definition = None
        patched_getter = self.patch(networks, "get_all_interfaces_definition")
        patched_getter.return_value = sentinel.definition
        expected_value, updated = networks.get_interfaces_definition()
        self.assertEquals(sentinel.definition, expected_value)
        self.assertEquals(sentinel.definition, networks._current_definition)
        self.assertTrue(updated)

    def test__sets_global_when_different(self):
        networks._current_definition = sentinel.old_definition
        patched_getter = self.patch(networks, "get_all_interfaces_definition")
        patched_getter.return_value = sentinel.definition
        expected_value, updated = networks.get_interfaces_definition()
        self.assertEquals(sentinel.definition, expected_value)
        self.assertEquals(sentinel.definition, networks._current_definition)
        self.assertTrue(updated)

    def test__returns_not_changed_if_same(self):
        networks._current_definition = sentinel.definition
        patched_getter = self.patch(networks, "get_all_interfaces_definition")
        patched_getter.return_value = sentinel.definition
        expected_value, updated = networks.get_interfaces_definition()
        self.assertEquals(sentinel.definition, expected_value)
        self.assertEquals(sentinel.definition, networks._current_definition)
        self.assertFalse(updated)


class TestClearCurrentInterfacesDefinition(MAASTestCase):
    """Tests for `clear_current_interfaces_definition`."""

    def test__sets_global_to_None(self):
        networks._current_definition = sentinel.old_definition
        networks.clear_current_interfaces_definition()
        self.assertIsNone(networks._current_definition)
