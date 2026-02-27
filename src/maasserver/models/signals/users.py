# Copyright 2017-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to user changes."""

from django.contrib.auth.models import User
from django.db.models.signals import post_delete, post_save, pre_delete

from maasserver.models import Event
from maasserver.sqlalchemy import service_layer
from maasserver.utils.signals import SignalsManager
from maasservicelayer.builders.openfga_tuple import OpenFGATupleBuilder

signals = SignalsManager()


USER_CLASSES = [User]


def pre_delete_set_event_username(sender, instance, **kwargs):
    """Set username for events that reference user being deleted."""
    for event in Event.objects.filter(user_id=instance.id).all():
        event.username = instance.username
        event.save()


def post_created_user(sender, instance, created, **kwargs):
    if created:
        # Guarantee backwards compatibility and assign users to pre-defined groups (users/administrators)
        service_layer.services.openfga_tuples.create(
            OpenFGATupleBuilder.build_user_member_group(
                instance.id,
                "administrators" if instance.is_superuser else "users",
            )
        )


def post_delete_user(sender, instance, **kwargs):
    service_layer.services.openfga_tuples.delete_user(instance.id)


for klass in USER_CLASSES:
    signals.watch(pre_delete, pre_delete_set_event_username, sender=klass)

signals.watch(post_save, post_created_user, sender=User)
signals.watch(post_delete, post_delete_user, sender=User)

# Enable all signals by default.
signals.enable()
