# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `BootResource`."""


from collections.abc import Iterable
import random

from django.core.exceptions import ValidationError
from django.utils import timezone

from maasserver.enum import (
    BOOT_RESOURCE_FILE_TYPE,
    BOOT_RESOURCE_TYPE,
    BOOT_RESOURCE_TYPE_CHOICES_DICT,
)
from maasserver.models import bootresource, EventType
from maasserver.models.bootresource import (
    BootResource,
    get_boot_resources_last_deployments,
)
from maasserver.models.config import Config
from maasserver.models.signals import bootsources
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from provisioningserver.events import EVENT_TYPES
from provisioningserver.testing.os import make_osystem


class TestBootResourceManager(MAASServerTestCase):
    """Tests for the `BootResource` model manager."""

    def setUp(self):
        super().setUp()
        self.region = factory.make_RegionController()

    def make_boot_resource(self, rtype, name):
        arch = factory.make_name("arch")
        subarch = factory.make_name("subarch")
        architecture = f"{arch}/{subarch}"
        resource = factory.make_BootResource(
            rtype=rtype, name=name, architecture=architecture
        )
        return resource, (arch, subarch)

    def make_synced_boot_resource(self):
        os = factory.make_name("os")
        series = factory.make_name("series")
        name = f"{os}/{series}"
        resource, (arch, subarch) = self.make_boot_resource(
            BOOT_RESOURCE_TYPE.SYNCED, name=name
        )
        return resource, (os, arch, subarch, series)

    def make_uploaded_boot_resource(self):
        name = factory.make_name("name")
        resource, (arch, subarch) = self.make_boot_resource(
            BOOT_RESOURCE_TYPE.UPLOADED, name=name
        )
        return resource, (name, arch, subarch)

    def test_has_synced_resource_returns_true_when_exists(self):
        _, args = self.make_synced_boot_resource()
        self.assertTrue(BootResource.objects.has_synced_resource(*args))

    def test_has_synced_resource_returns_false_when_doesnt_exists(self):
        os = factory.make_name("os")
        series = factory.make_name("series")
        arch = factory.make_name("arch")
        subarch = factory.make_name("subarch")
        self.assertFalse(
            BootResource.objects.has_synced_resource(os, arch, subarch, series)
        )

    def test_get_synced_resource_returns_resource_when_exists(self):
        resource, args = self.make_synced_boot_resource()
        self.assertEqual(
            resource, BootResource.objects.get_synced_resource(*args)
        )

    def test_get_synced_resource_returns_None_when_doesnt_exists(self):
        os = factory.make_name("os")
        series = factory.make_name("series")
        arch = factory.make_name("arch")
        subarch = factory.make_name("subarch")
        self.assertEqual(
            None,
            BootResource.objects.get_synced_resource(
                os, arch, subarch, series
            ),
        )

    def test_has_uploaded_resource_returns_true_when_exists(self):
        _, args = self.make_uploaded_boot_resource()
        self.assertTrue(BootResource.objects.has_uploaded_resource(*args))

    def test_has_uploaded_resource_returns_false_when_doesnt_exists(self):
        name = factory.make_name("name")
        arch = factory.make_name("arch")
        subarch = factory.make_name("subarch")
        self.assertFalse(
            BootResource.objects.has_uploaded_resource(name, arch, subarch)
        )

    def test_get_uploaded_resource_returns_resource_when_exists(self):
        resource, args = self.make_uploaded_boot_resource()
        self.assertEqual(
            resource, BootResource.objects.get_uploaded_resource(*args)
        )

    def test_get_uploaded_resource_returns_None_when_doesnt_exists(self):
        name = factory.make_name("name")
        arch = factory.make_name("arch")
        subarch = factory.make_name("subarch")
        self.assertEqual(
            None,
            BootResource.objects.get_uploaded_resource(name, arch, subarch),
        )

    def test_get_usable_architectures(self):
        arches = [
            f"{factory.make_name('arch')}/{factory.make_name('subarch')}"
            for _ in range(4)
        ]
        incomplete_arch = arches.pop()
        factory.make_incomplete_boot_resource(architecture=incomplete_arch)
        for arch in arches:
            factory.make_usable_boot_resource(
                architecture=arch,
                platform=None,
                supported_platforms=None,
            )
        usable_arches = BootResource.objects.get_usable_architectures()
        self.assertIsInstance(usable_arches, list)
        self.assertCountEqual(arches, usable_arches)

    def test_get_usable_architectures_combines_subarches(self):
        arches = set()
        for _ in range(3):
            arch = factory.make_name("arch")
            subarches = [factory.make_name("subarch") for _ in range(3)]
            architecture = f"{arch}/{subarches[0]}"
            for subarch in subarches:
                arches.add(f"{arch}/{subarch}")
            factory.make_usable_boot_resource(
                architecture=architecture,
                extra={"subarches": ",".join(subarches)},
                platform=None,
                supported_platforms=None,
            )
        usable_arches = BootResource.objects.get_usable_architectures()
        self.assertIsInstance(usable_arches, list)
        self.assertCountEqual(arches, usable_arches)

    def test_get_usable_architectures_supports_platform(self):
        arches = set()
        for _ in range(3):
            arch = factory.make_name("arch")
            platform = [factory.make_name("platform") for _ in range(3)]
            for i, platform in enumerate(platform):
                arches.add(f"{arch}/{platform}")
                arches.add(f"{arch}/{platform}-supported")
                arches.add(f"{arch}/{platform}-also-supported")
                factory.make_usable_boot_resource(
                    architecture=f"{arch}/hwe-{i}",
                    platform=platform,
                    supported_platforms=f"{platform}-supported,{platform}-also-supported",
                )
        usable_arches = BootResource.objects.get_usable_architectures()
        self.assertIsInstance(usable_arches, list)
        self.assertCountEqual(arches, usable_arches)

    def test_get_kernels_doesnt_include_all_subarches(self):
        factory.make_usable_boot_resource(
            architecture="amd64/hwe-16.04",
            extra={"subarches": "hwe-p,hwe-t,hwe-16.04,hwe-16.10"},
        )
        self.assertEqual(["hwe-16.04"], BootResource.objects.get_kernels())

    def test_get_supported_kernel_compatibility_levels_includes_all_subarches(
        self,
    ):
        factory.make_usable_boot_resource(
            architecture="amd64/hwe-16.04",
            extra={"subarches": "hwe-p,hwe-t,hwe-16.04,hwe-16.10"},
        )
        self.assertEqual(
            ["hwe-p", "hwe-t", "hwe-16.04", "hwe-16.10"],
            BootResource.objects.get_supported_kernel_compatibility_levels(),
        )

    def test_get_commissionable_resource_returns_iterable(self):
        os = factory.make_name("os")
        series = factory.make_name("series")
        name = f"{os}/{series}"
        factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED, name=name
        )
        commissionables = BootResource.objects.get_commissionable_resource(
            os, series
        )
        self.assertIsInstance(commissionables, Iterable)

    def test_get_commissionable_resource_returns_only_commissionable(self):
        os = factory.make_name("os")
        series = factory.make_name("series")
        name = f"{os}/{series}"
        resource = factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED, name=name
        )
        factory.make_incomplete_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED, name=name
        )
        not_commissionable = factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED, name=name
        )
        factory.make_BootResourceSet(not_commissionable)
        commissionables = BootResource.objects.get_commissionable_resource(
            os, series
        )
        self.assertEqual([resource], list(commissionables))

    def test_get_commissionable_resource_returns_only_for_os_series(self):
        os = factory.make_name("os")
        series = factory.make_name("series")
        name = f"{os}/{series}"
        resource = factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED, name=name
        )
        factory.make_usable_boot_resource()
        commissionables = BootResource.objects.get_commissionable_resource(
            os, series
        )
        self.assertCountEqual([resource], commissionables)

    def test_get_commissionable_resource_returns_sorted_by_architecture(self):
        os = factory.make_name("os")
        series = factory.make_name("series")
        name = f"{os}/{series}"
        resource_b = factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name=name,
            architecture="b/generic",
        )
        resource_a = factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name=name,
            architecture="a/generic",
        )
        resource_c = factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name=name,
            architecture="c/generic",
        )
        commissionables = BootResource.objects.get_commissionable_resource(
            os, series
        )
        self.assertEqual(
            [resource_a, resource_b, resource_c], list(commissionables)
        )

    def test_get_default_commissioning_resource_returns_i386_first(self):
        os = factory.make_name("os")
        series = factory.make_name("series")
        name = f"{os}/{series}"
        arches = ["i386/generic", "amd64/generic", "arm64/generic"]
        for arch in arches:
            factory.make_usable_boot_resource(
                rtype=BOOT_RESOURCE_TYPE.SYNCED,
                name=name,
                architecture=arch,
            )
        self.assertEqual(
            "i386/generic",
            BootResource.objects.get_default_commissioning_resource(
                os, series
            ).architecture,
        )

    def test_get_default_commissioning_resource_returns_amd64_second(self):
        os = factory.make_name("os")
        series = factory.make_name("series")
        name = f"{os}/{series}"
        arches = ["amd64/generic", "arm64/generic"]
        for arch in arches:
            factory.make_usable_boot_resource(
                rtype=BOOT_RESOURCE_TYPE.SYNCED,
                name=name,
                architecture=arch,
            )
        self.assertEqual(
            "amd64/generic",
            BootResource.objects.get_default_commissioning_resource(
                os, series
            ).architecture,
        )

    def test_get_default_commissioning_resource_returns_first_arch(self):
        os = factory.make_name("os")
        series = factory.make_name("series")
        name = f"{os}/{series}"
        arches = ["ppc64el/generic", "arm64/generic"]
        for arch in arches:
            factory.make_usable_boot_resource(
                rtype=BOOT_RESOURCE_TYPE.SYNCED,
                name=name,
                architecture=arch,
            )
        self.assertEqual(
            "arm64/generic",
            BootResource.objects.get_default_commissioning_resource(
                os, series
            ).architecture,
        )

    def test_get_resource_for_returns_matching_resource(self):
        resources = [
            factory.make_BootResource(rtype=BOOT_RESOURCE_TYPE.SYNCED)
            for _ in range(3)
        ]
        resource = resources.pop()
        subarches = [factory.make_name("subarch") for _ in range(3)]
        subarch = random.choice(subarches)
        extra = resource.extra.copy()
        extra["subarches"] = ",".join(subarches)
        resource.extra = extra
        resource.save()
        osystem, series = resource.name.split("/")
        arch, _ = resource.split_arch()
        self.assertEqual(
            resource,
            BootResource.objects.get_resource_for(
                osystem, arch, subarch, series
            ),
        )

    def test_get_resource_for_returns_custom_resource(self):
        factory.make_BootResource(rtype=BOOT_RESOURCE_TYPE.SYNCED)
        factory.make_BootResource(rtype=BOOT_RESOURCE_TYPE.SYNCED)
        custom = factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
            name=factory.make_name(),
            base_image=factory.make_name("ubuntu", "/"),
        )
        subarches = [factory.make_name("subarch") for _ in range(3)]
        subarch = random.choice(subarches)
        extra = custom.extra.copy()
        extra["subarches"] = ",".join(subarches)
        custom.extra = extra
        custom.save()
        osystem = "custom"
        series = custom.name
        arch, _ = custom.split_arch()
        self.assertEqual(
            custom,
            BootResource.objects.get_resource_for(
                osystem, arch, subarch, series
            ),
        )


class TestGetAvailableCommissioningResources(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        self.region = factory.make_RegionController()
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

    def test_returns_empty_if_no_cache(self):
        release = factory.make_name("release")
        name = "ubuntu/%s" % release
        factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED, name=name
        )
        self.assertEqual(
            [], BootResource.objects.get_available_commissioning_resources()
        )

    def test_returns_empty_if_no_lts(self):
        release = factory.make_name("release")
        name = "ubuntu/%s" % release
        support_eol = factory.make_date().strftime("%Y-%m-%d")
        factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED, name=name
        )
        factory.make_BootSourceCache(
            os="ubuntu",
            release=release,
            release_title=release,
            support_eol=support_eol,
        )
        self.assertEqual(
            [], BootResource.objects.get_available_commissioning_resources()
        )

    def test_returns_only_lts(self):
        release = factory.make_name("release")
        name = "ubuntu/%s" % release
        support_eol = factory.make_date().strftime("%Y-%m-%d")
        release_title = "%s LTS" % release
        resource = factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED, name=name
        )
        factory.make_BootSourceCache(
            os="ubuntu",
            release=release,
            release_title=release_title,
            support_eol=support_eol,
        )
        other_release = factory.make_name("release")
        other_name = "ubuntu/%s" % other_release
        other_support_eol = factory.make_date().strftime("%Y-%m-%d")
        factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED, name=other_name
        )
        factory.make_BootSourceCache(
            os="ubuntu",
            release=other_release,
            release_title=other_release,
            support_eol=other_support_eol,
        )
        self.assertEqual(
            [resource],
            BootResource.objects.get_available_commissioning_resources(),
        )

    def test_returns_longest_remaining_supported_lts_first(self):
        trusty_resource = factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED, name="ubuntu/trusty"
        )
        factory.make_BootSourceCache(
            os="ubuntu",
            release="trusty",
            release_title="14.04 LTS",
            support_eol="2019-04-17",
        )
        xenial_resource = factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED, name="ubuntu/xenial"
        )
        factory.make_BootSourceCache(
            os="ubuntu",
            release="xenial",
            release_title="16.04 LTS",
            support_eol="2021-04-17",
        )
        self.assertEqual(
            [xenial_resource, trusty_resource],
            BootResource.objects.get_available_commissioning_resources(),
        )


class TestGetKernels(MAASServerTestCase):
    """Tests for `get_kernels`."""

    scenarios = (
        (
            "ubuntu/trusty",
            {
                "name": "ubuntu/trusty",
                "arch": "amd64",
                "subarch": "generic",
                "kernels": ["hwe-t", "hwe-u", "hwe-v", "hwe-rolling"],
            },
        ),
        (
            "ubuntu/vivid",
            {
                "name": "ubuntu/vivid",
                "arch": "i386",
                "subarch": "generic",
                "kernels": ["hwe-v", "hwe-rolling"],
            },
        ),
        (
            "ubuntu/precise",
            {
                "name": "ubuntu/precise",
                "arch": "armfh",
                "subarch": "generic",
                "kernels": ["hwe-p", "hwe-t", "hwe-v", "hwe-rolling"],
            },
        ),
        (
            "ubuntu/wily",
            {
                "name": "ubuntu/wily",
                "arch": "armfh",
                "subarch": "hardbank",
                "kernels": [],
            },
        ),
        (
            "ubuntu/xenial",
            {
                "name": "ubuntu/xenial",
                "arch": "amd64",
                "subarch": "generic",
                "kernels": [
                    "hwe-16.04",
                    "hwe-16.04-lowlatency",
                    "hwe-rolling",
                    "hwe-rolling-lowlatency",
                ],
            },
        ),
    )

    def setUp(self):
        super().setUp()
        self.region = factory.make_RegionController()

    def test_returns_usable_kernels(self):
        if self.subarch == "generic":
            generic_kernels = []
            for i in self.kernels:
                kernel_parts = i.split("-")
                if len(kernel_parts) > 2:
                    kflavor = kernel_parts[2]
                else:
                    kflavor = "generic"
                    generic_kernels.append(i)
                factory.make_usable_boot_resource(
                    name=self.name,
                    rtype=BOOT_RESOURCE_TYPE.SYNCED,
                    architecture=f"{self.arch}/{i}",
                    kflavor=kflavor,
                    rolling=True,
                    platform=None,
                    supported_platforms=None,
                )
                factory.make_incomplete_boot_resource(
                    name=self.name,
                    rtype=BOOT_RESOURCE_TYPE.SYNCED,
                    architecture="%s/%s"
                    % (self.arch, factory.make_name("incomplete")),
                    kflavor=kflavor,
                )
        else:
            generic_kernels = self.kernels
            factory.make_usable_boot_resource(
                name=self.name,
                rtype=BOOT_RESOURCE_TYPE.SYNCED,
                architecture=f"{self.arch}/{self.subarch}",
                rolling=True,
                platform=None,
                supported_platforms=None,
            )
        self.assertCountEqual(
            self.kernels,
            BootResource.objects.get_kernels(self.name, self.arch),
            "%s should return %s as its usable kernel"
            % (self.name, self.kernels),
        )
        self.assertEqual(
            generic_kernels,
            BootResource.objects.get_kernels(
                name=self.name,
                architecture=self.arch,
                platform=None,
                kflavor="generic",
            ),
            "%s should return %s as its usable kernel"
            % (self.name, generic_kernels),
        )


class TestGetKpackageForNode(MAASServerTestCase):
    """Tests for `get_kpackage_for_node`."""

    def setUp(self):
        super().setUp()
        self.region = factory.make_RegionController()

    def test_returns_kpackage(self):
        resource = factory.make_BootResource(
            name="ubuntu/trusty",
            architecture="amd64/hwe-t",
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
        )
        resource_set = factory.make_BootResourceSet(resource)
        factory.make_boot_resource_file_with_content(
            resource_set,
            filename="boot-kernel",
            filetype="boot-kernel",
            extra={"kpackage": "linux-image-generic-lts-trusty"},
            synced=[(self.region, -1)],
        )
        node = factory.make_Node(
            interface=True,
            power_type="manual",
            osystem="ubuntu",
            distro_series="trusty",
            architecture="amd64/generic",
            hwe_kernel="hwe-t",
        )
        self.assertEqual(
            "linux-image-generic-lts-trusty",
            BootResource.objects.get_kpackage_for_node(node),
        )

    def test_returns_hwe_rolling(self):
        node = factory.make_Node()
        for hwe_kernel, kpackage in (
            ["hwe-rolling", "linux-generic-hwe-rolling"],
            ["hwe-rolling-lowlatency", "linux-lowlatency-hwe-rolling"],
            ["hwe-rolling-edge", "linux-generic-hwe-rolling-edge"],
            [
                "hwe-rolling-lowlatency-edge",
                "linux-lowlatency-hwe-rolling-edge",
            ],
        ):
            node.hwe_kernel = hwe_kernel
            self.assertEqual(
                kpackage, BootResource.objects.get_kpackage_for_node(node)
            )

    def test_returns_none(self):
        node = factory.make_Node()
        self.assertIsNone(BootResource.objects.get_kpackage_for_node(node))


class TestGetKparamsForNode(MAASServerTestCase):
    """Tests for `get_kparams_for_node`."""

    def setUp(self):
        super().setUp()
        self.region = factory.make_RegionController()

    def test_returns_kpackage(self):
        resource = factory.make_BootResource(
            name="ubuntu/trusty",
            architecture="amd64/hwe-t",
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
        )
        resource_set = factory.make_BootResourceSet(resource)
        factory.make_boot_resource_file_with_content(
            resource_set,
            filename="boot-kernel",
            filetype="boot-kernel",
            extra={
                "kpackage": "linux-image-generic-lts-trusty",
                "kparams": "a=b",
            },
            synced=[(self.region, -1)],
        )
        node = factory.make_Node(
            interface=True,
            power_type="manual",
            osystem="ubuntu",
            distro_series="trusty",
            architecture="amd64/generic",
            hwe_kernel="hwe-t",
        )
        self.assertEqual(
            "a=b", BootResource.objects.get_kparams_for_node(node)
        )

    def test_returns_none(self):
        node = factory.make_Node()
        self.assertIsNone(BootResource.objects.get_kparams_for_node(node))


class TestBootResource(MAASServerTestCase):
    """Tests for the `BootResource` model."""

    def setUp(self):
        super().setUp()
        self.region = factory.make_RegionController()

    def make_complete_boot_resource_set(self, resource):
        resource_set = factory.make_BootResourceSet(resource)
        filename = factory.make_name("name")
        filetype = factory.pick_enum(BOOT_RESOURCE_FILE_TYPE)
        factory.make_boot_resource_file_with_content(
            resource_set,
            filename=filename,
            filetype=filetype,
            synced=[(self.region, -1)],
        )
        return resource_set

    def test_validation_raises_error_on_missing_subarch(self):
        arch = factory.make_name("arch")
        self.assertRaises(
            ValidationError, factory.make_BootResource, architecture=arch
        )

    def test_validation_raises_error_on_invalid_name_for_synced(self):
        name = factory.make_name("name")
        arch = "{}/{}".format(
            factory.make_name("arch"),
            factory.make_name("subarch"),
        )
        resource = BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED, name=name, architecture=arch
        )
        self.assertRaises(ValidationError, resource.save)

    def test_validation_raises_error_on_invalid_name_for_uploaded(self):
        name = "{}/{}".format(
            factory.make_name("os"), factory.make_name("series")
        )
        arch = "{}/{}".format(
            factory.make_name("arch"),
            factory.make_name("subarch"),
        )
        resource = BootResource(
            rtype=BOOT_RESOURCE_TYPE.UPLOADED, name=name, architecture=arch
        )
        self.assertRaises(ValidationError, resource.save)

    def test_validation_allows_any_uploaded_name_slash_with_supported_os(self):
        osystem = factory.make_name("osystem")
        make_osystem(self, osystem)
        name = "{}/{}".format(osystem, factory.make_name("release"))
        arch = "{}/{}".format(
            factory.make_name("arch"),
            factory.make_name("subarch"),
        )
        resource = BootResource(
            rtype=BOOT_RESOURCE_TYPE.UPLOADED, name=name, architecture=arch
        )
        resource.save()

    def test_validation_allows_any_uploaded_name_without_slash(self):
        name = factory.make_name("name")
        arch = "{}/{}".format(
            factory.make_name("arch"),
            factory.make_name("subarch"),
        )
        resource = BootResource(
            rtype=BOOT_RESOURCE_TYPE.UPLOADED, name=name, architecture=arch
        )
        resource.save()

    def test_create_raises_error_on_not_unique(self):
        name = "{}/{}".format(
            factory.make_name("os"), factory.make_name("series")
        )
        arch = "{}/{}".format(
            factory.make_name("arch"),
            factory.make_name("subarch"),
        )
        factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED, name=name, architecture=arch
        )
        self.assertRaises(
            ValidationError,
            factory.make_BootResource,
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
            name=name,
            architecture=arch,
        )

    def test_display_rtype(self):
        for key, value in BOOT_RESOURCE_TYPE_CHOICES_DICT.items():
            resource = BootResource(rtype=key)
            self.assertEqual(value, resource.display_rtype)

    def test_split_arch(self):
        arch = factory.make_name("arch")
        subarch = factory.make_name("subarch")
        architecture = f"{arch}/{subarch}"
        resource = factory.make_BootResource(architecture=architecture)
        self.assertEqual((arch, subarch), resource.split_arch())

    def test_get_latest_set(self):
        resource = factory.make_BootResource()
        factory.make_BootResourceSet(resource)
        latest_two = factory.make_BootResourceSet(resource)
        self.assertEqual(latest_two, resource.get_latest_set())

    def test_get_latest_complete_set(self):
        resource = factory.make_BootResource()
        factory.make_BootResourceSet(resource)
        self.make_complete_boot_resource_set(resource)
        latest_complete = self.make_complete_boot_resource_set(resource)
        factory.make_BootResourceSet(resource)
        self.assertEqual(latest_complete, resource.get_latest_complete_set())

    def configure_now(self):
        now = timezone.now()
        self.patch(bootresource, "now").return_value = now
        return now.strftime("%Y%m%d")

    def test_get_next_version_name_returns_current_date(self):
        expected_version = self.configure_now()
        resource = factory.make_BootResource()
        self.assertEqual(expected_version, resource.get_next_version_name())

    def test_get_next_version_name_returns_first_revision(self):
        expected_version = "%s.1" % self.configure_now()
        resource = factory.make_BootResource()
        factory.make_BootResourceSet(
            resource, version=resource.get_next_version_name()
        )
        self.assertEqual(expected_version, resource.get_next_version_name())

    def test_get_next_version_name_returns_later_revision(self):
        expected_version = self.configure_now()
        set_count = random.randint(2, 4)
        resource = factory.make_BootResource()
        for _ in range(set_count):
            factory.make_BootResourceSet(
                resource, version=resource.get_next_version_name()
            )
        self.assertEqual(
            "%s.%d" % (expected_version, set_count),
            resource.get_next_version_name(),
        )

    def test_supports_subarch_returns_True_if_subarch_in_name_matches(self):
        arch = factory.make_name("arch")
        subarch = factory.make_name("subarch")
        architecture = f"{arch}/{subarch}"
        resource = factory.make_BootResource(architecture=architecture)
        self.assertTrue(resource.supports_subarch(subarch))

    def test_supports_subarch_returns_False_if_subarches_is_missing(self):
        resource = factory.make_BootResource()
        self.assertFalse(
            resource.supports_subarch(factory.make_name("subarch"))
        )

    def test_supports_subarch_returns_True_if_subarch_in_subarches(self):
        subarches = [factory.make_name("subarch") for _ in range(3)]
        subarch = random.choice(subarches)
        resource = factory.make_BootResource(
            extra={"subarches": ",".join(subarches)}
        )
        self.assertTrue(resource.supports_subarch(subarch))

    def test_supports_subarch_returns_False_if_subarch_not_in_subarches(self):
        subarches = [factory.make_name("subarch") for _ in range(3)]
        resource = factory.make_BootResource(
            extra={"subarches": ",".join(subarches)}
        )
        self.assertFalse(
            resource.supports_subarch(factory.make_name("subarch"))
        )

    def test_split_base_image_handles_no_base_image(self):
        resource = factory.make_BootResource()
        resource.base_image = None
        cfg = Config.objects.get_configs(
            ["commissioning_osystem", "commissioning_distro_series"]
        )
        self.assertCountEqual(
            (cfg["commissioning_osystem"], cfg["commissioning_distro_series"]),
            resource.split_base_image(),
        )

    def test_get_boot_resources_last_deployments(self):
        os = factory.make_name("os")
        series = factory.make_name("series")
        name = f"{os}/{series}"
        arch_one = factory.make_name("arch")
        arch_two = factory.make_name("arch")
        event_description_str_one = f"deployed {name}/{arch_one}/generic"
        event_description_str_two = f"deployed {name}/{arch_two}/generic"

        event_one = factory.make_Event(
            type=factory.make_EventType(name=EVENT_TYPES.IMAGE_DEPLOYED),
            description=f"{event_description_str_one}",
        )
        event_two = factory.make_Event(
            type=EventType.objects.get(name=EVENT_TYPES.IMAGE_DEPLOYED),
            description=f"{event_description_str_two}",
        )

        _ = factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name=name,
            architecture=f"{arch_one}/generic",
        )
        _ = factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name=name,
            architecture=f"{arch_two}/generic",
        )

        last_deployments = get_boot_resources_last_deployments()
        self.assertEqual(
            last_deployments[f"{name}/{arch_one}"], event_one.created
        )
        self.assertEqual(
            last_deployments[f"{name}/{arch_two}"], event_two.created
        )

    def test_get_boot_resources_last_deployments_many_subarchs(self):
        os = factory.make_name("os")
        series = factory.make_name("series")
        name = f"{os}/{series}"
        arch = factory.make_name("arch")
        subarch_one = factory.make_name("subarch_one")
        subarch_two = factory.make_name("subarch_two")
        architecture_one = f"{arch}/{subarch_one}"
        architecture_two = f"{arch}/{subarch_two}"
        event_description_str_one = f"deployed {name}/{architecture_one}"
        event_description_str_two = f"deployed {name}/{architecture_two}"

        event_one = factory.make_Event(
            type=factory.make_EventType(name=EVENT_TYPES.IMAGE_DEPLOYED),
            description=f"{event_description_str_one}",
        )
        event_two = factory.make_Event(
            type=EventType.objects.get(name=EVENT_TYPES.IMAGE_DEPLOYED),
            description=f"{event_description_str_one}",
        )
        event_three = factory.make_Event(
            type=EventType.objects.get(name=EVENT_TYPES.IMAGE_DEPLOYED),
            description=f"{event_description_str_two}",
        )

        _ = factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name=name,
            architecture=architecture_one,
        )
        _ = factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name=name,
            architecture=architecture_two,
        )

        last_deployments = get_boot_resources_last_deployments()
        self.assertNotEqual(
            last_deployments[f"{name}/{arch}"], event_one.created
        )
        self.assertNotEqual(
            last_deployments[f"{name}/{arch}"], event_two.created
        )
        self.assertEqual(
            last_deployments[f"{name}/{arch}"], event_three.created
        )

    def test_get_boot_resources_last_deployments_returns_None_if_no_deployments(
        self,
    ):
        os = factory.make_name("os")
        series = factory.make_name("series")
        name = f"{os}/{series}"
        arch = factory.make_name("arch")
        subarch = factory.make_name("subarch")
        architecture = f"{arch}/{subarch}"

        _ = factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name=name,
            architecture=architecture,
        )
        last_deployments = get_boot_resources_last_deployments()
        self.assertNotIn(f"{name}/{arch}", last_deployments)
