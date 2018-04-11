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
    BooleanField,
    CASCADE,
    CharField,
    Count,
    ForeignKey,
    Manager,
    ManyToManyField,
    Model,
    Q,
    TextField,
)
from maasserver import DefaultMeta
from maasserver.fields import MODEL_NAME_VALIDATOR
from maasserver.models import (
    Node,
    ResourcePool,
)
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

    def get_remote_group_names(self):
        """Return names of groups related to external authentication."""
        return frozenset(
            self.filter(local=False).values_list('name', flat=True))


class UserGroup(CleanSave, TimestampedModel):
    """A Group of Users."""

    objects = UserGroupManager()

    name = CharField(
        max_length=256, unique=True, editable=True,
        validators=[MODEL_NAME_VALIDATOR])
    description = TextField(null=False, blank=True)
    local = BooleanField(blank=True, default=True)
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

        # check if by removing the group, any user would lose access to
        # machines in related resource pools
        nodes = Node.objects.filter(
            owner__isnull=False, pool__role__groups=self)
        # get a list of tuples with (User ID, Node ID) for users that have a
        # single way of accessing nodes in pool related to the group being
        # removed through user groups
        affected_users = User.objects.filter(
            usergroup__role__resource_pools__node__in=nodes).annotate(
                access_count=Count('usergroup')).filter(
                    access_count__lte=1).values('id', 'node')
        # remove tuples where users can access machines through a direct
        # relation with roles associated to resource pools
        affected_users = affected_users.difference(
            User.objects.filter(
                role__resource_pools__node__in=nodes).values('id', 'node'))
        if affected_users:
            raise ValidationError(
                "Can't remove group, some users have machines that"
                " would become unaccessible")

        super().delete()

    def add(self, user):
        """Add a user to this group."""
        if user in self.users.all():
            return
        UserGroupMembership.objects.create(user=user, group=self)

    def remove(self, user):
        """Remove a user from this group."""
        self._check_pools_accessibility_without_group(user)
        UserGroupMembership.objects.filter(user=user, group=self).delete()

    def _check_pools_accessibility_without_group(self, user):
        """Check required pools are still accessible after removing user."""
        # pools that are required to be accessible by the user because of owned
        # resources
        required_pools = ResourcePool.objects.filter(node__owner=user)
        # pools that are accessible after removing the user from the group
        from maasserver.models import Role
        roles = Role.objects.filter(
            Q(users=user) | (Q(groups__users=user) & ~Q(groups=self)))
        pools = ResourcePool.objects.filter(role__in=roles)
        if required_pools.difference(pools):
            raise ValidationError(
                "Can't remove user from group, owned machines are in pools"
                " that would become unaccessible.")


class UserGroupMembership(Model):

    user = ForeignKey(User, on_delete=CASCADE)
    group = ForeignKey(UserGroup, on_delete=CASCADE)
