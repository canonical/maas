# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Fabric objects."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "DEFAULT_FABRIC_NAME",
    "Fabric",
    "FABRIC_NAME_VALIDATOR",
    ]

import datetime

from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from django.core.validators import RegexValidator
from django.db.models import (
    CharField,
    Manager,
)
from django.shortcuts import get_object_or_404
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.interface import Interface
from maasserver.models.timestampedmodel import TimestampedModel


FABRIC_NAME_VALIDATOR = RegexValidator('^[ \w-]+$')

# Name of the special, default fabric.  This fabric cannot be deleted.
DEFAULT_FABRIC_NAME = 'Default fabric'


class FabricManager(Manager):
    """Manager for :class:`Fabric` model."""

    def get_default_fabric(self):
        """Return the default fabric."""
        now = datetime.datetime.now()
        fabric, created = self.get_or_create(
            id=0,
            defaults={
                'id': 0,
                'name': DEFAULT_FABRIC_NAME,
                'created': now,
                'updated': now,
            }
        )
        if created:
            fabric._create_default_vlan()
        return fabric

    def get_fabric_or_404(self, id, user, perm):
        """Fetch a `Fabric` by its id.  Raise exceptions if no `Fabric` with
        this id exist or if the provided user has not the required permission
        to access this `Fabric`.

        :param id: The fabric_id.
        :type id: int
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
        fabric = get_object_or_404(self.model, id=id)
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
        max_length=256, unique=True, editable=True,
        validators=[FABRIC_NAME_VALIDATOR])

    def __unicode__(self):
        return "name=%s" % self.name

    def is_default(self):
        """Is this the default fabric?"""
        return self.id == 0

    def get_default_vlan(self):
        return self.vlan_set.all().order_by('id').first()

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
