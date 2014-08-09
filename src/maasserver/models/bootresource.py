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
    )
from maasserver import DefaultMeta
from maasserver.enum import BOOT_RESOURCE_TYPE_CHOICES
from maasserver.fields import JSONObjectField
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


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
            ('rtype', 'name', 'architecture'),
            )

    rtype = IntegerField(
        max_length=10, choices=BOOT_RESOURCE_TYPE_CHOICES, editable=False)

    name = CharField(max_length=255, blank=False)

    architecture = CharField(
        max_length=255, blank=False, validators=[validate_architecture])

    extra = JSONObjectField(blank=True, default="", editable=False)

    def __repr__(self):
        return "<BootResource %s>" % self.name

    def unique_error_message(self, model_class, unique_check):
        if unique_check == (
                'rtype', 'name', 'architecture'):
            return (
                "Boot resource of type, name, and architecture already "
                "exists.")
        return super(
            BootResource, self).unique_error_message(model_class, unique_check)

    def split_arch(self):
        return self.architecture.split('/')
