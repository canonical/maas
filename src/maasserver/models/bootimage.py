# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Registration of available boot images."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'BootImage',
    ]


from django.db.models import (
    CharField,
    ForeignKey,
    Manager,
    Model,
    )
from maasserver import DefaultMeta
from maasserver.models.nodegroup import NodeGroup
from maasserver.utils.orm import get_first


class BootImageManager(Manager):
    """Manager for model class.

    Don't import or instantiate this directly; access as `BootImage.objects`.
    """

    def get_by_natural_key(self, nodegroup, architecture, subarchitecture,
                           release, purpose):
        """Look up a specific image."""
        return self.get(
            nodegroup=nodegroup, architecture=architecture,
            subarchitecture=subarchitecture, release=release,
            purpose=purpose)

    def register_image(self, nodegroup, architecture, subarchitecture,
                       release, purpose):
        """Register an image if it wasn't already registered."""
        self.get_or_create(
            nodegroup=nodegroup, architecture=architecture,
            subarchitecture=subarchitecture, release=release,
            purpose=purpose)

    def have_image(self, nodegroup, architecture, subarchitecture, release,
                   purpose):
        """Is an image for the given kind of boot available?"""
        try:
            self.get_by_natural_key(
                nodegroup=nodegroup, architecture=architecture,
                subarchitecture=subarchitecture, release=release,
                purpose=purpose)
            return True
        except BootImage.DoesNotExist:
            return False

    def get_default_arch_image_in_nodegroup(self, nodegroup, series, purpose):
        """Return the first image available for any architecture in the
        nodegroup/series supplied.
        """
        images = BootImage.objects.filter(
            release=series, nodegroup=nodegroup, purpose=purpose)
        images = images.order_by('architecture')
        return get_first(images)


class BootImage(Model):
    """Available boot image (i.e. kernel and initrd).

    Each `BootImage` represents a type of boot for which a boot image is
    available.  The `maas-import-pxe-files` script imports these, and the
    TFTP server provides them to booting nodes.

    If a boot image is missing, that may mean that the import script has not
    been run yet, or has failed; or that it was not configured to provide
    that particular image.

    Fields correspond directly to values used in the `tftppath` module.
    """

    class Meta(DefaultMeta):
        unique_together = (
            ('nodegroup', 'architecture', 'subarchitecture', 'release',
             'purpose'),
            )

    objects = BootImageManager()

    # Nodegroup (cluster controller) that has the images.
    nodegroup = ForeignKey(NodeGroup, null=False, editable=False, unique=False)

    # System architecture (e.g. "i386") that the image is for.
    architecture = CharField(max_length=255, blank=False, editable=False)

    # Sub-architecture, e.g. a particular type of ARM machine that needs
    # different treatment.  (For architectures that don't need these
    # such as i386 and amd64, we use "generic").
    subarchitecture = CharField(max_length=255, blank=False, editable=False)

    # Ubuntu release (e.g. "precise") that the image boots.
    release = CharField(max_length=255, blank=False, editable=False)

    # Boot purpose (e.g. "commissioning" or "install") that the image is for.
    purpose = CharField(max_length=255, blank=False, editable=False)

    def __repr__(self):
        return "<BootImage %s/%s-%s-%s>" % (
            self.architecture,
            self.subarchitecture,
            self.release,
            self.purpose,
            )
