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
        ...
        pass

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
    """
    combined_fields_name = '__'.join(fields)
    last_seen_flag = '_fields_last_seen_values__%s' % combined_fields_name
    delta_flag = '_fields_delta__%s' % combined_fields_name

    def snapshot_values(instance):
        """Obtain the tuple of `fields` values for `instance`."""
        return tuple(
            getattr(instance, field_name)
            for field_name in fields
            )

    # Record the original values of the fields we're interested in.
    def post_init_callback(sender, instance, **kwargs):
        original_values = snapshot_values(instance)
        setattr(instance, last_seen_flag, original_values)
    post_init.connect(post_init_callback, sender=model, weak=False)

    # Set 'delta_flag' to hold the fields' old and new values.
    def record_delta_flag(sender, instance, **kwargs):
        original_values = getattr(instance, last_seen_flag)
        new_values = snapshot_values(instance)
        setattr(instance, delta_flag, (new_values, original_values))
    pre_save.connect(record_delta_flag, sender=model, weak=False)

    # Call the `callback` if the field has changed.
    def post_save_callback(sender, instance, created, **kwargs):
        (new_values, original_values) = getattr(instance, delta_flag)
        # Call the callback method is the field has changed.
        if original_values != new_values:
            callback(instance, original_values, deleted=False)
        setattr(instance, last_seen_flag, new_values)

    if delete:
        pre_delete.connect(record_delta_flag, sender=model, weak=False)

        def post_delete_callback(sender, instance, **kwargs):
            (new_values, original_values) = getattr(instance, delta_flag)
            callback(instance, original_values, deleted=True)

        post_delete.connect(post_delete_callback, sender=model, weak=False)

    post_save.connect(post_save_callback, sender=model, weak=False)
