# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from django.shortcuts import get_object_or_404
from piston3.utils import rc

from maasserver.api.support import admin_method, operation, OperationsHandler
from maasserver.exceptions import MAASAPIForbidden, MAASAPIValidationError
from maasserver.forms.notification import NotificationForm
from maasserver.models.notification import Notification

# Notification fields exposed on the API.
DISPLAYED_NOTIFICATION_FIELDS = frozenset(
    (
        "id",
        "ident",
        "user",
        "users",
        "admins",
        "message",
        "context",
        "category",
        "dismissable",
    )
)


class NotificationsHandler(OperationsHandler):
    """Manage the collection of all the notifications in MAAS."""

    api_doc_section_name = "Notifications"
    update = delete = None

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("notifications_handler", [])

    def read(self, request):
        """@description-title List notifications
        @description List notifications relevant to the invoking user.

        Notifications that have been dismissed are *not* returned.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a list of
        notification objects.
        @success-example "success-json" [exkey=notifications-read] placeholder
        text
        """
        return Notification.objects.find_for_user(request.user).order_by("id")

    @admin_method
    def create(self, request):
        """@description-title Create a notification
        @description Create a new notification.

        This is available to admins *only*.

        Note: One of the ``user``, ``users`` or ``admins`` parameters must be
        set to True for the notification to be visible to anyone.

        @param (string) "message" [required=true] The message for this
        notification. May contain basic HTML, such as formatting. This string
        will be sanitised before display so that it doesn't break MAAS HTML.

        @param (string) "context" [required=false] Optional JSON context. The
        root object *must* be an object (i.e. a mapping). The values herein can
        be referenced by ``message`` with Python's "format" (not %) codes.

        @param (string) "category" [required=false] Choose from: ``error``,
        ``warning``, ``success``, or ``info``. Defaults to ``info``.

        @param (string) "ident" [required=false] Unique identifier for this
        notification.

        @param (string) "user" [required=false] User ID this notification is
        intended for. By default it will not be targeted to any individual
        user.

        @param (boolean) "users" [required=false] True to notify all users,
        defaults to false, i.e. not targeted to all users.

        @param (boolean) "admins" [required=false] True to notify all admins,
        defaults to false, i.e. not targeted to all admins.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a new
        notification object.
        @success-example "success-json" [exkey=notifications-create]
        placeholder text
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
        """@description-title Read a notification
        @description Read a notification with the given id.

        @param (int) "{id}" [required=true] The notification id.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the requested
        notification object.
        @success-example "success-json" [exkey=notifications-read-by-id]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested notification is not found.
        @error-example "not-found"
            No Notification matches the given query.
        """
        notification = get_object_or_404(Notification, id=id)
        if (
            notification.is_relevant_to(request.user)
            or request.user.is_superuser
        ):
            return notification
        else:
            raise MAASAPIForbidden()

    @admin_method
    def update(self, request, id):
        """@description-title Update a notification
        @description Update a notification with a given id.

        This is available to admins *only*.

        Note: One of the ``user``, ``users`` or ``admins`` parameters must be
        set to True for the notification to be visible to anyone.

        @param (int) "{id}" [required=true] The notification id.

        @param (string) "message" [required=true] The message for this
        notification. May contain basic HTML, such as formatting. This string
        will be sanitised before display so that it doesn't break MAAS HTML.

        @param (string) "context" [required=false] Optional JSON context. The
        root object *must* be an object (i.e. a mapping). The values herein can
        be referenced by ``message`` with Python's "format" (not %) codes.

        @param (string) "category" [required=false] Choose from: ``error``,
        ``warning``, ``success``, or ``info``. Defaults to ``info``.

        @param (string) "ident" [required=false] Unique identifier for this
        notification.

        @param (string) "user" [required=false] User ID this notification is
        intended for. By default it will not be targeted to any individual
        user.

        @param (boolean) "users" [required=false] True to notify all users,
        defaults to false, i.e. not targeted to all users.

        @param (boolean) "admins" [required=false] True to notify all admins,
        defaults to false, i.e. not targeted to all admins.

        @param (boolean) "dismissable" [required=false] True to allow users
        dimissing the notification. Defaults to true.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the updated
        notification object.
        @success-example "success-json" [exkey=notifications-update]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested notification is not found.
        @error-example "not-found"
            No Notification matches the given query.
        """
        notification = get_object_or_404(Notification, id=id)
        form = NotificationForm(data=request.data, instance=notification)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    @admin_method
    def delete(self, request, id):
        """@description-title Delete a notification
        @description Delete a notification with a given id.

        @param (int) "{id}" [required=true] The notification id.

        @success (http-status-code) "server-success" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested notification is not found.
        @error-example "not-found"
            No Notification matches the given query.
        """
        notification = get_object_or_404(Notification, id=id)
        notification.delete()
        return rc.DELETED

    @operation(idempotent=False)
    def dismiss(self, request, id):
        """@description-title Dismiss a notification
        @description Dismiss a notification with the given id.

        It is safe to call multiple times for the same notification.

        @param (int) "{id}" [required=true] The notification id.

        @success (http-status-code) "server-success" 200

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The notification is not relevant to the
        invoking user.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested notification is not found.
        @error-example "not-found"
            No Notification matches the given query.
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
        return ("notification_handler", (notification_id,))
