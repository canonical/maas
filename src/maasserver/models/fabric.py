# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Fabric objects."""


from operator import attrgetter
import re

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import AutoField, CharField, Manager, TextField
from django.db.models.query import QuerySet

from maasserver.fields import MODEL_NAME_VALIDATOR
from maasserver.models.cleansave import CleanSave
from maasserver.models.interface import Interface
from maasserver.models.subnet import Subnet
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.orm import MAASQueriesMixin


def validate_fabric_name(value):
    """Django validator: `value` must be either `None`, or valid."""
    if value is None:
        return
    namespec = re.compile(r"^[\w-]+$")
    if not namespec.search(value):
        raise ValidationError("Invalid fabric name: %s." % value)


class FabricQueriesMixin(MAASQueriesMixin):
    def get_specifiers_q(self, specifiers, separator=":", **kwargs):
        # This dict is used by the constraints code to identify objects
        # with particular properties. Please note that changing the keys here
        # can impact backward compatibility, so use caution.
        specifier_types = {
            None: self._add_default_query,
            "name": "__name",
            "class": "__class_type",
        }
        return super().get_specifiers_q(
            specifiers,
            specifier_types=specifier_types,
            separator=separator,
            **kwargs,
        )


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
        fabric, created = self.get_or_create(id=0)
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
        if not (
            Subnet.objects.filter(vlan__fabric=default_fabric)
            .exclude(id=subnet.id)
            .exists()
        ):
            return default_fabric
        else:
            return Fabric.objects.create()

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

    class Meta:
        verbose_name = "Fabric"
        verbose_name_plural = "Fabrics"

    objects = FabricManager()

    # explicitly define the AutoField since default is BigAutoField and causing
    # modifications causes django to include this in the migration and not
    # allowing 0 as a value
    id = AutoField(primary_key=True, auto_created=True, verbose_name="ID")

    # We don't actually allow blank or null name, but that is enforced in
    # clean() and save().
    name = CharField(
        max_length=256,
        editable=True,
        null=True,
        blank=True,
        unique=True,
        validators=[validate_fabric_name],
    )

    description = TextField(null=False, blank=True)

    class_type = CharField(
        max_length=256,
        editable=True,
        null=True,
        blank=True,
        validators=[MODEL_NAME_VALIDATOR],
    )

    def __str__(self):
        return "name=%s" % self.get_name()

    def is_default(self):
        """Is this the default fabric?"""
        return self.id == 0

    def get_default_vlan(self):
        # This logic is replicated in the dehydrate() function of the
        # websockets handler.
        return sorted(self.vlan_set.all(), key=attrgetter("id"))[0]

    def get_name(self):
        """Return the name of the fabric."""
        return self.name or f"fabric-{self.id}"

    def delete(self):
        if self.is_default():
            raise ValidationError(
                "This fabric is the default fabric, it cannot be deleted."
            )
        if Subnet.objects.filter(vlan__fabric=self).exists():
            subnets = Subnet.objects.filter(vlan__fabric=self).order_by("cidr")
            descriptions = [str(subnet.cidr) for subnet in subnets]
            raise ValidationError(
                "Can't delete fabric; the following subnets are "
                "still present: %s" % (", ".join(descriptions))
            )
        if Interface.objects.filter(vlan__fabric=self).exists():
            interfaces = Interface.objects.filter(vlan__fabric=self).order_by(
                "node_config__node", "name"
            )
            descriptions = [iface.get_log_string() for iface in interfaces]
            raise ValidationError(
                "Can't delete fabric; the following interfaces are "
                "still connected: %s" % (", ".join(descriptions))
            )
        super().delete()

    def _create_default_vlan(self):
        from maasserver.models.vlan import DEFAULT_VID, DEFAULT_VLAN_NAME, VLAN

        VLAN.objects.create(
            name=DEFAULT_VLAN_NAME, vid=DEFAULT_VID, fabric=self
        )

    def save(self, *args, **kwargs):
        # Name will get set by clean_name() if None or empty, and there is an
        # id. We just need to handle names here for creation.
        created = self.id is None
        super().save(*args, **kwargs)
        if not self.name:
            # If we got here, then we have a newly created fabric that needs a
            # default name.
            self.name = f"fabric-{self.id}"
            self.save()
        # Create default VLAN if this is a fabric creation.
        if created:
            self._create_default_vlan()

    def clean_name(self):
        reserved = re.compile(r"^fabric-\d+$")
        if self.name:
            if reserved.search(self.name):
                if self.id is None or self.name != f"fabric-{self.id}":
                    raise ValidationError({"name": ["Reserved fabric name."]})
        elif self.id is not None:
            # Since we are not creating the fabric, force the (null or empty)
            # name to be the default name.
            self.name = f"fabric-{self.id}"

    def clean(self, *args, **kwargs):
        super().clean(*args, **kwargs)
        self.clean_name()
