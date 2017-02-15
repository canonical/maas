# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

__all__ = [
    "NotificationHandler",
    "NotificationsHandler",
]

from django.shortcuts import get_object_or_404
from maasserver.api.support import (
    admin_method,
    operation,
    OperationsHandler,
)
from maasserver.exceptions import (
    MAASAPIForbidden,
    MAASAPIValidationError,
)
from maasserver.forms.notification import NotificationForm
from maasserver.models.notification import Notification
from piston3.utils import rc

# Notification fields exposed on the API.
DISPLAYED_NOTIFICATION_FIELDS = frozenset((
    'id',
    'ident',
    'user',
    'users',
    'admins',
    'message',
    'context',
    'category',
))


class NotificationsHandler(OperationsHandler):
    """Manage the collection of all the notifications in MAAS."""

    api_doc_section_name = "Notifications"
    update = delete = None

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('notifications_handler', [])

    def read(self, request):
        """List notifications relevant to the invoking user.

        Notifications that have been dismissed are *not* returned.
        """
        return Notification.objects.find_for_user(request.user).order_by('id')

    @admin_method
    def create(self, request):
        """Create a notification.

        This is available to admins *only*.

        :param message: The message for this notification. May contain basic
            HTML; this will be sanitised before display.
        :param context: Optional JSON context. The root object *must* be an
            object (i.e. a mapping). The values herein can be referenced by
            `message` with Python's "format" (not %) codes.
        :param category: Optional category. Choose from: error, warning,
            success, or info. Defaults to info.

        :param ident: Optional unique identifier for this notification.
        :param user: Optional user ID this notification is intended for. By
            default it will not be targeted to any individual user.
        :param users: Optional boolean, true to notify all users, defaults to
            false, i.e. not targeted to all users.
        :param admins: Optional boolean, true to notify all admins, defaults to
            false, i.e. not targeted to all admins.

        Note: if neither user nor users nor admins is set, the notification
        will not be seen by anyone.
        """
        form = NotificationForm(data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)


class NotificationHandler(OperationsHandler):
    """Manage an individual notification."""

    api_doc_section_name = "Notification"

    create = None
    model = Notification
    fields = DISPLAYED_NOTIFICATION_FIELDS

    def read(self, request, id):
        """Read a specific notification."""
        notification = get_object_or_404(Notification, id=id)
        if notification.is_relevant_to(request.user):
            return notification
        elif request.user.is_superuser:
            return notification
        else:
            raise MAASAPIForbidden()

    @admin_method
    def update(self, request, id):
        """Update a specific notification.

        See `NotificationsHandler.create` for field information.
        """
        notification = get_object_or_404(Notification, id=id)
        form = NotificationForm(
            data=request.data, instance=notification)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    @admin_method
    def delete(self, request, id):
        """Delete a specific notification."""
        notification = get_object_or_404(Notification, id=id)
        notification.delete()
        return rc.DELETED

    @operation(idempotent=False)
    def dismiss(self, request, id):
        """Dismiss a specific notification.

        Returns HTTP 403 FORBIDDEN if this notification is not relevant
        (targeted) to the invoking user.

        It is safe to call multiple times for the same notification.
        """
        notification = get_object_or_404(Notification, id=id)
        if notification.is_relevant_to(request.user):
            notification.dismiss(request.user)
        else:
            raise MAASAPIForbidden()

    @classmethod
    def resource_uri(cls, notification=None):
        notification_id = "id"
        if notification is not None:
            notification_id = notification.id
        return ('notification_handler', (notification_id,))
