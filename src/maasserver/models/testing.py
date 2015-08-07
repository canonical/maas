# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing helpers for ORM models and their supporting code."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "SignalDisconnected",
    "SignalsDisconnected",
    "UpdateBootSourceCacheDisconnected",
]

from django.db.models.signals import post_save
import fixtures
from maasserver.models.bootsource import (
    BootSource,
    update_boot_source_cache,
)


class SignalDisconnected(fixtures.Fixture):
    """Disconnect a receiver from the given signal."""

    def __init__(
            self, signal, receiver, sender=None, weak=True,
            dispatch_uid=None):
        super(SignalDisconnected, self).__init__()
        self.signal = signal
        self.receiver = receiver
        self.sender = sender
        self.weak = weak
        self.dispatch_uid = dispatch_uid

    def setUp(self):
        super(SignalDisconnected, self).setUp()
        self.addCleanup(
            self.signal.connect, receiver=self.receiver, sender=self.sender,
            weak=self.weak, dispatch_uid=self.dispatch_uid)
        self.signal.disconnect(
            receiver=self.receiver, sender=self.sender, weak=self.weak,
            dispatch_uid=self.dispatch_uid)


class SignalsDisconnected(fixtures.Fixture):
    """Disconnect all receivers of the given signals.

    This is a fixture version of `NoReceivers`.
    """

    def __init__(self, *signals):
        super(SignalsDisconnected, self).__init__()
        self.signals = signals

    def setUp(self):
        super(SignalsDisconnected, self).setUp()

        def restore(signal, receivers):
            with signal.lock:
                signal.receivers = receivers

        for signal in self.signals:
            with signal.lock:
                self.addCleanup(restore, signal, signal.receivers)
                signal.receivers = []


class UpdateBootSourceCacheDisconnected(SignalDisconnected):

    def __init__(self, *signals):
        super(UpdateBootSourceCacheDisconnected, self).__init__(
            post_save, update_boot_source_cache, BootSource)
