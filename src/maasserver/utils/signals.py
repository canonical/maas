# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Signal utilities."""

from collections import namedtuple
from functools import partial

from django.db.models.signals import (
    post_delete,
    post_init,
    post_save,
    pre_delete,
    pre_save,
)

from maasserver.models import Config


def connect_to_field_change(callback, model, fields, delete=False):
    """Call `callback` when any of `fields` on `model` are modified.

    The triggering event is when a model object of the given type is either
    saved to the database with any of the given fields having a different
    value than it had originally; or, optionally, a model object of the given
    type is deleted.  In either case, no matter how many of the fields may
    have been changed, the callback is invoked exactly once.

    The signature of the callback method should be the following:

    >>> def callback(instance, old_values, deleted):
    ...     pass

    Where `instance` is the object which has just being saved to the
    database, `old_values` is a tuple of the original values for `fields`
    (in the same order as `fields`), and `deleted` indicates whether it was
    a deletion that triggered the callback.

    :param callback: The callback function.
    :type callback: callable
    :param model: Specifies a particular sender to receive signals from.
    :type model: class
    :param fields: Names of the fields to monitor.
    :type fields: iterable of unicode
    :param delete: Should the deletion of an object be considered a change
        in the field?
    :type delete: bool

    :return: A ``(connect, disconnect)`` tuple, where ``connect`` and
        ``disconnect`` are no-argument functions that connect and disconnect
        fields changes respectively.
    """
    # Capture the fields in case an iterator was passed.
    fields = tuple(fields)

    combined_fields_name = "__".join(fields)
    last_seen_flag = "_fields_last_seen_values__%s" % combined_fields_name
    delta_flag = "_fields_delta__%s" % combined_fields_name

    def snapshot_values(instance):
        """Obtain the tuple of `fields` values for `instance`."""
        return tuple(getattr(instance, field_name) for field_name in fields)

    # Set 'last_seen_flag' to hold the field' current values.
    def record_last_seen_flag(sender, instance, **kwargs):
        original_values = snapshot_values(instance)
        setattr(instance, last_seen_flag, original_values)

    # Set 'delta_flag' to hold the fields' old and new values.
    def record_delta_flag(sender, instance, **kwargs):
        original_values = getattr(instance, last_seen_flag)
        new_values = snapshot_values(instance)
        setattr(instance, delta_flag, (new_values, original_values))

    # Call the `callback` if any field has changed.
    def post_save_callback(sender, instance, created, **kwargs):
        (new_values, original_values) = getattr(instance, delta_flag)
        # Call the callback method is the field has changed.
        if original_values != new_values:
            callback(instance, original_values, deleted=False)
        setattr(instance, last_seen_flag, new_values)

    # Assemble the relevant signals and their handlers.
    signals = (
        (post_init, record_last_seen_flag),
        (pre_save, record_delta_flag),
        (post_save, post_save_callback),
    )

    if delete:
        # Call the `callback` if the instance is being deleted.
        def post_delete_callback(sender, instance, **kwargs):
            (new_values, original_values) = getattr(instance, delta_flag)
            callback(instance, original_values, deleted=True)

        signals += (
            (pre_delete, record_delta_flag),
            (post_delete, post_delete_callback),
        )

    def connect():
        for signal, handler in signals:
            signal.connect(handler, sender=model, weak=False)

    def disconnect():
        for signal, handler in signals:
            signal.disconnect(handler, sender=model)

    connect.__doc__ = "Connect to {} for changes in {}.".format(
        model.__name__,
        " or ".join(fields),
    )
    disconnect.__doc__ = "Disconnect from {} for changes in ({}).".format(
        model.__name__,
        " or ".join(fields),
    )

    return connect, disconnect


Signal = namedtuple("Signal", ("connect", "disconnect"))


class SignalsManager:
    """A convenience, to help manage signals connections within MAAS.

    It's a convenient way to wire up signals, but it's also useful to help
    with testing, because you can disable and re-enable multiple signals in
    one go.
    """

    def __init__(self):
        super().__init__()
        self._signals = set()
        self._signals_connected = set()
        self._signals_disconnected = set()
        self._enabled = None

    def watch_fields(self, cb, model, fields, delete=False):
        """Watch the given model fields for changes.

        See `connect_to_field_change` for details.

        :param cb: The function to call when a field changes.
        :type cb: callable
        :param model: The Django model object whose fields are of interest.
        :type model: Model class
        :param fields: Names of the fields to monitor.
        :type fields: Iterable of attribute names.
        :param delete: If true, call `cb` when an instance of `model` is
            deleted too. By default this is false.
        :type delete: bool
        """
        return self.add(
            Signal(*connect_to_field_change(cb, model, fields, delete))
        )

    def watch_config(self, cb, name):
        """Watch a configuration item for changes.

        :param cb: The function to call when a configuration item changes.
        :type cb: callable
        :param name: The name of the configuration item to watch.
        :type name: unicode
        """
        return self.add(
            Signal(
                partial(Config.objects.config_changed_connect, name, cb),
                partial(Config.objects.config_changed_disconnect, name, cb),
            )
        )

    def watch(self, sig, cb, sender=None, weak=True, dispatch_uid=None):
        """Watch the given model for changes.

        This is a thin shim around Django's signal management code. See
        Django's documentation on signals at https://docs.djangoproject.com/.
        """
        return self.add(
            Signal(
                partial(
                    sig.connect,
                    cb,
                    sender=sender,
                    weak=weak,
                    dispatch_uid=dispatch_uid,
                ),
                partial(
                    sig.disconnect,
                    cb,
                    sender=sender,
                    dispatch_uid=dispatch_uid,
                ),
            )
        )

    def add(self, signal):
        """Manage the given signal.

        If this manager is enabled, enable the signal, and vice-versa. This is
        used by the ``watch_*`` methods.

        :type signal: `Signal`.
        """
        self._signals.add(signal)
        if self._enabled is True:
            self.enable()
        elif self._enabled is False:
            self.disable()
        else:
            pass  # Do nothing.
        return signal

    def remove(self, signal):
        """Stop managing the given signal.

        No attempt to disable the signal is made before it is released from
        management.

        :type signal: `Signal`.
        """
        self._signals.discard(signal)
        self._signals_connected.discard(signal)
        self._signals_disconnected.discard(signal)

    def enable(self):
        """Enable/connect all the signals under management."""
        self._enabled = True
        for signal in self._signals:
            if signal not in self._signals_connected:
                signal.connect()
                self._signals_connected.add(signal)
            self._signals_disconnected.discard(signal)

    def disable(self):
        """Disable/disconnect all the signals under management."""
        self._enabled = False
        for signal in self._signals:
            if signal not in self._signals_disconnected:
                signal.disconnect()
                self._signals_disconnected.add(signal)
            self._signals_connected.discard(signal)

    @property
    def enabled(self):
        """Are the managed signals enabled/connected?"""
        return bool(self._enabled)
