# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAAS components notifications.

This is a legacy compatibility shim, to use the new notifications feature to
display the old components messages. In time this will go away, but it's
simple enough that there's no rush until it doesn't actually do what we want
it to do.
"""

__all__ = [
    "discard_persistent_error",
    "get_persistent_error",
    "get_persistent_errors",
    "register_persistent_error",
]

from maasserver.enum import COMPONENT
from maasserver.models import Notification
from maasserver.utils.orm import transactional
from provisioningserver.utils.enum import map_enum


@transactional
def discard_persistent_error(component):
    """Drop the persistent error for `component`.

    :param component: An enum value of :class:`COMPONENT`.
    """
    Notification.objects.filter(ident=component).delete()


@transactional
def register_persistent_error(component, error_message, dismissable=True):
    """Register a persistent error for `component`.

    :param component: An enum value of :class:`COMPONENT`.
    :param error_message: Human-readable error text.
    """
    try:
        notification = Notification.objects.get(ident=component)
    except Notification.DoesNotExist:
        notification = Notification.objects.create_error_for_admins(
            error_message,
            ident=component,
            dismissable=dismissable,
        )
    else:
        if notification.message != error_message:
            notification.message = error_message
            notification.save()


def get_persistent_error(component):
    """Return persistent error for `component`, or None."""
    try:
        notification = Notification.objects.get(ident=component)
    except Notification.DoesNotExist:
        return None
    else:
        return notification.render()


def get_persistent_errors():
    """Return list of current persistent error messages."""
    components = map_enum(COMPONENT).values()
    return sorted(
        notification.render()
        for notification in Notification.objects.filter(ident__in=components)
    )
