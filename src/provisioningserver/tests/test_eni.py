# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test eni module."""

__all__ = [
    ]

from maastesting.testcase import MAASTestCase
from mock import sentinel
from provisioningserver import eni


class TestGetInterfacesDefinition(MAASTestCase):
    """Tests for `get_interfaces_definition`."""

    def test__sets_global_when_None(self):
        eni._current_eni_definition = None
        patched_getter = self.patch(eni, "get_eni_interfaces_definition")
        patched_getter.return_value = sentinel.definition
        expected_value, updated = eni.get_interfaces_definition()
        self.assertEquals(sentinel.definition, expected_value)
        self.assertEquals(sentinel.definition, eni._current_eni_definition)
        self.assertTrue(updated)

    def test__sets_global_when_different(self):
        eni._current_eni_definition = sentinel.old_definition
        patched_getter = self.patch(eni, "get_eni_interfaces_definition")
        patched_getter.return_value = sentinel.definition
        expected_value, updated = eni.get_interfaces_definition()
        self.assertEquals(sentinel.definition, expected_value)
        self.assertEquals(sentinel.definition, eni._current_eni_definition)
        self.assertTrue(updated)

    def test__returns_not_changed_if_same(self):
        eni._current_eni_definition = sentinel.definition
        patched_getter = self.patch(eni, "get_eni_interfaces_definition")
        patched_getter.return_value = sentinel.definition
        expected_value, updated = eni.get_interfaces_definition()
        self.assertEquals(sentinel.definition, expected_value)
        self.assertEquals(sentinel.definition, eni._current_eni_definition)
        self.assertFalse(updated)


class TestClearCurrentInterfacesDefinition(MAASTestCase):
    """Tests for `clear_current_interfaces_definition`."""

    def test__sets_global_to_None(self):
        eni._current_eni_definition = sentinel.old_definition
        eni.clear_current_interfaces_definition()
        self.assertIsNone(eni._current_eni_definition)
