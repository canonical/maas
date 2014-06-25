# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
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

from django.core.exceptions import ValidationError
from django.db.models import (
    CharField,
    ForeignKey,
    Manager,
    )
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.nodegroup import NodeGroup
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.orm import get_first


class BootImageManager(Manager):
    """Manager for model class.

    Don't import or instantiate this directly; access as `BootImage.objects`.
    """

    def get_by_natural_key(self, nodegroup, osystem, architecture,
                           subarchitecture, release, purpose, label):
        """Look up a specific image."""
        return self.get(
            nodegroup=nodegroup, osystem=osystem, architecture=architecture,
            subarchitecture=subarchitecture, release=release,
            purpose=purpose, label=label)

    def register_image(self, nodegroup, osystem, architecture, subarchitecture,
                       release, purpose, label, supported_subarches,
                       xinstall_path=None, xinstall_type=None):
        """Register an image if it wasn't already registered."""
        image, created = self.get_or_create(
            nodegroup=nodegroup, osystem=osystem, architecture=architecture,
            subarchitecture=subarchitecture, release=release,
            purpose=purpose, label=label,
            defaults={
                'supported_subarches': supported_subarches,
                'xinstall_path': xinstall_path,
                'xinstall_type': xinstall_type,
                })
        if not created:
            save = False
            updates_subarches = (
                supported_subarches != '' and
                image.supported_subarches != supported_subarches)
            if updates_subarches:
                # Update the non-key field data if it changed and the
                # new value contains data (ie. not blank).
                image.supported_subarches = supported_subarches
                save = True
            if image.xinstall_path != xinstall_path or \
                    image.xinstall_type != xinstall_type:
                image.xinstall_path = xinstall_path
                image.xinstall_type = xinstall_type
                save = True
            if save:
                image.save()
        return image

    def have_image(self, nodegroup, osystem, architecture, subarchitecture,
                   release, purpose, label=None, supported_subarches=None):
        """Is an image for the given kind of boot available?"""
        if label is None:
            label = "release"
        try:
            # supported_subarches is currently not a key field so is
            # ignored.
            self.get_by_natural_key(
                nodegroup=nodegroup, osystem=osystem,
                architecture=architecture, subarchitecture=subarchitecture,
                release=release, purpose=purpose, label=label)
            return True
        except BootImage.DoesNotExist:
            return False

    def get_default_arch_image_in_nodegroup(self, nodegroup, osystem, series,
                                            purpose):
        """Return any image for the given nodegroup, osystem, series,
        and purpose.

        Prefers `i386` images if available.  Returns `None` if no images match
        requirements.
        """
        images = BootImage.objects.filter(
            osystem=osystem, release=series, nodegroup=nodegroup,
            purpose=purpose)
        for image in images:
            # Prefer i386, any available subarchitecture (usually just
            # "generic").  It will work for most cases where we don't know
            # the actual architecture.
            if image.architecture == 'i386':
                return image
        images = images.order_by('architecture')
        return get_first(images)

    def _get_bootable_architectures(self, nodegroup, purpose):
        """Return architecture/subarchitecture pairs with boot images.

        :param nodegroup: The `NodeGroup` whose boot images should be queried.
        :param purpose: Boot purpose, e.g. `install` or `commissioning`.
            Only consider architectures for which `nodegroup` has images whose
            `purpose` matches.
        :return: A set of architecture names, in `arch/subarch` format.
        """
        query = BootImage.objects.filter(nodegroup=nodegroup, purpose=purpose)
        arch_pairs = query.values_list('architecture', 'subarchitecture')
        return {'%s/%s' % pair for pair in arch_pairs}

    def get_usable_architectures(self, nodegroup):
        """Return the list of usable architectures for a nodegroup.

        Return the architectures for which the nodegroup has at least one
        commissioning image and at least one install image.
        """
        arches_commissioning = self._get_bootable_architectures(
            nodegroup, 'commissioning')
        arches_install = self._get_bootable_architectures(
            nodegroup, 'install')
        return arches_commissioning & arches_install

    def get_latest_image(self, nodegroup, osystem, architecture,
                         subarchitecture, release, purpose):
        """Return the latest image for a set of criteria."""
        image = BootImage.objects.filter(
            nodegroup=nodegroup, osystem=osystem, architecture=architecture,
            subarchitecture=subarchitecture, release=release,
            purpose=purpose).order_by('id').last()
        if image is not None:
            return image
        images = BootImage.objects.filter(
            nodegroup=nodegroup, osystem=osystem, architecture=architecture,
            release=release, purpose=purpose,
            supported_subarches__icontains=subarchitecture)
        return images.order_by('id').last()

    def get_usable_osystems(self, nodegroup):
        """Return the list of usable operating systems for a nodegroup.
        """
        query = BootImage.objects.filter(nodegroup=nodegroup)
        return set(query.values_list('osystem', flat=True))

    def get_usable_releases(self, nodegroup, osystem):
        """Return the list of usable releases for a nodegroup and
        operating system.
        """
        query = BootImage.objects.filter(nodegroup=nodegroup, osystem=osystem)
        releases = query.values_list('release', flat=True)
        return set(releases)


class BootImage(CleanSave, TimestampedModel):
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
            ('nodegroup', 'osystem', 'architecture', 'subarchitecture',
             'release', 'purpose', 'label'),
            )

    objects = BootImageManager()

    # Nodegroup (cluster controller) that has the images.
    nodegroup = ForeignKey(NodeGroup, null=False, editable=False, unique=False)

    # Operating system (e.g. "ubuntu") that the image boots.
    osystem = CharField(max_length=255, blank=False, editable=False)

    # System architecture (e.g. "i386") that the image is for.
    architecture = CharField(max_length=255, blank=False, editable=False)

    # Sub-architecture, e.g. a particular type of ARM machine that needs
    # different treatment.  (For architectures that don't need these
    # such as i386 and amd64, we use "generic").
    subarchitecture = CharField(max_length=255, blank=False, editable=False)

    # Historic subarchitectures that this image implicitly supports.
    # For example, trusty's image also supports hwe-s, hwe-r, ... and so on.
    # This should be a comma separated list.
    supported_subarches = CharField(
        max_length=255, blank=True, editable=False)

    # OS release (e.g. "precise") that the image boots.
    release = CharField(max_length=255, blank=False, editable=False)

    # Boot purpose (e.g. "commissioning" or "install") that the image is for.
    purpose = CharField(max_length=255, blank=False, editable=False)

    # "Label" as in simplestreams parlance. (e.g. "release", "beta-1")
    label = CharField(
        max_length=255, blank=False, editable=False, default="release")

    # Curtin image path (e.g. "root-tgz"). Only used when purpose is set
    # to "xinstall".
    xinstall_path = CharField(
        max_length=255, null=True, blank=True, editable=False, default='')

    # Curtin image type (e.g. "tgz" or "dd"). Only used when purpose is set
    # to "xinstall".
    xinstall_type = CharField(
        max_length=30, null=True, blank=True, editable=False, default='')

    def clean_xinstall(self):
        """Validates that xinstall_path and xinstall_type are valid when
        xinstall purpose is set."""
        if self.purpose != 'xinstall':
            return
        invalid_xinstall_path = (
            self.xinstall_path is None or
            self.xinstall_path == '')
        invalid_xinstall_type = (
            self.xinstall_type is None or
            self.xinstall_type == '')
        if invalid_xinstall_path:
            raise ValidationError(
                "Invalid xinstall_path for an xinstall boot image.")
        if invalid_xinstall_type:
            raise ValidationError(
                "Invalid xinstall_type for an xinstall boot image.")

    def clean(self, *args, **kwargs):
        super(BootImage, self).clean(*args, **kwargs)
        self.clean_xinstall()

    def __repr__(self):
        return "<BootImage %s-%s/%s-%s-%s-%s>" % (
            self.osystem,
            self.architecture,
            self.subarchitecture,
            self.release,
            self.purpose,
            self.label,
            )
