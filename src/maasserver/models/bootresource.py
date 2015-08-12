# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
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
    BOOT_RESOURCE_FILE_TYPE,
    BOOT_RESOURCE_TYPE,
    BOOT_RESOURCE_TYPE_CHOICES,
    BOOT_RESOURCE_TYPE_CHOICES_DICT,
)
from maasserver.fields import JSONObjectField
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import (
    now,
    TimestampedModel,
)
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
            if (resource_set is not None and
                    resource_set.commissionable and
                    resource_set.installable):
                arch, _ = resource.split_arch()
                if 'kflavor' in resource.extra:
                    arches.add('%s/%s' % (arch, resource.extra['kflavor']))
        return sorted(arches)

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

    def get_resource_for(
            self, osystem, architecture, subarchitecture, series):
        """Return resource that support the given osystem, architecture,
        subarchitecture, and series."""
        name = '%s/%s' % (osystem, series)
        resources = BootResource.objects.filter(
            rtype__in=RTYPE_REQUIRING_OS_SERIES_NAME,
            name=name, architecture__startswith=architecture)
        for resource in resources:
            if resource.supports_subarch(subarchitecture):
                return resource
        return None

    def get_resources_matching_boot_images(self, images):
        """Return `BootResource` that match the given images."""
        resources = BootResource.objects.all()
        matched_resources = set()
        for image in images:
            if image['osystem'] != 'custom':
                rtypes = [
                    BOOT_RESOURCE_TYPE.SYNCED,
                    BOOT_RESOURCE_TYPE.GENERATED,
                    ]
                name = '%s/%s' % (image['osystem'], image['release'])
            else:
                rtypes = [BOOT_RESOURCE_TYPE.UPLOADED]
                name = image['release']
            matching_resources = resources.filter(
                rtype__in=rtypes, name=name,
                architecture__startswith=image['architecture'])
            for resource in matching_resources:
                if resource is None:
                    # This shouldn't happen at all, but just to be sure.
                    continue
                if not resource.supports_subarch(image['subarchitecture']):
                    # This matching resource doesn't support the images
                    # subarchitecture, so its not a matching resource.
                    continue
                resource_set = resource.get_latest_complete_set()
                if resource_set is None:
                    # Possible that the import just started, and there is no
                    # set. Making it not a matching resource, as it cannot
                    # exist on the cluster unless it has a set.
                    continue
                if resource_set.label != image['label']:
                    # The label is different so the cluster has a different
                    # version of this set.
                    continue
                matched_resources.add(resource)
        return list(matched_resources)

    def boot_images_are_in_sync(self, images):
        """Return True if the given images match items in the `BootResource`
        table."""
        resources = BootResource.objects.all()
        matched_resources = self.get_resources_matching_boot_images(images)
        if len(matched_resources) == 0 and len(images) > 0:
            # If there are images, but no resources then there is a mismatch.
            return False
        if len(matched_resources) != resources.count():
            # If not all resources have been matched then there is a mismatch.
            return False
        return True

    def get_usable_hwe_kernels(self, name=None, architecture=None):
        """Return the set of usable kernels for architecture and release."""
        if not name:
            name = ''
        if not architecture:
            architecture = ''
        kernels = set()
        for resource in self.filter(
                architecture__startswith=architecture, name__startswith=name):
            resource_set = resource.get_latest_set()
            if(resource_set is None or
               not resource_set.commissionable or
               not resource_set.installable):
                continue
            subarch = resource.split_arch()[1]
            if subarch.startswith("hwe-"):
                kernels.add(subarch)
            if "subarches" in resource.extra:
                for subarch in resource.extra["subarches"].split(","):
                    if subarch.startswith("hwe-"):
                        kernels.add(subarch)
        return sorted(kernels)

    def get_kpackage_for_node(self, node):
        """Return the kernel package name for the kernel specified."""
        if not node.hwe_kernel:
            return None
        arch = node.split_arch()[0]
        os_release = node.get_osystem() + '/' + node.get_distro_series()
        # Before hwe_kernel was introduced the subarchitecture was the
        # hwe_kernel simple stream still uses this convention
        hwe_arch = arch + '/' + node.hwe_kernel

        resource = self.filter(name=os_release, architecture=hwe_arch).first()
        if resource:
            latest_set = resource.get_latest_set()
            if latest_set:
                kernel = latest_set.files.filter(
                    filetype=BOOT_RESOURCE_FILE_TYPE.BOOT_KERNEL).first()
                if kernel and 'kpackage' in kernel.extra:
                    return kernel.extra['kpackage']
        return None


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

    def __unicode__(self):
        return "<BootResource name=%s, arch=%s>" % (
            self.name, self.architecture)

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

    def get_next_version_name(self):
        """Return the version a `BootResourceSet` should use when adding to
        this resource.

        The version naming is specific to how the resource sets will be sorted
        by simplestreams. The version name is YYYYmmdd, with an optional
        revision index. (e.g. 20140822.1)

        This method gets the current date, and checks if a revision already
        exists in the database. If it doesn't then just the current date is
        returned. If it does exists then the next revision in the set for that
        date will be returned.

        :return: Name of version to use for a new set on this `BootResource`.
        :rtype: string
        """
        version_name = now().strftime('%Y%m%d')
        sets = self.sets.filter(
            version__startswith=version_name).order_by('version')
        if not sets.exists():
            return version_name
        max_idx = 0
        for resource_set in sets:
            if '.' in resource_set.version:
                _, set_idx = resource_set.version.split('.')
                set_idx = int(set_idx)
                if set_idx > max_idx:
                    max_idx = set_idx
        return '%s.%d' % (version_name, max_idx + 1)

    def supports_subarch(self, subarch):
        """Return True if the resource supports the given subarch."""
        _, self_subarch = self.split_arch()
        if subarch == self_subarch:
            return True
        if 'subarches' not in self.extra:
            return False
        subarches = self.extra['subarches'].split(',')
        return subarch in subarches
