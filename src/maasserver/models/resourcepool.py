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

# The default pool cannot be renamed or deleted.
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
        super().delete()
