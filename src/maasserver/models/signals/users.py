# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to user changes."""

from django.contrib.auth.models import User
from django.db.models.signals import pre_delete

from maasserver.utils.signals import SignalsManager

signals = SignalsManager()


USER_CLASSES = [User]


def pre_delete_set_event_username(sender, instance, **kwargs):
    """Set username for events that reference user being deleted."""
    for event in instance.event_set.all():
        event.username = instance.username
        event.save()


for klass in USER_CLASSES:
    signals.watch(pre_delete, pre_delete_set_event_username, sender=klass)


# Enable all signals by default.
signals.enable()
