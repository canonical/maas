# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for signals helpers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maasserver.signals import connect_to_field_change
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestModelTestCase
from maasserver.tests.models import FieldChangeTestModel
from maastesting.fakemethod import FakeMethod


class ConnectToFieldChangeTest(TestModelTestCase):
    """Testing for the method `connect_to_field_change`."""

    app = 'maasserver.tests'

    def test_connect_to_field_change_calls_callback(self):
        callback = FakeMethod()
        connect_to_field_change(callback, FieldChangeTestModel, 'name1')
        old_name1_value = factory.getRandomString()
        obj = FieldChangeTestModel(name1=old_name1_value)
        obj.save()
        obj.name1 = factory.getRandomString()
        obj.save()
        self.assertEqual(
            (1, [(obj, old_name1_value)]),
            (callback.call_count, callback.extract_args()))

    def test_connect_to_field_change_calls_callback_for_each_save(self):
        callback = FakeMethod()
        connect_to_field_change(callback, FieldChangeTestModel, 'name1')
        old_name1_value = factory.getRandomString()
        obj = FieldChangeTestModel(name1=old_name1_value)
        obj.save()
        obj.name1 = factory.getRandomString()
        obj.save()
        obj.name1 = factory.getRandomString()
        obj.save()
        self.assertEqual(2, callback.call_count)

    def test_connect_to_field_change_calls_callback_for_each_real_save(self):
        callback = FakeMethod()
        connect_to_field_change(callback, FieldChangeTestModel, 'name1')
        old_name1_value = factory.getRandomString()
        obj = FieldChangeTestModel(name1=old_name1_value)
        obj.save()
        obj.name1 = factory.getRandomString()
        obj.save()
        obj.save()
        self.assertEqual(1, callback.call_count)

    def test_connect_to_field_change_calls_multiple_callbacks(self):
        callback1 = FakeMethod()
        connect_to_field_change(callback1, FieldChangeTestModel, 'name1')
        callback2 = FakeMethod()
        connect_to_field_change(callback2, FieldChangeTestModel, 'name1')
        old_name1_value = factory.getRandomString()
        obj = FieldChangeTestModel(name1=old_name1_value)
        obj.save()
        obj.name1 = factory.getRandomString()
        obj.save()
        self.assertEqual((1, 1), (callback1.call_count, callback2.call_count))

    def test_connect_to_field_change_ignores_changes_to_other_fields(self):
        obj = FieldChangeTestModel(name2=factory.getRandomString())
        obj.save()
        callback = FakeMethod()
        connect_to_field_change(callback, FieldChangeTestModel, 'name1')
        obj.name2 = factory.getRandomString()
        obj.save()
        self.assertEqual(0, callback.call_count)

    def test_connect_to_field_change_ignores_object_creation(self):
        callback = FakeMethod()
        connect_to_field_change(callback, FieldChangeTestModel, 'name1')
        obj = FieldChangeTestModel(name1=factory.getRandomString())
        obj.save()
        self.assertEqual(0, callback.call_count)
