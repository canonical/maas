# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Fabric objects."""

__all__ = [
    "DEFAULT_FABRIC_NAME",
    "Fabric",
    "NAME_VALIDATOR",
    ]

import datetime
import re

from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from django.core.validators import RegexValidator
from django.db.models import (
    CharField,
    Manager,
)
from django.db.models.query import QuerySet
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.interface import Interface
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.orm import MAASQueriesMixin


def validate_fabric_name(value):
    """Django validator: `value` must be either `None`, or valid."""
    if value is None:
        return
    namespec = re.compile(r'^[ \w-]+$')
    if not namespec.search(value):
        raise ValidationError("Invalid fabric name: %s." % value)

NAME_VALIDATOR = RegexValidator(r'^[ \w-]+$')

# Name of the special, default fabric.  This fabric cannot be deleted.
DEFAULT_FABRIC_NAME = 'fabric-0'


class FabricQueriesMixin(MAASQueriesMixin):

    def get_specifiers_q(self, specifiers, separator=':', **kwargs):
        # This dict is used by the constraints code to identify objects
        # with particular properties. Please note that changing the keys here
        # can impact backward compatibility, so use caution.
        specifier_types = {
            None: self._add_default_query,
            'name': "__name",
            'class': "__class_type",
        }
        return super(FabricQueriesMixin, self).get_specifiers_q(
            specifiers, specifier_types=specifier_types, separator=separator,
            **kwargs)


class FabricQuerySet(QuerySet, FabricQueriesMixin):
    """Custom QuerySet which mixes in some additional queries specific to
    this object. This needs to be a mixin because an identical method is needed
    on both the Manager and all QuerySets which result from calling the
    manager.
    """


class FabricManager(Manager, FabricQueriesMixin):
    """Manager for :class:`Fabric` model."""

    def get_queryset(self):
        queryset = FabricQuerySet(self.model, using=self._db)
        return queryset

    def get_default_fabric(self):
        """Return the default fabric."""
        now = datetime.datetime.now()
        fabric, created = self.get_or_create(
            id=0,
            defaults={
                'id': 0,
                'name': None,
                'created': now,
                'updated': now,
            }
        )
        if created:
            fabric._create_default_vlan()
        return fabric

    def get_or_create_for_subnet(self, subnet):
        """Given an existing fabric_id (by default, the default fabric)
        creates and returns a new Fabric if there is an existing Subnet in
        the fabric already. Exclude the specified subnet (which will be one
        that was just created).
        """
        from maasserver.models import Subnet
        default_fabric = self.get_default_fabric()
        if Subnet.objects.filter(
                vlan__fabric=default_fabric).exclude(
                id=subnet.id).count() == 0:
            return default_fabric
        else:
            return Fabric.objects.create()

    def filter_by_nodegroup_interface(self, nodegroup, ifname):
        """Query for the Fabric associated with the specified NodeGroup,
        where the NodeGroupInterface matches the specified name.
        """
        return self.filter(
            vlan__subnet__nodegroupinterface__nodegroup=nodegroup,
            vlan__subnet__nodegroupinterface__interface=ifname)

    def get_fabric_or_404(self, specifiers, user, perm):
        """Fetch a `Fabric` by its id.  Raise exceptions if no `Fabric` with
        this id exist or if the provided user has not the required permission
        to access this `Fabric`.

        :param specifiers: The fabric specifiers.
        :type specifiers: string
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
        fabric = self.get_object_by_specifiers_or_raise(specifiers)
        if user.has_perm(perm, fabric):
            return fabric
        else:
            raise PermissionDenied()


class Fabric(CleanSave, TimestampedModel):
    """A `Fabric`.

    :ivar name: The short-human-identifiable name for this fabric.
    :ivar objects: An instance of the class :class:`FabricManager`.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""
        verbose_name = "Fabric"
        verbose_name_plural = "Fabrics"

    objects = FabricManager()

    name = CharField(
        max_length=256, editable=True, null=True, blank=True, unique=False,
        validators=[validate_fabric_name])

    class_type = CharField(
        max_length=256, editable=True, null=True, blank=True,
        validators=[NAME_VALIDATOR])

    def __str__(self):
        return "name=%s" % self.get_name()

    def is_default(self):
        """Is this the default fabric?"""
        return self.id == 0

    def get_default_vlan(self):
        return self.vlan_set.all().order_by('id').first()

    def get_name(self):
        """Return the name of the fabric."""
        if self.name:
            return self.name
        else:
            return "fabric-%s" % self.id

    def delete(self):
        if self.is_default():
            raise ValidationError(
                "This fabric is the default fabric, it cannot be deleted.")
        # Circular imports.
        if Interface.objects.filter(vlan__fabric=self).exists():
            raise ValidationError(
                "Can't delete fabric: interfaces are connected to VLANs from "
                "this fabric.")
        # Circular imports.
        from maasserver.models.nodegroupinterface import NodeGroupInterface
        if NodeGroupInterface.objects.filter(vlan__fabric=self).exists():
            raise ValidationError(
                "Can't delete fabric: cluster interfaces are connected to "
                "VLANs from this fabric.")
        super(Fabric, self).delete()

    def _create_default_vlan(self):
        # Circular imports.
        from maasserver.models.vlan import (
            VLAN, DEFAULT_VLAN_NAME, DEFAULT_VID)
        VLAN.objects.create(
            name=DEFAULT_VLAN_NAME, vid=DEFAULT_VID, fabric=self)

    def save(self, *args, **kwargs):
        created = self.id is None
        super(Fabric, self).save(*args, **kwargs)
        # Create default VLAN if this is a fabric creation.
        if created:
            self._create_default_vlan()

    def clean_name(self):
        reserved = re.compile('fabric-\d+$')
        if self.name is not None and reserved.search(self.name):
            if (self.id is None or self.name != 'fabric-%d' % self.id):
                raise ValidationError(
                    {'name': ["Reserved fabric name."]})

    def clean(self, *args, **kwargs):
        super(Fabric, self).clean(*args, **kwargs)
        self.clean_name()
