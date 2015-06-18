# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""VLAN objects."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "DEFAULT_VID",
    "DEFAULT_VLAN_NAME",
    "Fabric",
    ]


from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db.models import (
    CharField,
    ForeignKey,
    IntegerField,
    Manager,
)
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.fabric import Fabric
from maasserver.models.interface import VLANInterface
from maasserver.models.timestampedmodel import TimestampedModel


VLAN_NAME_VALIDATOR = RegexValidator('^[ \w-]+$')

DEFAULT_VLAN_NAME = 'Default VLAN'
DEFAULT_VID = 0


class VLANManager(Manager):
    """Manager for :class:`VLAN` model."""

    def get_default_vlan(self):
        """Return the default VLAN of the default fabric."""
        # Circular imports
        from maasserver.models.fabric import Fabric
        return Fabric.objects.get_default_fabric().get_default_vlan()


class VLAN(CleanSave, TimestampedModel):
    """A `VLAN`.

    :ivar name: The short-human-identifiable name for this VLAN.
    :ivar vid: The VLAN ID of this VLAN.
    :ivar fabric: The `Fabric` this VLAN belongs to.
    """

    objects = VLANManager()

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""
        verbose_name = "VLAN"
        verbose_name_plural = "VLANs"
        unique_together = (
            ('vid', 'fabric'),
            ('name', 'fabric'),
        )

    name = CharField(
        max_length=256, editable=True, validators=[VLAN_NAME_VALIDATOR])

    vid = IntegerField(editable=True)

    fabric = ForeignKey('Fabric', blank=False, editable=True)

    def __unicode__(self):
        return "name=%s, vid=%d, fabric=%s" % (
            self.name, self.vid, self.fabric.name)

    def clean_vid(self):
        if self.vid < 0 or self.vid > 4095:
            raise ValidationError(
                {'vid':
                    ["Vid must be between 0 and 4095."]})

    def clean(self):
        self.clean_vid()

    def is_fabric_default(self):
        """Is this the default VLAN in the fabric?"""
        return self.fabric.get_default_vlan() == self

    def manage_connected_interfaces(self):
        """Deal with connected interfaces:

        - delete all VLAN interfaces.
        - reconnect the other interfaces to the default VLAN of the fabric.
        """
        for interface in self.interface_set.all():
            if isinstance(interface, VLANInterface):
                interface.delete()
            else:
                interface.vlan = self.fabric.get_default_vlan()
                interface.save()

    def manage_connected_cluster_interfaces(self):
        """Reconnect cluster interfaces to the default VLAN of the fabric."""
        for ngi in self.nodegroupinterface_set.all():
            ngi.vlan = self.fabric.get_default_vlan()
            ngi.save()

    def delete(self):
        if self.is_fabric_default():
            raise ValidationError(
                "This VLAN is the default VLAN in the fabric, "
                "it cannot be deleted.")
        self.manage_connected_interfaces()
        self.manage_connected_cluster_interfaces()
        super(VLAN, self).delete()
