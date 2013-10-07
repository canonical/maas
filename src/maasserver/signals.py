# Copyright 2012 Canonical Ltd.  This software is licensed under the
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


def connect_to_field_change(callback, model, field_name, delete=False):
    """Call the provided callback when a field is modified on a model.

    The provided `callback` method will be called when the value of the field
    named `fieldname` of an object of type `model` is changed.

    The signature of the callback method should be the following:

    >>> def callback(instance, old_value, deleted):
        ...
        pass

    Where `instance` is the object which has just being saved to the
    database, `old_value` is the old value of the field (different from the
    value of the field in `instance`) and `deleted` indicates whether or not
    the callback was called because the object was deleted.

    :param callback: The callback function.
    :type callback: callable
    :param model: Specifies a particular sender to receive signals from.
    :type model: class
    :param field_name: Name of the field to monitor.
    :type field_name: unicode
    :param delete: Should the deletion of an object be considered a change
        in the field?
    :type delete: bool
    """
    last_seen_flag = '_field_last_seen_value_%s' % field_name
    delta_flag = '_field_delta_%s' % field_name

    # Record the original value of the field we're interested in.
    def post_init_callback(sender, instance, **kwargs):
        original_value = getattr(instance, field_name)
        setattr(instance, last_seen_flag, original_value)
    post_init.connect(post_init_callback, sender=model, weak=False)

    # Set 'delta_flag' with the new and the old value of the field.
    def record_delta_flag(sender, instance, **kwargs):
        original_value = getattr(instance, last_seen_flag)
        new_value = getattr(instance, field_name)
        setattr(instance, delta_flag, (new_value, original_value))
    pre_save.connect(record_delta_flag, sender=model, weak=False)

    # Call the `callback` if the field has changed.
    def post_save_callback(sender, instance, created, **kwargs):
        (new_value, original_value) = getattr(instance, delta_flag)
        # Call the callback method is the field has changed.
        if original_value != new_value:
            callback(instance, original_value, deleted=False)
        setattr(instance, last_seen_flag, new_value)

    if delete:
        pre_delete.connect(record_delta_flag, sender=model, weak=False)

        def post_delete_callback(sender, instance, **kwargs):
            (new_value, original_value) = getattr(instance, delta_flag)
            callback(instance, original_value, deleted=True)

        post_delete.connect(post_delete_callback, sender=model, weak=False)

    post_save.connect(post_save_callback, sender=model, weak=False)
