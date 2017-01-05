# Copyright 2015-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for a notification message."""

__all__ = [
    'Notification',
]

from django.contrib.auth.models import User
from django.db.models import (
    BooleanField,
    CharField,
    ForeignKey,
    Manager,
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

    def clean(self):
        super(Notification, self).clean()
        self.render()  # Just check it works.
