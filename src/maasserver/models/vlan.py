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
    Q,
)
from django.db.models.query import QuerySet
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.fabric import Fabric
from maasserver.models.interface import VLANInterface
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.orm import MAASQueriesMixin
from provisioningserver.utils.network import parse_integer


VLAN_NAME_VALIDATOR = RegexValidator('^[ \w-]+$')

DEFAULT_VLAN_NAME = 'Default VLAN'
DEFAULT_VID = 0
DEFAULT_MTU = 1500


def validate_vid(vid):
    """Raises a ValidationError if the given VID is not valid."""
    if vid < 0 or vid >= 0xfff:
        raise ValidationError(
            "VLAN tag (VID) out of range "
            "(0-4094; 0 for untagged.)")


class VLANQueriesMixin(MAASQueriesMixin):

    def get_specifiers_q(self, specifiers, separator=':', **kwargs):
        # Circular imports.
        from maasserver.models import (
            Fabric,
            Subnet,
        )

        # This dict is used by the constraints code to identify objects
        # with particular properties. Please note that changing the keys here
        # can impact backward compatibility, so use caution.
        specifier_types = {
            None: self._add_default_query,
            'fabric': (Fabric.objects, 'vlan'),
            'id': "__id",
            'name': "__name",
            'subnet': (Subnet.objects, 'vlan'),
            'vid': self._add_vid_query,
        }
        return super(VLANQueriesMixin, self).get_specifiers_q(
            specifiers, specifier_types=specifier_types, separator=separator,
            **kwargs)

    def _add_default_query(self, current_q, op, item):
        """If the item we're matching is an integer, first try to locate the
        object by its ID. Otherwise, search by name.
        """
        try:
            # Check if the user passed in a VID.
            vid = parse_integer(item)
        except ValueError:
            vid = None
            pass
        if item == "untagged":
            vid = 0

        if vid is not None:
            # We could do something like this here, if you actually need to
            # look up the VLAN by its ID:
            # if isinstance(item, unicode) and item.strip().startswith('vlan-')
            # ... but it's better to use VID, since that means something to
            # the user (and you always need to qualify a VLAN with its fabric
            # anyway).
            validate_vid(vid)
            return op(current_q, Q(vid=vid))
        else:
            return op(current_q, Q(name=item))

    def _add_vid_query(self, current_q, op, item):
        if item.lower() == 'untagged':
            vid = 0
        else:
            vid = parse_integer(item)
        validate_vid(vid)
        current_q = op(current_q, Q(vid=vid))
        return current_q


class VLANQuerySet(QuerySet, VLANQueriesMixin):
    """Custom QuerySet which mixes in some additional queries specific to
    this object. This needs to be a mixin because an identical method is needed
    on both the Manager and all QuerySets which result from calling the
    manager.
    """


class VLANManager(Manager, VLANQueriesMixin):
    """Manager for :class:`VLAN` model."""

    def get_queryset(self):
        queryset = VLANQuerySet(self.model, using=self._db)
        return queryset

    def get_default_vlan(self):
        """Return the default VLAN of the default fabric."""
        # Circular imports
        from maasserver.models.fabric import Fabric
        return Fabric.objects.get_default_fabric().get_default_vlan()

    def filter_by_nodegroup_interface(self, nodegroup, ifname):
        """Query fot the VLAN that matches the specified NodeGroup, whose
        interface matches the specified name.
        """
        return self.filter(
            subnet__nodegroupinterface__nodegroup=nodegroup,
            subnet__nodegroupinterface__interface=ifname)


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
        )

    name = CharField(
        max_length=256, editable=True, null=True, blank=True,
        validators=[VLAN_NAME_VALIDATOR])

    vid = IntegerField(editable=True)

    fabric = ForeignKey('Fabric', blank=False, editable=True)

    mtu = IntegerField(default=DEFAULT_MTU)

    def __unicode__(self):
        return "%s.%s" % (self.fabric.get_name(), self.get_name())

    def clean_vid(self):
        if self.vid < 0 or self.vid > 4095:
            raise ValidationError(
                {'vid':
                    ["Vid must be between 0 and 4095."]})

    def clean_mtu(self):
        # Linux doesn't allow lower than 552 for the MTU.
        if self.mtu < 552 or self.mtu > 65535:
            raise ValidationError(
                {'mtu':
                    ["MTU must be between 552 and 65535."]})

    def clean(self):
        self.clean_vid()
        self.clean_mtu()

    def is_fabric_default(self):
        """Is this the default VLAN in the fabric?"""
        return self.fabric.get_default_vlan() == self

    def get_name(self):
        """Return the name of the VLAN."""
        if self.is_fabric_default():
            return "untagged"
        else:
            return self.name

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

    def manage_connected_subnets(self):
        """Reconnect subnets the default VLAN of the fabric."""
        for subnet in self.subnet_set.all():
            subnet.vlan = self.fabric.get_default_vlan()
            subnet.save()

    def delete(self):
        if self.is_fabric_default():
            raise ValidationError(
                "This VLAN is the default VLAN in the fabric, "
                "it cannot be deleted.")
        self.manage_connected_interfaces()
        self.manage_connected_cluster_interfaces()
        self.manage_connected_subnets()
        super(VLAN, self).delete()
