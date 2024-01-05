# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import random
from unittest.mock import call, Mock, sentinel

from twisted.python.reflect import namedObject

from maasserver.models import Config
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASLegacyTransactionServerTestCase,
    MAASServerTestCase,
)
from maasserver.tests.models import FieldChangeTestModel
from maasserver.utils import signals as signals_module
from maasserver.utils.signals import (
    connect_to_field_change,
    Signal,
    SignalsManager,
)

django_signal_names = [
    "pre_init",
    "post_init",
    "pre_save",
    "post_save",
    "pre_delete",
    "post_delete",
    "m2m_changed",
]


def pick_django_signal():
    return namedObject(
        "django.db.models.signals." + random.choice(django_signal_names)
    )


class TestConnectToFieldChange(MAASLegacyTransactionServerTestCase):
    apps = ["maasserver.tests"]

    def connect(self, callback, fields, delete=False):
        connect, disconnect = connect_to_field_change(
            callback, FieldChangeTestModel, fields, delete=delete
        )
        self.addCleanup(disconnect)
        connect()  # No longer done by default.
        return connect, disconnect

    def test_connect_to_field_change_calls_callback(self):
        callback = Mock()
        self.connect(callback, ["name1"])
        old_name1_value = factory.make_string()
        obj = FieldChangeTestModel(name1=old_name1_value)
        obj.save()
        obj.name1 = factory.make_string()
        obj.save()
        self.assertEqual(
            [call(obj, (old_name1_value,), deleted=False)], callback.mock_calls
        )

    def test_connect_to_field_change_returns_two_functions(self):
        callback = Mock()
        connect, disconnect = self.connect(callback, ["name1"])
        self.assertTrue(callable(connect))
        self.assertTrue(callable(disconnect))

    def test_returned_function_connect_and_disconnect(self):
        callback = Mock()
        connect, disconnect = self.connect(callback, ["name1"])

        obj = FieldChangeTestModel()
        obj.save()

        obj.name1 = "one"
        obj.save()
        expected_one = call(obj, ("",), deleted=False)
        # The callback has been called once, for name1="one".
        callback.assert_has_calls((expected_one,))

        # Disconnect and `callback` is not called any more.
        disconnect()
        obj.name1 = "two"
        obj.save()
        # The callback has still only been called once.
        callback.assert_has_calls((expected_one,))

        # Reconnect and `callback` is called again.
        connect()
        obj.name1 = "three"
        obj.save()
        expected_three = call(obj, ("one",), deleted=False)
        # The callback has been called twice, once for the change to "one" and
        # then for the change to "three". The delta is from "one" to "three"
        # because no snapshots were taken when disconnected.
        callback.assert_has_calls((expected_one, expected_three))

    def test_connect_to_field_change_calls_callback_for_each_save(self):
        callback = Mock()
        self.connect(callback, ["name1"])
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
        self.connect(callback, ["name1"])
        old_name1_value = factory.make_string()
        obj = FieldChangeTestModel(name1=old_name1_value)
        obj.save()
        obj.name1 = factory.make_string()
        obj.save()
        obj.save()
        self.assertEqual(1, callback.call_count)

    def test_connect_to_field_change_calls_multiple_callbacks(self):
        callback1 = Mock()
        self.connect(callback1, ["name1"])
        callback2 = Mock()
        self.connect(callback2, ["name1"])
        old_name1_value = factory.make_string()
        obj = FieldChangeTestModel(name1=old_name1_value)
        obj.save()
        obj.name1 = factory.make_string()
        obj.save()
        self.assertEqual((1, 1), (callback1.call_count, callback2.call_count))

    def test_connect_to_field_change_ignores_changes_to_other_fields(self):
        callback = Mock()
        self.connect(callback, ["name1"])
        obj = FieldChangeTestModel(name2=factory.make_string())
        obj.save()
        obj.name2 = factory.make_string()
        obj.save()
        self.assertEqual(0, callback.call_count)

    def test_connect_to_field_change_ignores_object_creation(self):
        callback = Mock()
        self.connect(callback, ["name1"])
        obj = FieldChangeTestModel(name1=factory.make_string())
        obj.save()
        self.assertEqual(0, callback.call_count)

    def test_connect_to_field_change_ignores_deletion_by_default(self):
        obj = FieldChangeTestModel(name2=factory.make_string())
        obj.save()
        callback = Mock()
        self.connect(callback, ["name1"])
        obj.delete()
        self.assertEqual(0, callback.call_count)

    def test_connect_to_field_change_listens_to_deletion_if_delete_True(self):
        callback = Mock()
        self.connect(callback, ["name1"], delete=True)
        old_name1_value = factory.make_string()
        obj = FieldChangeTestModel(name1=old_name1_value)
        obj.save()
        obj.delete()
        self.assertEqual(
            [call(obj, (old_name1_value,), deleted=True)], callback.mock_calls
        )

    def test_connect_to_field_change_notices_change_in_any_given_field(self):
        callback = Mock()
        self.connect(callback, ["name1", "name2"])
        name1 = factory.make_name("name1")
        old_name2_value = factory.make_name("old")
        obj = FieldChangeTestModel(name1=name1, name2=old_name2_value)
        obj.save()
        obj.name2 = factory.make_name("new")
        obj.save()
        self.assertEqual(
            [call(obj, (name1, old_name2_value), deleted=False)],
            callback.mock_calls,
        )

    def test_connect_to_field_change_only_calls_once_per_object_change(self):
        callback = Mock()
        self.connect(callback, ["name1", "name2"])
        old_name1_value = factory.make_name("old1")
        old_name2_value = factory.make_name("old2")
        obj = FieldChangeTestModel(
            name1=old_name1_value, name2=old_name2_value
        )
        obj.save()
        obj.name1 = factory.make_name("new1")
        obj.name2 = factory.make_name("new2")
        obj.save()
        self.assertEqual(
            [call(obj, (old_name1_value, old_name2_value), deleted=False)],
            callback.mock_calls,
        )


class TestSignalsManager(MAASServerTestCase):
    def test_can_watch_fields(self):
        connect_to_field_change = self.patch_autospec(
            signals_module, "connect_to_field_change"
        )
        connect_to_field_change.return_value = (
            sentinel.connect,
            sentinel.disconnect,
        )

        manager = SignalsManager()
        manager.watch_fields(
            sentinel.callback, sentinel.model, sentinel.fields, sentinel.delete
        )

        self.assertEqual(
            {Signal(sentinel.connect, sentinel.disconnect)},
            manager._signals,
        )
        connect_to_field_change.assert_called_once_with(
            sentinel.callback,
            sentinel.model,
            sentinel.fields,
            sentinel.delete,
        )

    def test_can_watch_config(self):
        def callback():
            pass

        config_name = factory.make_name("config")

        manager = SignalsManager()
        manager.watch_config(callback, config_name)

        self.assertEqual(len(manager._signals), 1)
        [signal] = manager._signals
        self.assertEqual(
            signal.connect.func, Config.objects.config_changed_connect
        )
        self.assertEqual(signal.connect.args, (config_name, callback))
        self.assertEqual(signal.connect.keywords, {})

        self.assertEqual(
            signal.disconnect.func, Config.objects.config_changed_disconnect
        )
        self.assertEqual(signal.disconnect.args, (config_name, callback))
        self.assertEqual(signal.disconnect.keywords, {})

    def test_can_watch_any_signal(self):
        django_signal = pick_django_signal()

        manager = SignalsManager()
        manager.watch(
            django_signal,
            sentinel.callback,
            sender=sentinel.sender,
            weak=sentinel.weak,
            dispatch_uid=sentinel.dispatch_uid,
        )

        self.assertEqual(len(manager._signals), 1)
        [signal] = manager._signals
        self.assertEqual(signal.connect.func, django_signal.connect)
        self.assertEqual(signal.connect.args, (sentinel.callback,))
        self.assertEqual(
            signal.connect.keywords,
            {
                "sender": sentinel.sender,
                "weak": sentinel.weak,
                "dispatch_uid": sentinel.dispatch_uid,
            },
        )
        self.assertEqual(signal.disconnect.func, django_signal.disconnect)
        self.assertEqual(signal.disconnect.args, (sentinel.callback,))
        self.assertEqual(
            signal.disconnect.keywords,
            {
                "sender": sentinel.sender,
                "dispatch_uid": sentinel.dispatch_uid,
            },
        )

    def make_Signal(self):
        return Signal(Mock(name="connect"), Mock(name="disconnect"))

    def test_add_adds_the_signal(self):
        manager = SignalsManager()
        signal = self.make_Signal()
        self.assertIs(manager.add(signal), signal)
        self.assertEqual({signal}, manager._signals)
        # The manager is in its "new" state, neither enabled nor disabled, so
        # the signal is not asked to connect or disconnect yet.
        signal.connect.assert_not_called()
        signal.disconnect.assert_not_called()
        signal.connect.assert_not_called()
        signal.disconnect.assert_not_called()

    def test_add_connects_signal_if_manager_is_enabled(self):
        manager = SignalsManager()
        manager.enable()
        signal = self.make_Signal()
        manager.add(signal)
        signal.connect.assert_called_once_with()
        signal.disconnect.assert_not_called()

    def test_add_disconnects_signal_if_manager_is_disabled(self):
        manager = SignalsManager()
        manager.disable()
        signal = self.make_Signal()
        manager.add(signal)
        signal.connect.assert_not_called()
        signal.disconnect.assert_called_once_with()

    def test_remove_removes_the_signal(self):
        manager = SignalsManager()
        signal = self.make_Signal()
        manager.add(signal)
        manager.remove(signal)
        self.assertEqual(len(manager._signals), 0)
        signal.connect.assert_not_called()
        signal.disconnect.assert_not_called()

    def test_enable_enables_all_signals(self):
        manager = SignalsManager()
        signals = [self.make_Signal(), self.make_Signal()]
        for signal in signals:
            manager.add(signal)
        manager.enable()
        for signal in signals:
            signal.connect.assert_called_once_with()
            signal.disconnect.assert_not_called()

    def test_disable_disables_all_signals(self):
        manager = SignalsManager()
        signals = [self.make_Signal(), self.make_Signal()]
        for signal in signals:
            manager.add(signal)
        manager.disable()
        for signal in signals:
            signal.connect.assert_not_called()
            signal.disconnect.assert_called_once_with()
