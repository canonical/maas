# Copyright 2013-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Physical zone objects."""


import datetime

from django.core.exceptions import ValidationError
from django.db.models import CharField, Manager, TextField

from maasserver.enum import NODE_TYPE
from maasserver.fields import MODEL_NAME_VALIDATOR
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel

# Name of the special, default zone.  This zone can be neither deleted nor
# renamed.
DEFAULT_ZONE_NAME = "default"


class ZoneManager(Manager):
    """Manager for :class:`Zone` model.

    Don't import or instantiate this directly; access as `<Class>.objects` on
    the model class it manages.
    """

    def get_default_zone(self):
        """Return the default zone."""
        now = datetime.datetime.now()
        zone, _ = self.get_or_create(
            name=DEFAULT_ZONE_NAME,
            defaults={
                "name": DEFAULT_ZONE_NAME,
                "created": now,
                "updated": now,
            },
        )
        return zone


class Zone(CleanSave, TimestampedModel):
    """A `Zone` is an entity used to logically group nodes together.

    :ivar name: The short-human-identifiable name for this zone.
    :ivar description: Free-form description for this zone.
    :ivar objects: An instance of the class :class:`ZoneManager`.
    """

    class Meta:
        verbose_name = "Physical zone"
        verbose_name_plural = "Physical zones"
        ordering = ["name"]

    objects = ZoneManager()

    name = CharField(
        max_length=256,
        unique=True,
        editable=True,
        validators=[MODEL_NAME_VALIDATOR],
    )

    description = TextField(blank=True, editable=True)

    def __str__(self):
        return self.name

    def is_default(self):
        """Is this the default zone?"""
        return self.name == DEFAULT_ZONE_NAME

    def delete(self):
        if self.is_default():
            raise ValidationError(
                "This zone is the default zone, it cannot be deleted."
            )
        super().delete()

    @property
    def node_only_set(self):
        """Returns just the nodes of node_type node in this zone."""
        return self.node_set.filter(node_type=NODE_TYPE.MACHINE)

    @property
    def device_only_set(self):
        """Returns just the nodes of node_type device in this zone."""
        return self.node_set.filter(node_type=NODE_TYPE.DEVICE)

    @property
    def rack_controller_only_set(self):
        """Returns just the nodes of node_type rack controller in this zone."""
        return self.node_set.filter(node_type=NODE_TYPE.RACK_CONTROLLER)
