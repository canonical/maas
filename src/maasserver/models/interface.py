# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for interfaces."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'BondInterface',
    'build_vlan_interface_name',
    'PhysicalInterface',
    'Interface',
    'VLANInterface',
    ]


from django.db import models
from django.db.models import (
    CharField,
    ForeignKey,
    Manager,
    ManyToManyField,
    PROTECT,
)
from djorm_pgarray.fields import ArrayField
from maasserver import DefaultMeta
from maasserver.enum import (
    INTERFACE_TYPE,
    INTERFACE_TYPE_CHOICES,
)
from maasserver.fields import (
    JSONObjectField,
    VerboseRegexValidator,
)
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel

# This is only last-resort validation, more specialized validation
# will happen at the form level based on the interface type.
INTERFACE_NAME_REGEXP = '^[\w\-_.:]+$'


def get_default_vlan():
    from maasserver.models.vlan import VLAN
    return VLAN.objects.get_default_vlan()


class Interface(CleanSave, TimestampedModel):

    class Meta(DefaultMeta):
        verbose_name = "Interface"
        verbose_name_plural = "Interfaces"
        ordering = ('created', )

    def __init__(self, *args, **kwargs):
        type = kwargs.get('type', self.get_type())
        kwargs['type'] = type
        # Derive the concret class from the interface's type.
        super(Interface, self).__init__(*args, **kwargs)
        klass = INTERFACE_TYPE_MAPPING.get(self.type)
        if klass:
            self.__class__ = klass
        else:
            raise ValueError("Unknown interface type: %s" % type)

    @classmethod
    def get_type(cls):
        return INTERFACE_TYPE.PHYSICAL

    name = CharField(
        blank=False, editable=True, max_length=255,
        validators=[VerboseRegexValidator(INTERFACE_NAME_REGEXP)],
        help_text="Interface name.")

    type = CharField(
        max_length=20, editable=False, choices=INTERFACE_TYPE_CHOICES,
        blank=False)

    parents = ManyToManyField(
        'self', blank=True, null=True, editable=True,
        through='InterfaceRelationship', symmetrical=False)

    vlan = ForeignKey(
        'VLAN', default=get_default_vlan, editable=True, blank=False,
        null=False, on_delete=PROTECT)

    ip_addresses = ManyToManyField(
        'StaticIPAddress', editable=True, blank=True, null=True)

    mac = ForeignKey('MACAddress', editable=True, blank=True, null=True)

    ipv4_params = JSONObjectField(blank=True, default="")

    ipv6_params = JSONObjectField(blank=True, default="")

    params = JSONObjectField(blank=True, default="")

    tags = ArrayField(
        dbtype="text", blank=True, null=False, default=[])

    def __unicode__(self):
        return "name=%s, type=%s, mac=%s" % (
            self.name, self.type, self.mac)

    def get_node(self):
        return self.mac.node


class InterfaceRelationship(CleanSave, TimestampedModel):
    child = ForeignKey(Interface, related_name="parent_relationships")
    parent = ForeignKey(Interface, related_name="children_relationships")


def delete_children_interface_handler(sender, instance, **kwargs):
    """Remove children interface when the parent gets removed."""
    if type(instance) in ALL_INTERFACE_TYPES:
        [rel.child.delete() for rel in instance.children_relationships.all()]


models.signals.pre_delete.connect(delete_children_interface_handler)


class InterfaceManager(Manager):
    """A Django manager managing one type of interface."""

    def get_queryset(self):
        qs = super(InterfaceManager, self).get_query_set()
        return qs.filter(type=self.model.get_type())


class PhysicalInterface(Interface):
    objects = InterfaceManager()

    class Meta(Interface.Meta):
        proxy = True
        verbose_name = "Physical interface"
        verbose_name_plural = "Physical interface"


class BondInterface(Interface):
    objects = InterfaceManager()

    class Meta(Interface.Meta):
        proxy = True
        verbose_name = "Bond"
        verbose_name_plural = "Bonds"

    @classmethod
    def get_type(self):
        return INTERFACE_TYPE.BOND

    def get_node(self):
        return self.parents.first().get_node()


def build_vlan_interface_name(vlan):
    return "vlan%d" % vlan.vid


class VLANInterface(Interface):
    objects = InterfaceManager()

    class Meta(Interface.Meta):
        proxy = True
        verbose_name = "VLAN interface"
        verbose_name_plural = "VLAN interfaces"

    @classmethod
    def get_type(self):
        return INTERFACE_TYPE.VLAN

    def get_node(self):
        # Return the node of the first parent.  The assertion that all the
        # parents are on the same node will be enforced at the form level.
        return self.parents.first().get_node()

    def get_name(self):
        return build_vlan_interface_name(self.vlan)

    def save(self, *args, **kwargs):
        # Auto update the interface name.
        new_name = self.get_name()
        if self.name != new_name:
            self.name = new_name
        return super(VLANInterface, self).save(*args, **kwargs)


INTERFACE_TYPE_MAPPING = {
    klass.get_type(): klass
    for klass in
    [
        PhysicalInterface,
        BondInterface,
        VLANInterface,
    ]
}

ALL_INTERFACE_TYPES = set(INTERFACE_TYPE_MAPPING.values())
