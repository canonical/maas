# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Signal utilities."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'connect_to_field_change',
    ]

from django.db.models.signals import (
    post_delete,
    post_init,
    post_save,
    pre_delete,
    pre_save,
    )


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
        fields changes respectively. ``connect`` has already been called when
        this function returns.
    """
    # Capture the fields in case an iterator was passed.
    fields = tuple(fields)

    combined_fields_name = '__'.join(fields)
    last_seen_flag = '_fields_last_seen_values__%s' % combined_fields_name
    delta_flag = '_fields_delta__%s' % combined_fields_name

    def snapshot_values(instance):
        """Obtain the tuple of `fields` values for `instance`."""
        return tuple(
            getattr(instance, field_name)
            for field_name in fields
            )

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
            signal.disconnect(handler, sender=model, weak=False)

    connect.__doc__ = "Connect to %s for changes in %s." % (
        model.__name__, " or ".join(fields))
    disconnect.__doc__ = "Disconnect from %s for changes in (%s)." % (
        model.__name__, " or ".join(fields))

    # The caller expects to be connected initially.
    connect()

    return connect, disconnect
