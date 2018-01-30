# Copyright 2012-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""ResourcePool model."""

__all__ = [
    'DEFAULT_RESOURCEPOOL_DESCRIPTION',
    'DEFAULT_RESOURCEPOOL_NAME',
    'ResourcePool',
]

from datetime import datetime

from django.core.exceptions import ValidationError
from django.db.models import (
    CharField,
    Manager,
    TextField,
)
from maasserver import DefaultMeta
from maasserver.fields import MODEL_NAME_VALIDATOR
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.worker_user import user_name as worker_username
from metadataserver.nodeinituser import user_name as node_init_username


DEFAULT_RESOURCEPOOL_NAME = 'default'
DEFAULT_RESOURCEPOOL_DESCRIPTION = 'Default pool'


class ResourcePoolManager(Manager):
    """Manager for the :class:`ResourcePool` model."""

    def get_default_resource_pool(self):
        """Return the default resource pool."""
        now = datetime.now()
        pool, _ = self.get_or_create(
            id=0,
            defaults={
                'id': 0,
                'name': DEFAULT_RESOURCEPOOL_NAME,
                'description': DEFAULT_RESOURCEPOOL_DESCRIPTION,
                'created': now,
                'updated': now})
        return pool

    def get_user_resource_pools(self, user):
        """Return ResourcePools a User has access to."""
        return self.model.objects.filter(role__users=user)

    def user_can_access_pool(self, user, pool):
        """Whether a User has access to a ResourcePool."""
        # maas internal users need to be able to own any node
        admin_usernames = (worker_username, node_init_username)
        if user.username in admin_usernames:
            return True
        return self.get_user_resource_pools(user).filter(pk=pool.pk).exists()


class ResourcePool(CleanSave, TimestampedModel):
    """A resource pool."""

    objects = ResourcePoolManager()

    name = CharField(
        max_length=256, unique=True, editable=True,
        validators=[MODEL_NAME_VALIDATOR])
    description = TextField(null=False, blank=True, editable=True)

    class Meta(DefaultMeta):

        ordering = ['name']

    def __str__(self):
        return self.name

    def is_default(self):
        """Whether this is the default pool."""
        return self.id == 0

    def delete(self):
        if self.is_default():
            raise ValidationError(
                'This is the default pool, it cannot be deleted.')
        if self.node_set.exists():
            raise ValidationError(
                'Pool has machines in it, it cannot be deleted.')
        self._get_pool_role().delete()
        super().delete()

    def grant_user(self, user):
        """Grant user access to the resource pool.

        XXX This should be dropped once we implement full RBAC, and the logic
        moved to methods in Role.
        """
        role = self._get_pool_role()
        role.users.add(user)

    def revoke_user(self, user):
        """Revoke user access to the resource pool.

        XXX This should be dropped once we implement full RBAC, and the logic
        moved to methods in Role.
        """
        from maasserver.models.node import Machine
        if Machine.objects.filter(pool=self, owner=user).exists():
            raise ValidationError(
                'User has machines in the pool, it cannot be revoked.')
        role = self._get_pool_role()
        role.users.remove(user)

    def _get_pool_role(self):
        """Return the Role associated to the pool.

        Until full RBAC is implemented, each ResourcePool is assigned to a
        single role.
        """
        return self.role_set.first()


# When a resource pool is created is created, create a default role associated
# to it.
def create_resource_pool(sender, instance, created, **kwargs):
    if not created:
        return

    from maasserver.models.role import Role
    role = Role(
        name='role-{}'.format(instance.name),
        description='Default role for resource pool {}'.format(instance.name))
    role.save()
    role.resource_pools.add(instance)
