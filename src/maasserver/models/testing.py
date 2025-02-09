# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing helpers for ORM models and their supporting code."""

import fixtures


class SignalDisconnected(fixtures.Fixture):  # DEPRECATED
    """Disconnect a receiver from the given signal.

    :deprecated: Use the managers in `m.models.signals` instead.
    """

    def __init__(
        self, signal, receiver, sender=None, weak=True, dispatch_uid=None
    ):
        super().__init__()
        self.signal = signal
        self.receiver = receiver
        self.sender = sender
        self.weak = weak
        self.dispatch_uid = dispatch_uid

    def setUp(self):
        super().setUp()
        self.addCleanup(
            self.signal.connect,
            receiver=self.receiver,
            sender=self.sender,
            weak=self.weak,
            dispatch_uid=self.dispatch_uid,
        )
        self.signal.disconnect(
            receiver=self.receiver,
            sender=self.sender,
            dispatch_uid=self.dispatch_uid,
        )


class SignalsDisconnected(fixtures.Fixture):  # DEPRECATED
    """Disconnect all receivers of the given signals.

    This is a fixture version of `NoReceivers`.

    :deprecated: Use the managers in `m.models.signals` instead.
    """

    def __init__(self, *signals):
        super().__init__()
        self.signals = signals

    def setUp(self):
        super().setUp()

        def restore(signal, receivers):
            with signal.lock:
                signal.receivers = receivers

        for signal in self.signals:
            with signal.lock:
                self.addCleanup(restore, signal, signal.receivers)
                signal.receivers = []
