# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Boot Resource."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'BootResource',
    ]

from django.core.exceptions import ValidationError
from django.db.models import (
    CharField,
    IntegerField,
    Manager,
    )
from maasserver import DefaultMeta
from maasserver.enum import (
    BOOT_RESOURCE_TYPE,
    BOOT_RESOURCE_TYPE_CHOICES,
    BOOT_RESOURCE_TYPE_CHOICES_DICT,
    )
from maasserver.fields import JSONObjectField
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.orm import (
    get_first,
    get_one,
    )

# Names on boot resources have a specific meaning depending on the type
# of boot resource. If its a synced or generated image then the name must
# be in the format os/series.
RTYPE_REQUIRING_OS_SERIES_NAME = (
    BOOT_RESOURCE_TYPE.SYNCED,
    BOOT_RESOURCE_TYPE.GENERATED,
    )


class BootResourceManager(Manager):

    def _has_resource(self, rtype, name, architecture, subarchitecture):
        """Return True if `BootResource` exists with given rtype, name,
        architecture, and subarchitecture."""
        arch = '%s/%s' % (architecture, subarchitecture)
        return self.filter(
            rtype=rtype, name=name, architecture=arch).exists()

    def _get_resource(self, rtype, name, architecture, subarchitecture):
        """Return `BootResource` with given rtype, name, architecture, and
        subarchitecture."""
        arch = '%s/%s' % (architecture, subarchitecture)
        return get_one(
            self.filter(rtype=rtype, name=name, architecture=arch))

    def has_synced_resource(self, osystem, architecture, subarchitecture,
                            series):
        """Return True if `BootResource` exists with type of SYNCED, and given
        osystem, architecture, subarchitecture, and series."""
        name = '%s/%s' % (osystem, series)
        return self._has_resource(
            BOOT_RESOURCE_TYPE.SYNCED, name, architecture, subarchitecture)

    def get_synced_resource(self, osystem, architecture, subarchitecture,
                            series):
        """Return `BootResource` with type of SYNCED, and given
        osystem, architecture, subarchitecture, and series."""
        name = '%s/%s' % (osystem, series)
        return self._get_resource(
            BOOT_RESOURCE_TYPE.SYNCED, name, architecture, subarchitecture)

    def has_generated_resource(self, osystem, architecture, subarchitecture,
                               series):
        """Return True if `BootResource` exists with type of GENERATED, and
        given osystem, architecture, subarchitecture, and series."""
        name = '%s/%s' % (osystem, series)
        return self._has_resource(
            BOOT_RESOURCE_TYPE.GENERATED, name, architecture, subarchitecture)

    def get_generated_resource(self, osystem, architecture, subarchitecture,
                               series):
        """Return `BootResource` with type of GENERATED, and given
        osystem, architecture, subarchitecture, and series."""
        name = '%s/%s' % (osystem, series)
        return self._get_resource(
            BOOT_RESOURCE_TYPE.GENERATED, name, architecture, subarchitecture)

    def has_uploaded_resource(self, name, architecture, subarchitecture):
        """Return True if `BootResource` exists with type of UPLOADED, and
        given name, architecture, and subarchitecture."""
        return self._has_resource(
            BOOT_RESOURCE_TYPE.UPLOADED, name, architecture, subarchitecture)

    def get_uploaded_resource(self, name, architecture, subarchitecture):
        """Return `BootResource` with type of UPLOADED, and given
        name, architecture, and subarchitecture."""
        return self._get_resource(
            BOOT_RESOURCE_TYPE.UPLOADED, name, architecture, subarchitecture)

    def get_usable_architectures(self):
        """Return the set of usable architectures.

        Return the architectures for which the has at least one
        commissioning image and at least one install image.
        """
        arches = set()
        for resource in self.all():
            resource_set = resource.get_latest_set()
            if resource_set.commissionable and resource_set.installable:
                arches.add(resource.architecture)
        return arches

    def get_commissionable_resource(self, osystem, series):
        """Return generator for all commissionable resources for the
        given osystem and series."""
        name = '%s/%s' % (osystem, series)
        resources = self.filter(name=name).order_by('architecture')
        for resource in resources:
            resource_set = resource.get_latest_set()
            if resource_set is not None and resource_set.commissionable:
                yield resource

    def get_default_commissioning_resource(self, osystem, series):
        """Return best guess `BootResource` for the given osystem and series.

        Prefers `i386` then `amd64` resources if available.  Returns `None`
        if none match requirements.
        """
        commissionable = list(
            self.get_commissionable_resource(osystem, series))
        for resource in commissionable:
            # Prefer i386. It will work for most cases where we don't
            # know the actual architecture.
            arch, subarch = resource.split_arch()
            if arch == 'i386':
                return resource
        for resource in commissionable:
            # Prefer amd64. It has a much better chance of working than
            # say arm or ppc.
            arch, subarch = resource.split_arch()
            if arch == 'amd64':
                return resource
        return get_first(commissionable)


def validate_architecture(value):
    """Validates that architecture value contains a subarchitecture."""
    if '/' not in value:
        raise ValidationError(
            "Invalid architecture, missing subarchitecture.")


class BootResource(CleanSave, TimestampedModel):
    """Boot resource.

    Each `BootResource` represents a os/series combination or custom uploaded
    image that maps to a specific architecture that a node can use to
    commission or install.

    `BootResource` can have multiple `BootResourceSet` corresponding to
    different versions of this `BootResource`. When a node selects this
    `BootResource` the newest `BootResourceSet` is used to deploy to the node.

    :ivar rtype: Type of `BootResource`. See the vocabulary
        :class:`BOOT_RESOURCE_TYPE`.
    :ivar name: Name of the `BootResource`. If its BOOT_RESOURCE_TYPE.UPLOADED
        then `name` is used to reference this image. If its
        BOOT_RESOURCE_TYPE.SYCNED or BOOT_RESOURCE_TYPE.GENERATED then its
        in the format of os/series.
    :ivar architecture: Architecture of the `BootResource`. It must be in
        the format arch/subarch.
    :ivar extra: Extra information about the file. This is only used
        for synced Ubuntu images.
    """

    class Meta(DefaultMeta):
        unique_together = (
            ('name', 'architecture'),
            )

    objects = BootResourceManager()

    rtype = IntegerField(
        max_length=10, choices=BOOT_RESOURCE_TYPE_CHOICES, editable=False)

    name = CharField(max_length=255, blank=False)

    architecture = CharField(
        max_length=255, blank=False, validators=[validate_architecture])

    extra = JSONObjectField(blank=True, default="", editable=False)

    def __repr__(self):
        return "<BootResource %s>" % self.name

    @property
    def display_rtype(self):
        """Return rtype text as displayed to the user."""
        return BOOT_RESOURCE_TYPE_CHOICES_DICT[self.rtype]

    def clean(self):
        """Validate the model.

        Checks that the name is in a valid format, for its type.
        """
        if self.rtype == BOOT_RESOURCE_TYPE.UPLOADED:
            if '/' in self.name:
                raise ValidationError(
                    "%s boot resource cannot contain a '/' in it's name." % (
                        self.display_rtype))
        elif self.rtype in RTYPE_REQUIRING_OS_SERIES_NAME:
            if '/' not in self.name:
                raise ValidationError(
                    "%s boot resource must contain a '/' in it's name." % (
                        self.display_rtype))

    def unique_error_message(self, model_class, unique_check):
        if unique_check == (
                'name', 'architecture'):
            return (
                "Boot resource of name, and architecture already "
                "exists.")
        return super(
            BootResource, self).unique_error_message(model_class, unique_check)

    def get_latest_set(self):
        """Return latest `BootResourceSet`."""
        return self.sets.order_by('id').last()

    def get_latest_complete_set(self):
        """Return latest `BootResourceSet` where all `BootResouceFile`'s
        are complete."""
        for resource_set in self.sets.order_by('id').reverse():
            if resource_set.complete:
                return resource_set
        return None

    def split_arch(self):
        return self.architecture.split('/')
