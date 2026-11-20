# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Gap-free tests for `maasserver.utils.signals`, split out of the legacy
`src/maasserver/utils/tests/test_signals.py`: the legacy
`TestConnectToFieldChange` class stays there in the region-legacy pytest
leg, while this class runs in the main pytest suite."""

import random
from unittest.mock import Mock, sentinel

from twisted.python.reflect import namedObject

from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils import signals as signals_module
from maasserver.utils.signals import Signal, SignalsManager

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
