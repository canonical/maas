# Copyright 2013-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Physical zone objects."""

from django.core.exceptions import ValidationError
from django.db.models import CharField, TextField

from maasserver.enum import NODE_TYPE
from maasserver.fields import MODEL_NAME_VALIDATOR
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


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

    name = CharField(
        max_length=256,
        unique=True,
        editable=True,
        validators=[MODEL_NAME_VALIDATOR],
    )

    description = TextField(blank=True, editable=True)

    def __str__(self):
        return self.name

    def delete(self):
        # Avoid circular import
        from maasserver.models.defaultresource import DefaultResource

        if DefaultResource.objects.get_default_zone().id == self.id:
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
