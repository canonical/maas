# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""UserGroup model"""

__all__ = [
    "DEFAULT_USERGROUP_DESCRIPTION",
    "DEFAULT_USERGROUP_NAME",
    "UserGroup",
]

from datetime import datetime

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import (
    CASCADE,
    CharField,
    ForeignKey,
    Manager,
    ManyToManyField,
    Model,
    TextField,
)
from maasserver import DefaultMeta
from maasserver.fields import MODEL_NAME_VALIDATOR
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


DEFAULT_USERGROUP_NAME = 'default'
DEFAULT_USERGROUP_DESCRIPTION = 'Default user group'


class UserGroupManager(Manager):
    """Manager for the :class:`UserGroup` model."""

    def get_default_usergroup(self):
        """Return the default user group."""
        now = datetime.now()
        group, _ = self.get_or_create(
            id=0,
            defaults={
                'id': 0,
                'name': DEFAULT_USERGROUP_NAME,
                'description': DEFAULT_USERGROUP_DESCRIPTION,
                'created': now,
                'updated': now})
        return group


class UserGroup(CleanSave, TimestampedModel):
    """A Group of Users."""

    objects = UserGroupManager()

    name = CharField(
        max_length=256, unique=True, editable=True,
        validators=[MODEL_NAME_VALIDATOR])
    description = TextField(null=False, blank=True, editable=True)
    users = ManyToManyField(User, through='UserGroupMembership')

    class Meta(DefaultMeta):

        ordering = ['name']

    def __str__(self):
        return self.name

    def is_default(self):
        """Whether this is the default user group."""
        return self.id == 0

    def delete(self):
        if self.is_default():
            raise ValidationError(
                'This is the default user group, it cannot be deleted.')
        super().delete()


class UserGroupMembership(Model):

    user = ForeignKey(User, on_delete=CASCADE)
    group = ForeignKey(UserGroup, on_delete=CASCADE)
