# Copyright 2012-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""ResourcePool model."""

__all__ = [
    "DEFAULT_RESOURCEPOOL_DESCRIPTION",
    "DEFAULT_RESOURCEPOOL_NAME",
    "ResourcePool",
]

from datetime import datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import AutoField, CharField, Manager, TextField

from maasserver.fields import MODEL_NAME_VALIDATOR
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.orm import MAASQueriesMixin

DEFAULT_RESOURCEPOOL_NAME = "default"
DEFAULT_RESOURCEPOOL_DESCRIPTION = "Default pool"


class ResourcePoolQueriesMixin(MAASQueriesMixin):
    def get_specifiers_q(self, specifiers, separator=":", **kwargs):
        specifier_types = {
            None: self._add_default_query,
            "name": "__name",
            "id": "__id",
        }
        return super().get_specifiers_q(
            specifiers,
            specifier_types=specifier_types,
            separator=separator,
            **kwargs
        )


class ResourcePoolManager(Manager, ResourcePoolQueriesMixin):
    """Manager for the :class:`ResourcePool` model."""

    def get_default_resource_pool(self):
        """Return the default resource pool."""
        now = datetime.now()
        pool, _ = self.get_or_create(
            id=0,
            defaults={
                "id": 0,
                "name": DEFAULT_RESOURCEPOOL_NAME,
                "description": DEFAULT_RESOURCEPOOL_DESCRIPTION,
                "created": now,
                "updated": now,
            },
        )
        return pool

    def get_resource_pool_or_404(self, specifiers, user, perm):
        """Fetch a `ResourcePool` by its id.  Raise exceptions if no
        `ResourcePool` with this id exists or if the provided user has not
        the required permission to access this `ResourcePool`.

        :param specifiers: A specifier to uniquely locate the ResourcePool.
        :type specifiers: unicode
        :param user: The user that should be used in the permission check.
        :type user: django.contrib.auth.models.User
        :param perm: The permission to assert that the user has on the node.
        :type perm: unicode
        :raises: django.http.Http404_,
            :class:`maasserver.exceptions.PermissionDenied`.

        .. _django.http.Http404: https://
           docs.djangoproject.com/en/dev/topics/http/views/
           #the-http404-exception
        """
        pool = self.get_object_by_specifiers_or_raise(specifiers)
        if user.has_perm(perm, pool):
            return pool
        else:
            raise PermissionDenied()

    def get_resource_pools(self, user):
        """Fetch `ResourcePool`'s on which the User_ has the given permission.

        :param user: The user that should be used in the permission check.
        :type user: User_

        .. _User: https://
           docs.djangoproject.com/en/dev/topics/auth/
           #django.contrib.auth.models.User

        """
        # Circular imports.
        from maasserver.rbac import rbac

        if rbac.is_enabled():
            fetched = rbac.get_resource_pool_ids(
                user.username, "view", "view-all"
            )
            pool_ids = set(fetched["view"] + fetched["view-all"])
            return self.filter(id__in=pool_ids)
        return self.all()


class ResourcePool(CleanSave, TimestampedModel):
    """A resource pool."""

    objects = ResourcePoolManager()

    # explicitly define the AutoField since default is BigAutoField which
    # doesn't allow 0 as a value (used for the default resource pool)
    id = AutoField(primary_key=True)
    name = CharField(
        max_length=256,
        unique=True,
        editable=True,
        validators=[MODEL_NAME_VALIDATOR],
    )
    description = TextField(null=False, blank=True, editable=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def is_default(self):
        """Whether this is the default pool."""
        return self.id == 0

    def delete(self):
        if self.is_default():
            raise ValidationError(
                "This is the default pool, it cannot be deleted."
            )
        if self.node_set.exists():
            raise ValidationError(
                "Pool has machines in it, it cannot be deleted."
            )
        super().delete()
