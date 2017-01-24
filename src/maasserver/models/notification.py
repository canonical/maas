# Copyright 2015-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for a notification message."""

__all__ = [
    'Notification',
]

from django.contrib.auth.models import User
from django.db import connection
from django.db.models import (
    BooleanField,
    CharField,
    ForeignKey,
    Manager,
    Model,
    TextField,
)
from maasserver import DefaultMeta
from maasserver.fields import JSONObjectField
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


class NotificationManager(Manager):
    """Manager for `Notification` class."""

    def create_for_user(self, message, user, *, context=None, ident=None):
        """Create a notification for a specific user."""
        if ident is not None:
            self.filter(ident=ident).update(ident=None)

        notification = self._create(
            user, False, False, ident, message, context)
        notification.save()

        return notification

    def create_for_users(self, message, *, context=None, ident=None):
        """Create a notification for all users and admins."""
        if ident is not None:
            self.filter(ident=ident).update(ident=None)

        notification = self._create(
            None, True, True, ident, message, context)
        notification.save()

        return notification

    def create_for_admins(self, message, *, context=None, ident=None):
        """Create a notification for all admins, but not users."""
        if ident is not None:
            self.filter(ident=ident).update(ident=None)

        notification = self._create(
            None, False, True, ident, message, context)
        notification.save()

        return notification

    def _create(self, user, users, admins, ident, message, context):
        return self.model(
            ident=ident, user=user, users=users, admins=admins,
            message=message, context={} if context is None else context)

    def find_for_user(self, user):
        """Find notifications for the given user.

        :return: A `QuerySet` of `Notification` instances that haven't been
            dismissed by `user`.
        """
        if user.is_superuser:
            where = "notification.users OR notification.admins"
        else:
            where = "notification.users"
        # We want to return a QuerySet because things like the WebSocket
        # handler code wants to use order_by. This seems reasonable. However,
        # we can't do outer joins with Django so we have to use self.raw().
        # However #2, that returns a RawQuerySet which doesn't do order_by.
        # Nor can we do self.filter(id__in=self.raw(...)) to "legitimise" a
        # raw query. Nope, we have to actually fetch those IDs then issue
        # another query to get a QuerySet for a set of Notification rows.
        with connection.cursor() as cursor:
            find_ids = self._sql_find_ids_for_user % where
            cursor.execute(find_ids, [user.id, user.id])
            ids = [nid for (nid, ) in cursor.fetchall()]
        return self.filter(id__in=ids)

    _sql_find_ids_for_user = """\
    SELECT notification.id FROM maasserver_notification AS notification
    LEFT OUTER JOIN maasserver_notificationdismissal AS dismissal ON
      (dismissal.notification_id = notification.id AND dismissal.user_id = %%s)
    WHERE (notification.user_id = %%s OR %s) AND dismissal.id IS NULL
    ORDER BY notification.updated, notification.id
    """


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
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    objects = NotificationManager()

    # The ident column *is* unique, but uniqueness will be ensured using a
    # partial index in PostgreSQL. These cannot be expressed using Django. See
    # migrations for the SQL used to create this index.
    ident = CharField(max_length=40, null=True, blank=True)

    user = ForeignKey(User, null=True, blank=True)
    users = BooleanField(default=False)
    admins = BooleanField(default=False)

    message = TextField(null=False, blank=True)
    context = JSONObjectField(null=False, blank=True, default=dict)

    def render(self):
        """Render this notification's message using its context."""
        return self.message.format(**self.context)

    def is_relevant_to(self, user):
        """Is this notification relevant to the given user?"""
        return user is not None and (
            (self.user_id is not None and self.user_id == user.id) or
            (self.users and not user.is_superuser) or
            (self.admins and user.is_superuser)
        )

    def dismiss(self, user):
        """Dismiss this notification.

        :param user: The user dismissing this notification.
        """
        NotificationDismissal.objects.get_or_create(
            notification=self, user=user)

    def clean(self):
        super(Notification, self).clean()
        self.render()  # Just check it works.

    def __repr__(self):
        return "<Notification user=%s users=%r admins=%r %r>" % (
            ("None" if self.user is None else repr(self.user.username)),
            self.users, self.admins, self.render(),
        )


class NotificationDismissal(Model):
    """A notification dismissal.

    :ivar notification: The notification which has been dismissed.
    :ivar user: The user that has dismissed the linked notification.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    objects = Manager()

    notification = ForeignKey(Notification, null=False, blank=False)
    user = ForeignKey(User, null=False, blank=False)
