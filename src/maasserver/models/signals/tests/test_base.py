# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for signals helpers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.models.signals.base import connect_to_field_change
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.tests.models import FieldChangeTestModel
from maastesting.djangotestcase import TestModelMixin
from maastesting.matchers import (
    IsCallable,
    MockCallsMatch,
)
from mock import (
    call,
    Mock,
)


class ConnectToFieldChangeTest(TestModelMixin, MAASServerTestCase):
    """Testing for the method `connect_to_field_change`."""

    app = 'maasserver.tests'

    def connect(self, callback, fields, delete=False):
        connect, disconnect = connect_to_field_change(
            callback, FieldChangeTestModel, fields, delete=delete)
        self.addCleanup(disconnect)
        return connect, disconnect

    def test_connect_to_field_change_calls_callback(self):
        callback = Mock()
        self.connect(callback, ['name1'])
        old_name1_value = factory.make_string()
        obj = FieldChangeTestModel(name1=old_name1_value)
        obj.save()
        obj.name1 = factory.make_string()
        obj.save()
        self.assertEqual(
            [call(obj, (old_name1_value,), deleted=False)],
            callback.mock_calls)

    def test_connect_to_field_change_returns_two_functions(self):
        callback = Mock()
        connect, disconnect = self.connect(callback, ['name1'])
        self.assertThat(connect, IsCallable())
        self.assertThat(disconnect, IsCallable())

    def test_returned_function_connect_and_disconnect(self):
        callback = Mock()
        connect, disconnect = self.connect(callback, ['name1'])

        obj = FieldChangeTestModel()
        obj.save()

        obj.name1 = "one"
        obj.save()
        expected_one = call(obj, ("",), deleted=False)
        # The callback has been called once, for name1="one".
        self.assertThat(callback, MockCallsMatch(expected_one))

        # Disconnect and `callback` is not called any more.
        disconnect()
        obj.name1 = "two"
        obj.save()
        # The callback has still only been called once.
        self.assertThat(callback, MockCallsMatch(expected_one))

        # Reconnect and `callback` is called again.
        connect()
        obj.name1 = "three"
        obj.save()
        expected_three = call(obj, ("one",), deleted=False)
        # The callback has been called twice, once for the change to "one" and
        # then for the change to "three". The delta is from "one" to "three"
        # because no snapshots were taken when disconnected.
        self.assertThat(callback, MockCallsMatch(expected_one, expected_three))

    def test_connect_to_field_change_calls_callback_for_each_save(self):
        callback = Mock()
        self.connect(callback, ['name1'])
        old_name1_value = factory.make_string()
        obj = FieldChangeTestModel(name1=old_name1_value)
        obj.save()
        obj.name1 = factory.make_string()
        obj.save()
        obj.name1 = factory.make_string()
        obj.save()
        self.assertEqual(2, callback.call_count)

    def test_connect_to_field_change_calls_callback_for_each_real_save(self):
        callback = Mock()
        self.connect(callback, ['name1'])
        old_name1_value = factory.make_string()
        obj = FieldChangeTestModel(name1=old_name1_value)
        obj.save()
        obj.name1 = factory.make_string()
        obj.save()
        obj.save()
        self.assertEqual(1, callback.call_count)

    def test_connect_to_field_change_calls_multiple_callbacks(self):
        callback1 = Mock()
        self.connect(callback1, ['name1'])
        callback2 = Mock()
        self.connect(callback2, ['name1'])
        old_name1_value = factory.make_string()
        obj = FieldChangeTestModel(name1=old_name1_value)
        obj.save()
        obj.name1 = factory.make_string()
        obj.save()
        self.assertEqual((1, 1), (callback1.call_count, callback2.call_count))

    def test_connect_to_field_change_ignores_changes_to_other_fields(self):
        callback = Mock()
        self.connect(callback, ['name1'])
        obj = FieldChangeTestModel(name2=factory.make_string())
        obj.save()
        obj.name2 = factory.make_string()
        obj.save()
        self.assertEqual(0, callback.call_count)

    def test_connect_to_field_change_ignores_object_creation(self):
        callback = Mock()
        self.connect(callback, ['name1'])
        obj = FieldChangeTestModel(name1=factory.make_string())
        obj.save()
        self.assertEqual(0, callback.call_count)

    def test_connect_to_field_change_ignores_deletion_by_default(self):
        obj = FieldChangeTestModel(name2=factory.make_string())
        obj.save()
        callback = Mock()
        self.connect(callback, ['name1'])
        obj.delete()
        self.assertEqual(0, callback.call_count)

    def test_connect_to_field_change_listens_to_deletion_if_delete_True(self):
        callback = Mock()
        self.connect(callback, ['name1'], delete=True)
        old_name1_value = factory.make_string()
        obj = FieldChangeTestModel(name1=old_name1_value)
        obj.save()
        obj.delete()
        self.assertEqual(
            [call(obj, (old_name1_value,), deleted=True)],
            callback.mock_calls)

    def test_connect_to_field_change_notices_change_in_any_given_field(self):
        callback = Mock()
        self.connect(callback, ['name1', 'name2'])
        name1 = factory.make_name('name1')
        old_name2_value = factory.make_name('old')
        obj = FieldChangeTestModel(name1=name1, name2=old_name2_value)
        obj.save()
        obj.name2 = factory.make_name('new')
        obj.save()
        self.assertEqual(
            [call(obj, (name1, old_name2_value), deleted=False)],
            callback.mock_calls)

    def test_connect_to_field_change_only_calls_once_per_object_change(self):
        callback = Mock()
        self.connect(callback, ['name1', 'name2'])
        old_name1_value = factory.make_name('old1')
        old_name2_value = factory.make_name('old2')
        obj = FieldChangeTestModel(
            name1=old_name1_value, name2=old_name2_value)
        obj.save()
        obj.name1 = factory.make_name('new1')
        obj.name2 = factory.make_name('new2')
        obj.save()
        self.assertEqual(
            [call(obj, (old_name1_value, old_name2_value), deleted=False)],
            callback.mock_calls)
