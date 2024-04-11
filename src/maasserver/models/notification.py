# Copyright 2015-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for a notification message."""


from functools import wraps

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models import (
    BooleanField,
    CASCADE,
    CharField,
    ForeignKey,
    JSONField,
    Manager,
    TextField,
)
from markupsafe import Markup

from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


def _create(method, category):
    """Return a wrapped `method` that passes `category` as first argument."""

    @wraps(method)
    def call_with_category(self, *args, **kwargs):
        return method(self, category, *args, **kwargs)

    return call_with_category


class NotificationNotDismissable(Exception):
    """The notification can't be dismissed."""

    def __init__(self):
        super().__init__("Notification is not dismissable")


class NotificationManager(Manager):
    """Manager for `Notification` class."""

    def _create_for_user(
        self,
        category,
        message,
        user,
        *,
        context=None,
        ident=None,
        dismissable=True,
    ):
        """Create a notification for a specific user."""
        if ident is not None:
            self.filter(ident=ident).update(ident=None)

        notification = self._create(
            category,
            user,
            False,
            False,
            ident,
            message,
            context,
            dismissable=dismissable,
        )
        notification.save()

        return notification

    create_error_for_user = _create(_create_for_user, "error")
    create_warning_for_user = _create(_create_for_user, "warning")
    create_success_for_user = _create(_create_for_user, "success")
    create_info_for_user = _create(_create_for_user, "info")

    def _create_for_users(
        self,
        category,
        message,
        *,
        context=None,
        ident=None,
        dismissable=True,
    ):
        """Create a notification for all users and admins."""
        if ident is not None:
            self.filter(ident=ident).update(ident=None)

        notification = self._create(
            category,
            None,
            True,
            True,
            ident,
            message,
            context,
            dismissable=dismissable,
        )
        notification.save()

        return notification

    create_error_for_users = _create(_create_for_users, "error")
    create_warning_for_users = _create(_create_for_users, "warning")
    create_success_for_users = _create(_create_for_users, "success")
    create_info_for_users = _create(_create_for_users, "info")

    def _create_for_admins(
        self,
        category,
        message,
        *,
        context=None,
        ident=None,
        dismissable=True,
    ):
        """Create a notification for all admins, but not users."""
        if ident is not None:
            self.filter(ident=ident).update(ident=None)

        notification = self._create(
            category,
            None,
            False,
            True,
            ident,
            message,
            context,
            dismissable,
        )
        notification.save()

        return notification

    create_error_for_admins = _create(_create_for_admins, "error")
    create_warning_for_admins = _create(_create_for_admins, "warning")
    create_success_for_admins = _create(_create_for_admins, "success")
    create_info_for_admins = _create(_create_for_admins, "info")

    def _create(
        self,
        category,
        user,
        users,
        admins,
        ident,
        message,
        context,
        dismissable,
    ):
        return self.model(
            category=category,
            ident=ident,
            message=message,
            user=user,
            users=users,
            admins=admins,
            context=({} if context is None else context),
            dismissable=dismissable,
        )

    def find_for_user(self, user):
        """Find notifications for the given user.

        :return: A `QuerySet` of `Notification` instances that haven't been
            dismissed by `user`.
        """
        if user is None:
            return Notification.objects.none()
        elif user.is_superuser:
            query = self._sql_find_ids_for_admins
        else:
            query = self._sql_find_ids_for_users
        # We want to return a QuerySet because things like the WebSocket
        # handler code wants to use order_by. This seems reasonable. However,
        # we can't do outer joins with Django so we have to use self.raw().
        # However #2, that returns a RawQuerySet which doesn't do order_by.
        # Nor can we do self.filter(id__in=self.raw(...)) to "legitimise" a
        # raw query. Nope, we have to actually fetch those IDs then issue
        # another query to get a QuerySet for a set of Notification rows.
        with connection.cursor() as cursor:
            cursor.execute(query, [user.id, user.id])
            ids = [nid for (nid,) in cursor.fetchall()]
        return self.filter(id__in=ids)

    _sql_find_ids_for_xxx = """\
    SELECT notification.id FROM maasserver_notification AS notification
    LEFT OUTER JOIN maasserver_notificationdismissal AS dismissal ON
      (dismissal.notification_id = notification.id AND dismissal.user_id = %%s)
    WHERE (notification.user_id = %%s OR %s) AND dismissal.id IS NULL
    ORDER BY notification.updated, notification.id
    """

    _sql_find_ids_for_users = _sql_find_ids_for_xxx % "notification.users"
    _sql_find_ids_for_admins = _sql_find_ids_for_xxx % "notification.admins"


class Notification(CleanSave, TimestampedModel):
    """A notification message.

    :ivar ident: Unique identifier for the notification. Not required but is
        used to make sure messages of the same type are not posted multiple
        times.

    :ivar user: Specific user who can see the message.
    :ivar users: If true, this message can be seen by all ordinary users.
    :ivar admins: If true, this message can be seen by all administrators.

    :ivar message: Message that is viewable by the user. This is used as a
        format-style template; see `context`.
    :ivar context: A dict (that can be serialised to JSON) that's used with
        `message`.
    :ivar category: The category of this notification. The "success" category
        is used to reinforce a positive action or event, giving good news. The
        meaning of the "warning" and "error" categories are fairly obvious.
        The "info" category might be used to reaffirm a small action, like "10
        partitions were created on machine foo".
    :ivar dismissable: Whether the notification can be dismissed.
    """

    objects = NotificationManager()

    ident = CharField(
        max_length=40, null=True, blank=True, default=None, unique=True
    )

    user = ForeignKey(
        User, null=True, blank=True, default=None, on_delete=CASCADE
    )
    users = BooleanField(null=False, blank=True, default=False)
    admins = BooleanField(null=False, blank=True, default=False)

    message = TextField(null=False, blank=False)
    context = JSONField(blank=True, default=dict)
    category = CharField(
        null=False,
        blank=True,
        default="info",
        max_length=10,
        choices=[
            ("error", "Error"),
            ("warning", "Warning"),
            ("success", "Success"),
            ("info", "Informational"),
        ],
    )
    dismissable = BooleanField(null=False, blank=True, default=True)

    def render(self):
        """Render this notification's message using its context.

        The message can contain HTML markup. Values from the context are
        escaped.
        """
        markup = Markup(self.message)
        markup = markup.format(**self.context)
        return str(markup)

    def is_relevant_to(self, user):
        """Is this notification relevant to the given user?"""
        return user is not None and (
            (self.user_id is not None and self.user_id == user.id)
            or (self.users and not user.is_superuser)
            or (self.admins and user.is_superuser)
        )

    def dismiss(self, user):
        """Dismiss this notification.

        :param user: The user dismissing this notification.
        """
        if not self.dismissable:
            raise NotificationNotDismissable()
        NotificationDismissal.objects.get_or_create(
            notification=self, user=user
        )

    def clean(self):
        super().clean()
        # Elementary cleaning that Django can't seem to do for us, mainly
        # because setting blank=False causes any number of problems.
        if self.ident == "":
            self.ident = None
        if self.category == "":
            self.category = "info"
        # The context must be a a dict (well, mapping, but we check for dict
        # because it will be converted to JSON later and a dict-like object
        # won't do). This could be done as a validator but, meh, I'm sick of
        # jumping through Django-hoops like a circus animal.
        if not isinstance(self.context, dict):
            raise ValidationError({"context": "Context is not a mapping."})
        # Finally, check that the notification can be rendered. No point in
        # doing any of this if we cannot relate the message.
        try:
            self.render()
        except Exception:
            raise ValidationError("Notification cannot be rendered.")

    def __repr__(self):
        username = "None" if self.user is None else repr(self.user.username)
        return "<Notification {} user={} users={!r} admins={!r} {!r}>".format(
            self.category.upper(),
            username,
            self.users,
            self.admins,
            self.render(),
        )


class NotificationDismissal(TimestampedModel):
    """A notification dismissal.

    :ivar notification: The notification which has been dismissed.
    :ivar user: The user that has dismissed the linked notification.
    """

    objects = Manager()

    notification = ForeignKey(
        Notification, null=False, blank=False, on_delete=CASCADE
    )
    user = ForeignKey(User, null=False, blank=False, on_delete=CASCADE)
