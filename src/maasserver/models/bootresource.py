# Copyright 2014-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Boot Resource."""
from datetime import datetime
from operator import attrgetter
from typing import Optional

from django.core.exceptions import ValidationError
from django.db.models import (
    BooleanField,
    CharField,
    Count,
    IntegerField,
    JSONField,
    Manager,
    OuterRef,
    Prefetch,
    Subquery,
    Sum,
)

from maasserver.enum import (
    BOOT_RESOURCE_FILE_TYPE,
    BOOT_RESOURCE_TYPE,
    BOOT_RESOURCE_TYPE_CHOICES,
    BOOT_RESOURCE_TYPE_CHOICES_DICT,
)
from maasserver.models.bootresourceset import BootResourceSet
from maasserver.models.bootsourcecache import BootSourceCache
from maasserver.models.cleansave import CleanSave
from maasserver.models.config import Config
from maasserver.models.timestampedmodel import now, TimestampedModel
from maasserver.utils.orm import get_first, get_one
from provisioningserver.drivers.osystem import OperatingSystemRegistry
from provisioningserver.utils.twisted import undefined

LINUX_OSYSTEMS = ("ubuntu", "centos", "rhel", "ol")


class BootResourceManager(Manager):
    def _has_resource(self, rtype, name, architecture, subarchitecture):
        """Return True if `BootResource` exists with given rtype, name,
        architecture, and subarchitecture."""
        arch = f"{architecture}/{subarchitecture}"
        return self.filter(rtype=rtype, name=name, architecture=arch).exists()

    def _get_resource(self, rtype, name, architecture, subarchitecture):
        """Return `BootResource` with given rtype, name, architecture, and
        subarchitecture."""
        arch = f"{architecture}/{subarchitecture}"
        return get_one(self.filter(rtype=rtype, name=name, architecture=arch))

    def has_synced_resource(
        self, osystem, architecture, subarchitecture, series
    ):
        """Return True if `BootResource` exists with type of SYNCED, and given
        osystem, architecture, subarchitecture, and series."""
        name = f"{osystem}/{series}"
        return self._has_resource(
            BOOT_RESOURCE_TYPE.SYNCED, name, architecture, subarchitecture
        )

    def get_synced_resource(
        self, osystem, architecture, subarchitecture, series
    ):
        """Return `BootResource` with type of SYNCED, and given
        osystem, architecture, subarchitecture, and series."""
        name = f"{osystem}/{series}"
        return self._get_resource(
            BOOT_RESOURCE_TYPE.SYNCED, name, architecture, subarchitecture
        )

    def has_uploaded_resource(self, name, architecture, subarchitecture):
        """Return True if `BootResource` exists with type of UPLOADED, and
        given name, architecture, and subarchitecture."""
        return self._has_resource(
            BOOT_RESOURCE_TYPE.UPLOADED, name, architecture, subarchitecture
        )

    def get_uploaded_resource(self, name, architecture, subarchitecture):
        """Return `BootResource` with type of UPLOADED, and given
        name, architecture, and subarchitecture."""
        return self._get_resource(
            BOOT_RESOURCE_TYPE.UPLOADED, name, architecture, subarchitecture
        )

    def get_usable_architectures(self):
        """Return the set of usable architectures.

        Return the architectures for which the resource has at least one
        commissioning image and at least one install image.
        """
        arches = set()
        for resource in self.all():
            resource_set = resource.get_latest_complete_set()
            if (
                resource_set is not None
                and resource_set.commissionable
                and resource_set.xinstallable
            ):
                if (
                    "hwe-" not in resource.architecture
                    and "ga-" not in resource.architecture
                ):
                    arches.add(resource.architecture)
                arch, _ = resource.split_arch()
                if "subarches" in resource.extra:
                    for subarch in resource.extra["subarches"].split(","):
                        if "hwe-" not in subarch and "ga-" not in subarch:
                            arches.add(f"{arch}/{subarch.strip()}")
                if "platform" in resource.extra:
                    arches.add(f"{arch}/{resource.extra['platform']}")
                if "supported_platforms" in resource.extra:
                    for platform in resource.extra[
                        "supported_platforms"
                    ].split(","):
                        arches.add(f"{arch}/{platform}")
        return sorted(arches)

    def get_commissionable_resource(self, osystem, series):
        """Return generator for all commissionable resources for the
        given osystem and series."""
        name = f"{osystem}/{series}"
        resources = self.filter(name=name).order_by("architecture")
        for resource in resources:
            resource_set = resource.get_latest_complete_set()
            if resource_set is not None and resource_set.commissionable:
                yield resource

    def get_default_commissioning_resource(self, osystem, series):
        """Return best guess `BootResource` for the given osystem and series.

        Prefers `i386` then `amd64` resources if available.  Returns `None`
        if none match requirements.
        """
        commissionable = list(
            self.get_commissionable_resource(osystem, series)
        )
        for resource in commissionable:
            # Prefer i386. It will work for most cases where we don't
            # know the actual architecture.
            arch, subarch = resource.split_arch()
            if arch == "i386":
                return resource
        for resource in commissionable:
            # Prefer amd64. It has a much better chance of working than
            # say arm or ppc.
            arch, subarch = resource.split_arch()
            if arch == "amd64":
                return resource
        return get_first(commissionable)

    def get_resource_for(
        self,
        osystem,
        architecture,
        subarchitecture,
        series,
        purpose=None,
    ):
        """Return resource that support the given osystem, architecture,
        subarchitecture, and series."""
        if purpose is not None:
            os_driver = OperatingSystemRegistry.get_item(osystem)
            if (
                os_driver is None
                or purpose not in os_driver.get_boot_image_purposes()
            ):
                return None

        if osystem != "custom":
            name = f"{osystem}/{series}"
            rtype = (BOOT_RESOURCE_TYPE.SYNCED, BOOT_RESOURCE_TYPE.UPLOADED)
        else:
            name = series
            rtype = (BOOT_RESOURCE_TYPE.UPLOADED,)

        resources = self.filter(
            rtype__in=rtype,
            name=name,
            architecture__startswith=architecture,
        ).all()
        for resource in resources:
            if resource.supports_subarch(
                subarchitecture
            ) or resource.supports_platform(subarchitecture):
                return resource
        return None

    def get_hwe_kernels(
        self,
        name=None,
        architecture=None,
        platform=None,
        kflavor=None,
        include_subarches=False,
        strict_platform_match=False,
    ):
        """Return the set of kernels.

        UPD: because of 3.4 transition from "subarches" to "platforms",
        expect some confusion ahead.
        """
        from maasserver.models.bootresourcefile import BootResourceFile
        from maasserver.utils.osystems import (
            get_release_version_from_string,
            parse_subarch_kernel_string,
        )

        if not name:
            name = ""
        if not architecture:
            architecture = ""

        # In order to calculate the sum of the bootresourcefilesync we have to FULL OUTER JOIN the tables and the rows are
        # duplicated: this is why we need a subquery to calculate the total files size.
        subquery = (
            BootResourceFile.objects.filter(resource_set_id=OuterRef("pk"))
            .values("resource_set_id")
            .annotate(group_size=Sum("size"))
            .values("group_size")[:1]
        )
        sets_prefetch = BootResourceSet.objects.annotate(
            files_count=Count("files__id", distinct=True),
            files_size=Subquery(subquery),
            sync_size=Sum("files__bootresourcefilesync__size"),
        )
        sets_prefetch = sets_prefetch.prefetch_related("files")
        sets_prefetch = sets_prefetch.order_by("id")
        query = self.filter(
            architecture__startswith=architecture, name__startswith=name
        )
        query = query.prefetch_related(Prefetch("sets", sets_prefetch))

        kernels = set()
        for resource in query:
            if kflavor is not None and resource.kflavor != kflavor:
                continue
            resource_set = resource.get_latest_complete_set()
            if (
                resource_set is None
                or not resource_set.commissionable
                or not resource_set.xinstallable
            ):
                continue
            subarch = resource.split_arch()[1]
            channel, _, kplatform, flavor = parse_subarch_kernel_string(
                subarch
            )

            old_style_platform = (
                not channel and platform and platform != "generic"
            )

            # Skip non-generic platform-specific kernels
            if platform:
                resource_platform = resource.extra.get("platform", kplatform)
                if not resource_platform:
                    # Somewhat reasonable assumption, since the
                    # `parse_subarch_kernel_string` will figure out
                    # platform from all kernels that are currently
                    # in the stream
                    resource_platform = "generic"

                resource_supported_platforms = resource.extra.get(
                    "supported_platforms", ""
                ).split(",")
                if resource_platform != platform and (
                    strict_platform_match
                    or platform not in resource_supported_platforms
                ):
                    continue

            if channel.startswith("hwe") or channel == "ga":
                kernels.add(subarch)
                if resource.rolling:
                    kernels.add(
                        "-".join(
                            (kplatform, channel, "rolling", flavor)
                        ).strip("-")
                    )
            elif old_style_platform:
                # TODO A hack to pass through the old-style platform kernels
                kernels.add(subarch)

            # Add resource compatibility levels to the set
            if include_subarches and "subarches" in resource.extra:
                for extra_subarch in resource.extra["subarches"].split(","):
                    channel, _, _, flavor = parse_subarch_kernel_string(
                        extra_subarch
                    )
                    # TODO This is a hack for old-style platform kernels
                    old_style_platform = (
                        not channel and platform and platform != "generic"
                    )
                    if (
                        channel != "ga"
                        and not channel.startswith("hwe")
                        and not old_style_platform
                    ):
                        continue

                    if kflavor is None:
                        kernels.add(extra_subarch)
                    elif flavor == "generic":
                        # generic kflavors are not included in the subarch.
                        kparts = extra_subarch.split("-")
                        if len(kparts) == 2:
                            kernels.add(extra_subarch)
                    elif flavor == kflavor:
                        kernels.add(extra_subarch)

        # Make sure kernels named with a version come after the kernels named
        # with the first letter of release. This switched in Xenial so this
        # preserves the chronological order of the kernels.
        return sorted(kernels, key=get_release_version_from_string)

    def get_kernels(
        self,
        name=None,
        architecture=None,
        platform=None,
        kflavor=None,
        strict_platform_match=False,
    ):
        """Return the set of usable kernels for the given name, arch,
        platform, and kflavor.

        Returns only the list of kernels which MAAS has downloaded. For example
        if Trusty and Xenial have been downloaded this will return hwe-t,
        ga-16.04, hwe-16.04, hwe-16.04-edge, hwe-16.04-lowlatency, and
        hwe-16.04-lowlatency-edge."""
        return self.get_hwe_kernels(
            name,
            architecture=architecture,
            platform=platform,
            kflavor=kflavor,
            include_subarches=False,
            strict_platform_match=strict_platform_match,
        )

    def get_supported_kernel_compatibility_levels(
        self, name=None, architecture=None, platform=None, kflavor=None
    ):
        """Return the set of supported kernels for the given name, arch,
        kflavor.

        Returns the list of kernels' "subarch" values for all downloaded
        kernels, as well as subarchitectures those kernels support.
        Think of it as a list of "compatibility levels", where each
        comma-separated value in "subarches" simplestream property
        is a separate compatibility level. Useful for setting minimal
        supported kernel version.

        For example if Trusty and Xenial have been
        downloaded this will return
            - ga-16.04
            - hwe-16.04
            - hwe-16.04-edge
            - hwe-16.04-lowlatency
            - hwe-16.04-lowlatency-edge (all these are values of "subarch" field)
            - hwe-[pqrstuvw] (all these are from "subarches" comma-separated list)
        """
        return self.get_hwe_kernels(
            name,
            architecture=architecture,
            platform=platform,
            kflavor=kflavor,
            include_subarches=True,
        )

    def get_kpackage_for_node(self, node):
        """Return the kernel package name for the kernel specified."""
        if not node.hwe_kernel:
            return None
        elif "hwe-rolling" in node.hwe_kernel:
            kparts = node.hwe_kernel.split("-")
            if kparts[-1] == "edge":
                if len(kparts) == 3:
                    kflavor = "generic"
                else:
                    kflavor = kparts[-2]
                return "linux-%s-hwe-rolling-edge" % kflavor
            else:
                if len(kparts) == 2:
                    kflavor = "generic"
                else:
                    kflavor = kparts[-1]
                return "linux-%s-hwe-rolling" % kflavor

        arch = node.split_arch()[0]
        os_release = node.get_osystem() + "/" + node.get_distro_series()
        # Before hwe_kernel was introduced the subarchitecture was the
        # hwe_kernel simple stream still uses this convention
        hwe_arch = arch + "/" + node.hwe_kernel

        resource = self.filter(name=os_release, architecture=hwe_arch).first()
        if resource:
            latest_set = resource.get_latest_complete_set()
            if latest_set:
                kernel = latest_set.files.filter(
                    filetype=BOOT_RESOURCE_FILE_TYPE.BOOT_KERNEL
                ).first()
                if kernel and "kpackage" in kernel.extra:
                    return kernel.extra["kpackage"]
        return None

    def get_kparams_for_node(
        self, node, default_osystem=undefined, default_distro_series=undefined
    ):
        """Return the kernel package name for the kernel specified."""
        arch = node.split_arch()[0]
        os_release = (
            node.get_osystem(default=default_osystem)
            + "/"
            + node.get_distro_series(default=default_distro_series)
        )

        # Before hwe_kernel was introduced the subarchitecture was the
        # hwe_kernel simple stream still uses this convention
        if node.hwe_kernel is None or node.hwe_kernel == "":
            hwe_arch = arch + "/generic"
        else:
            hwe_arch = arch + "/" + node.hwe_kernel

        resource = self.filter(name=os_release, architecture=hwe_arch).first()
        if resource:
            latest_set = resource.get_latest_set()
            if latest_set:
                kernel = latest_set.files.filter(
                    filetype=BOOT_RESOURCE_FILE_TYPE.BOOT_KERNEL
                ).first()
                if kernel and "kparams" in kernel.extra:
                    return kernel.extra["kparams"]
        return None

    def get_available_commissioning_resources(self):
        """Return list of Ubuntu boot resources that can be used for
        commissioning.

        Only return's LTS releases that have been fully imported.
        """
        # Get the LTS releases placing the release with the longest support
        # window first.
        lts_releases = BootSourceCache.objects.filter(
            os="ubuntu", release_title__endswith="LTS"
        )
        lts_releases = lts_releases.exclude(support_eol__isnull=True)
        lts_releases = lts_releases.order_by("-support_eol")
        lts_releases = lts_releases.values("release").distinct()
        lts_releases = [
            "ubuntu/%s" % release["release"] for release in lts_releases
        ]

        # Filter the completed and commissionable resources. The operation
        # loses the ordering of the releases.
        resources = []
        for resource in self.filter(
            rtype=BOOT_RESOURCE_TYPE.SYNCED, name__in=lts_releases
        ):
            resource_set = resource.get_latest_complete_set()
            if resource_set is not None and resource_set.commissionable:
                resources.append(resource)

        # Re-order placing the resource with the longest support window first.
        return sorted(
            resources, key=lambda resource: lts_releases.index(resource.name)
        )


def validate_architecture(value):
    """Validates that architecture value contains a subarchitecture."""
    if "/" not in value:
        raise ValidationError("Invalid architecture, missing subarchitecture.")


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
        BOOT_RESOURCE_TYPE.SYCNED, then its in the format of os/series.
    :ivar alias: The alias of the `BootResource` name. For example, `20.04` is
        the alias for `focal`. Bootloaders and custom images DO NOT have an alias.
    :ivar architecture: Architecture of the `BootResource`. It must be in
        the format arch/subarch.
    :ivar extra: Extra information about the file. This is only used
        for synced Ubuntu images.
    """

    class Meta:
        unique_together = (("name", "architecture", "alias"),)

    objects = BootResourceManager()

    rtype = IntegerField(choices=BOOT_RESOURCE_TYPE_CHOICES, editable=False)

    name = CharField(max_length=255, blank=False)

    alias = CharField(max_length=255, blank=True, null=True)

    base_image = CharField(max_length=255, blank=True)

    architecture = CharField(
        max_length=255, blank=False, validators=[validate_architecture]
    )

    bootloader_type = CharField(max_length=32, blank=True, null=True)

    kflavor = CharField(max_length=32, blank=True, null=True)

    # The hwe-rolling kernel is a meta-package which depends on the latest
    # kernel available. Instead of placing a duplicate kernel in the stream
    # SimpleStreams adds a boolean field to indicate that the hwe-rolling
    # kernel meta-package points to this kernel. When the rolling field is set
    # true MAAS allows users to deploy the hwe-rolling kernel by using this
    # BootResource kernel and instructs Curtin to install the meta-package.
    rolling = BooleanField(blank=False, null=False, default=False)

    extra = JSONField(blank=True, default=dict)

    def __str__(self):
        return (
            f"<BootResource name={self.name}, alias={self.alias}, arch={self.architecture}, "
            f"kflavor={self.kflavor}, base={self.base_image} "
            f"rtype={self.rtype}>"
        )

    @property
    def display_rtype(self):
        """Return rtype text as displayed to the user."""
        return BOOT_RESOURCE_TYPE_CHOICES_DICT[self.rtype]

    def clean(self):
        """Validate the model.

        Checks that the name is in a valid format, for its type.
        """
        if self.rtype == BOOT_RESOURCE_TYPE.UPLOADED:
            if "/" in self.name:
                os_name = self.name.split("/")[0]
                osystem = OperatingSystemRegistry.get_item(os_name)
                if osystem is None:
                    raise ValidationError(
                        "%s boot resource cannot contain a '/' in it's name "
                        "unless it starts with a supported operating system."
                        % (self.display_rtype)
                    )
        elif self.rtype == BOOT_RESOURCE_TYPE.SYNCED:
            if "/" not in self.name:
                raise ValidationError(
                    "%s boot resource must contain a '/' in it's name."
                    % (self.display_rtype)
                )

    def unique_error_message(self, model_class, unique_check):
        if unique_check == ("name", "architecture"):
            return "Boot resource of name, and architecture already exists."
        return super().unique_error_message(model_class, unique_check)

    def get_latest_set(self):
        """Return latest `BootResourceSet`."""
        if (
            not hasattr(self, "_prefetched_objects_cache")
            or "sets" not in self._prefetched_objects_cache
        ):
            return self.sets.order_by("id").last()
        elif self.sets.all():
            return sorted(self.sets.all(), key=attrgetter("id"), reverse=True)[
                0
            ]
        else:
            return None

    def get_latest_complete_set(self):
        """Return latest `BootResourceSet` where all `BootResouceFile`'s
        are complete."""
        from maasserver.models.bootresourcefile import BootResourceFile
        from maasserver.models.node import RegionController

        if (
            not hasattr(self, "_prefetched_objects_cache")
            or "sets" not in self._prefetched_objects_cache
        ):
            # In order to calculate the sum of the bootresourcefilesync we have to FULL OUTER JOIN the tables and the rows are
            # duplicated: this is why we need a subquery to calculate the total files size.
            subquery = (
                BootResourceFile.objects.filter(resource_set_id=OuterRef("pk"))
                .values("resource_set_id")
                .annotate(group_size=Sum("size"))
                .values("group_size")[:1]
            )
            resource_sets = self.sets.order_by("-id").annotate(
                files_count=Count("files__id", distinct=True),
                files_size=Subquery(subquery),
                sync_size=Sum("files__bootresourcefilesync__size"),
            )
        else:
            resource_sets = sorted(
                self.sets.all(), key=attrgetter("id"), reverse=True
            )
        n_regions = RegionController.objects.count()
        for resource_set in resource_sets:
            if resource_set.files_count > 0 and resource_set.sync_size == (
                n_regions * resource_set.files_size
            ):
                return resource_set
        return None

    def get_last_deploy(self) -> Optional[datetime]:
        from maasserver.models.event import Event
        from provisioningserver.events import EVENT_TYPES

        # Ignore subarch/platform/supported_platforms
        arch, _ = self.split_arch()
        deploy_msg_prefix = f"deployed {self.name}/{arch}/"
        if (
            event := Event.objects.filter(
                type__name=EVENT_TYPES.IMAGE_DEPLOYED,
                description__startswith=deploy_msg_prefix,
            )
            .only("created")
            .order_by("-created")[:1]
            .first()
        ):
            return event.created
        return None

    def split_arch(self) -> tuple[str, str]:
        return tuple(self.architecture.split("/", 1))

    def split_base_image(self) -> tuple[str, str]:
        # handle older custom images that may not have a base image
        if not self.base_image:
            cfg = Config.objects.get_configs(
                ["commissioning_osystem", "commissioning_distro_series"]
            )
            return (
                cfg["commissioning_osystem"],
                cfg["commissioning_distro_series"],
            )

        return tuple(self.base_image.split("/", 1))

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
        version_name = now().strftime("%Y%m%d")
        sets = self.sets.filter(version__startswith=version_name).order_by(
            "version"
        )
        if not sets.exists():
            return version_name
        max_idx = 0
        for resource_set in sets:
            if "." in resource_set.version:
                _, set_idx = resource_set.version.split(".")
                set_idx = int(set_idx)
                if set_idx > max_idx:
                    max_idx = set_idx
        return "%s.%d" % (version_name, max_idx + 1)

    def supports_subarch(self, subarch):
        """Return True if the resource supports the given subarch."""
        _, self_subarch = self.split_arch()
        if subarch == self_subarch:
            return True
        if "subarches" not in self.extra:
            return False
        subarches = self.extra["subarches"].split(",")
        return subarch in subarches

    def supports_platform(self, platform):
        """Return True if the resource supports the given platform."""
        _, self_subarch = self.split_arch()
        if platform == self_subarch:
            return True
        if platform == self.extra.get("platform"):
            return True
        if "supported_platforms" not in self.extra:
            return False
        platforms = self.extra["supported_platforms"].split(",")
        return platform in platforms
