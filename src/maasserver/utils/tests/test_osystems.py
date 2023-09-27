# Copyright 2014-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.utils.osystems`."""


from operator import attrgetter
import random

from distro_info import UbuntuDistroInfo
from django.core.exceptions import ValidationError

from maasserver.enum import BOOT_RESOURCE_FILE_TYPE, BOOT_RESOURCE_TYPE
from maasserver.models import BootResource, Config
from maasserver.models.signals.testing import SignalsDisabled
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.osystems import (
    FLAVOURED_WEIGHT,
    get_available_kernels_prioritising_platform,
    get_distro_series_initial,
    get_release_from_db,
    get_release_from_distro_info,
    get_release_requires_key,
    get_release_version_from_string,
    get_working_kernel,
    HWE_CHANNEL_WEIGHT,
    HWE_EDGE_CHANNEL_WEIGHT,
    InvalidSubarchKernelStringError,
    list_all_releases_requiring_keys,
    list_all_usable_osystems,
    list_commissioning_choices,
    list_osystem_choices,
    list_release_choices,
    make_hwe_kernel_ui_text,
    NEW_STYLE_KERNEL_WEIGHT,
    OLD_STYLE_HWE_WEIGHT,
    OperatingSystem,
    OSRelease,
    parse_subarch_kernel_string,
    ParsedKernelString,
    PLATFORM_ONLY_STRING_WEIGHT,
    PLATFORM_OPTIMISED_WEIGHT,
    release_a_newer_than_b,
    validate_min_hwe_kernel,
    validate_osystem_and_distro_series,
)
from maastesting.matchers import MockAnyCall
from maastesting.testcase import MAASTestCase


class TestOsystems(MAASServerTestCase):
    def test_list_all_usable_osystems(self):
        custom_os = factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
            extra={"title": factory.make_name("title")},
        )
        factory.make_default_ubuntu_release_bootable()
        # Bootloader to be ignored.
        factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED, bootloader_type="uefi"
        )

        osystems = list_all_usable_osystems()
        self.assertEqual(["custom", "ubuntu"], sorted(osystems.keys()))
        ubuntu = osystems["ubuntu"]
        custom = osystems["custom"]
        self.assertEqual("custom", custom.name)
        self.assertEqual("Custom", custom.title)
        self.assertIsNone(custom.default_commissioning_release)
        self.assertEqual("", custom.default_release)
        self.assertEqual([custom_os.name], list(custom.releases.keys()))
        custom_release = custom.releases[custom_os.name]
        self.assertEqual(custom_os.extra["title"], custom_release.title)
        self.assertFalse(custom_release.can_commission)
        self.assertFalse(custom_release.requires_license_key)

        self.assertEqual("ubuntu", ubuntu.name)
        self.assertEqual("Ubuntu", ubuntu.title)
        self.assertEqual("focal", ubuntu.default_commissioning_release)
        self.assertEqual("focal", ubuntu.default_release)
        self.assertEqual(["focal"], list(ubuntu.releases.keys()))
        self.assertEqual(
            'Ubuntu 20.04 LTS "Focal Fossa"', ubuntu.releases["focal"].title
        )
        self.assertTrue(ubuntu.releases["focal"].can_commission)
        self.assertFalse(ubuntu.releases["focal"].requires_license_key)

    def test_list_osystem_choices_includes_default(self):
        self.assertEqual(
            [("", "Default OS")],
            list_osystem_choices(
                list_all_usable_osystems(), include_default=True
            ),
        )

    def test_list_osystem_choices_doesnt_include_default(self):
        self.assertEqual(
            [],
            list_osystem_choices(
                list_all_usable_osystems(), include_default=False
            ),
        )

    def test_list_osystem_choices_uses_name_and_title(self):
        factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
        )
        self.assertEqual(
            [("custom", "Custom")],
            list_osystem_choices(
                list_all_usable_osystems(), include_default=False
            ),
        )

    def test_list_osystem_choices_doesnt_duplicate(self):
        factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
        )
        factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
        )
        self.assertEqual(
            [("custom", "Custom")],
            list_osystem_choices(
                list_all_usable_osystems(), include_default=False
            ),
        )

    def test_list_all_usable_osystems_can_deploy_to_memory(self):
        factory.make_usable_boot_resource(
            name="ubuntu/focal",
            architecture="amd64/generic",
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            image_filetype=BOOT_RESOURCE_FILE_TYPE.SQUASHFS_IMAGE,
        )
        factory.make_custom_boot_resource(
            name="rhel/9.1",
            architecture="amd64/generic",
            filetype=BOOT_RESOURCE_FILE_TYPE.ROOT_DD,
        )
        factory.make_custom_boot_resource(
            name="rhel/9.1",
            architecture="arm64/generic",
            filetype=BOOT_RESOURCE_FILE_TYPE.ROOT_TGZ,
        )
        factory.make_custom_boot_resource(
            name="my-custom",
            architecture="amd64/generic",
            filetype=BOOT_RESOURCE_FILE_TYPE.ROOT_TBZ,
        )
        factory.make_custom_boot_resource(
            name="my-custom",
            architecture="arm64/generic",
            filetype=BOOT_RESOURCE_FILE_TYPE.ROOT_TXZ,
        )
        osystems = list_all_usable_osystems()
        self.assertEqual(["custom", "rhel", "ubuntu"], sorted(osystems.keys()))
        ubuntu_release = osystems["ubuntu"].releases["focal"]
        self.assertTrue(
            ubuntu_release.architectures["amd64/generic"].can_deploy_to_memory
        )
        rhel_release = osystems["rhel"].releases["9.1"]
        self.assertFalse(
            rhel_release.architectures["amd64/generic"].can_deploy_to_memory
        )
        self.assertTrue(
            rhel_release.architectures["arm64/generic"].can_deploy_to_memory
        )
        custom_release = osystems["custom"].releases["my-custom"]
        self.assertFalse(
            custom_release.architectures["amd64/generic"].can_deploy_to_memory
        )
        self.assertTrue(
            custom_release.architectures["arm64/generic"].can_deploy_to_memory
        )

    def make_release_choice(self, os_name, release, include_asterisk=False):
        key = "{}/{}".format(os_name, release.name)
        title = release.title
        if include_asterisk:
            return ("%s*" % key, title)
        return (key, title)

    def test_list_all_releases_requiring_keys(self):
        factory.make_BootResource(
            name="windows/win2008r2",
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
        )
        factory.make_BootResource(
            name="windows/win2012",
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
        )
        factory.make_BootResource(
            name="windows/win2012r2",
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
        )
        factory.make_BootResource(
            name="windows/win-no-key",
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
        )
        factory.make_BootResource(
            name="custom/my-image",
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
            extra={"title": factory.make_name("title")},
        )
        osystems = list_all_releases_requiring_keys(list_all_usable_osystems())
        self.assertEqual(["windows"], list(osystems.keys()))
        self.assertEqual(
            ["win2008r2", "win2012", "win2012r2"],
            [
                release.name
                for release in osystems["windows"].releases.values()
            ],
        )

    def test_get_release_requires_key_returns_asterisk_when_required(self):
        release = OSRelease(
            requires_license_key=True,
            name="no-key",
            title="No Key",
        )
        self.assertEqual("*", get_release_requires_key(release))

    def test_get_release_requires_key_returns_empty_when_not_required(self):
        release = OSRelease(
            requires_license_key=False,
            name="no-key",
            title="No Key",
        )
        self.assertEqual("", get_release_requires_key(release))

    def test_list_release_choices_includes_default(self):
        self.assertEqual(
            [("", "Default OS Release")],
            list_release_choices({}, include_default=True),
        )

    def test_list_release_choices_doesnt_include_default(self):
        self.assertEqual([], list_release_choices({}, include_default=False))

    def test_list_release_choices(self):
        for _ in range(3):
            factory.make_BootResource(name="custom/%s" % factory.make_name())
        choices = [
            self.make_release_choice("custom", release)
            for release in list_all_usable_osystems()[
                "custom"
            ].releases.values()
        ]
        self.assertCountEqual(
            choices,
            list_release_choices(
                list_all_usable_osystems(), include_default=False
            ),
        )

    def test_list_release_choices_sorts(self):
        for _ in range(3):
            factory.make_custom_boot_resource(
                name=f"custom/{factory.make_name()}",
            )
        custom = list_all_usable_osystems()["custom"]
        choices = [
            self.make_release_choice("custom", release)
            for release in sorted(
                custom.releases.values(), key=attrgetter("title")
            )
        ]
        self.assertEqual(
            choices,
            list_release_choices(
                list_all_usable_osystems(), include_default=False
            ),
        )

    def test_list_release_choices_includes_requires_key_asterisk(self):
        factory.make_BootResource(name="windows/win2016")
        windows = list_all_usable_osystems()["windows"]
        choices = [
            self.make_release_choice("windows", release, include_asterisk=True)
            for release in windows.releases.values()
        ]
        self.assertCountEqual(
            choices,
            list_release_choices(
                list_all_usable_osystems(), include_default=False
            ),
        )

    def test_get_distro_series_initial(self):
        releases = [
            OSRelease(
                name=factory.make_name("release"),
                title=factory.make_string(),
            )
            for _ in range(3)
        ]
        osystem = OperatingSystem(
            name="my-os",
            title="My OS",
            releases=dict((release.name, release) for release in releases),
        )
        release = random.choice(releases)
        node = factory.make_Node(osystem="my-os", distro_series=release.name)
        self.assertEqual(
            f"my-os/{release.name}",
            get_distro_series_initial(
                {"my-os": osystem}, node, with_key_required=False
            ),
        )

    def test_get_distro_series_initial_without_key_required(self):
        releases = [
            OSRelease(
                requires_license_key=True,
                name=factory.make_name("release"),
                title=factory.make_string(),
            )
            for _ in range(3)
        ]
        osystem = OperatingSystem(
            name="my-os",
            title="My OS",
            releases=dict((release.name, release) for release in releases),
        )
        release = random.choice(releases)
        node = factory.make_Node(
            osystem="my-os",
            distro_series=release.name,
        )
        self.assertEqual(
            f"my-os/{release.name}",
            get_distro_series_initial(
                {"my-os": osystem}, node, with_key_required=False
            ),
        )

    def test_get_distro_series_initial_with_key_required(self):
        releases = [
            OSRelease(
                requires_license_key=True,
                name=factory.make_name("release"),
                title=factory.make_string(),
            )
            for _ in range(3)
        ]
        osystem = OperatingSystem(
            name="my-os",
            title="My OS",
            releases=dict((release.name, release) for release in releases),
        )
        release = random.choice(releases)
        node = factory.make_Node(osystem="my-os", distro_series=release.name)
        self.assertEqual(
            f"my-os/{release.name}*",
            get_distro_series_initial(
                {"my-os": osystem},
                node,
                with_key_required=True,
            ),
        )

    def test_get_distro_series_initial_works_around_conflicting_os(self):
        # Test for bug 1456892.
        node = factory.make_Node(
            osystem="my-os",
            distro_series="my-release",
        )
        self.assertEqual(
            "my-os/my-release",
            get_distro_series_initial({}, node, with_key_required=True),
        )

    def test_list_commissioning_choices_returns_empty_list_if_not_ubuntu(self):
        factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
        )
        self.assertEqual(
            [], list_commissioning_choices(list_all_usable_osystems())
        )

    def test_list_commissioning_choices_returns_commissioning_releases(self):
        factory.make_default_ubuntu_release_bootable()
        factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
        )
        self.assertEqual(
            [("focal", 'Ubuntu 20.04 LTS "Focal Fossa"')],
            list_commissioning_choices(list_all_usable_osystems()),
        )

    def test_list_commissioning_choices_returns_sorted(self):
        factory.make_BootResource(
            name="ubuntu/focal",
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
        )
        factory.make_BootResource(
            name="ubuntu/jammy",
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
        )
        self.assertEqual(
            [
                ("focal", 'Ubuntu 20.04 LTS "Focal Fossa"'),
                ("jammy", 'Ubuntu 22.04 LTS "Jammy Jellyfish"'),
            ],
            list_commissioning_choices(list_all_usable_osystems()),
        )

    def test_list_commissioning_choices_returns_current_selection(self):
        factory.make_BootResource(
            name="ubuntu/focal",
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
        )
        factory.make_BootResource(
            name="ubuntu/jammy",
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
        )
        commissioning_series, _ = Config.objects.get_or_create(
            name="commissioning_distro_series"
        )
        commissioning_series.value = factory.make_name("commissioning_series")
        commissioning_series.save()
        self.maxDiff = 1000
        choices = [
            (
                commissioning_series.value,
                "%s (No image available)" % commissioning_series.value,
            )
        ] + [
            ("focal", 'Ubuntu 20.04 LTS "Focal Fossa"'),
            ("jammy", 'Ubuntu 22.04 LTS "Jammy Jellyfish"'),
        ]
        self.assertEqual(
            choices, list_commissioning_choices(list_all_usable_osystems())
        )

    def test_make_hwe_kernel_ui_text_finds_release_from_bootsourcecache(self):
        self.useFixture(SignalsDisabled("bootsources"))
        release = factory.pick_ubuntu_release()
        kernel = "hwe-" + release[0]
        factory.make_BootSourceCache(
            os="ubuntu/%s" % release, subarch=kernel, release=release
        )
        self.assertEqual(
            f"{release} ({kernel})", make_hwe_kernel_ui_text(kernel)
        )

    def test_make_hwe_kernel_ui_finds_release_from_ubuntudistroinfo(self):
        self.assertEqual("trusty (hwe-t)", make_hwe_kernel_ui_text("hwe-t"))

    def test_make_hwe_kernel_ui_returns_kernel_when_none_found(self):
        unknown_kernel = factory.make_name("kernel")
        self.assertEqual(
            unknown_kernel, make_hwe_kernel_ui_text(unknown_kernel)
        )


class TestValidateOsystemAndDistroSeries(MAASServerTestCase):
    def test_raises_error_of_osystem_and_distro_series_dont_match(self):
        os = factory.make_name("os")
        release = "{}/{}".format(
            factory.make_name("os"),
            factory.make_name("release"),
        )
        error = self.assertRaises(
            ValidationError, validate_osystem_and_distro_series, os, release
        )
        self.assertEqual(
            "%s in distro_series does not match with "
            "operating system %s." % (release, os),
            error.message,
        )

    def test_raises_error_if_not_supported_osystem(self):
        os = factory.make_name("os")
        release = factory.make_name("release")
        error = self.assertRaises(
            ValidationError, validate_osystem_and_distro_series, os, release
        )
        self.assertEqual(
            "%s is not a supported operating system." % os, error.message
        )

    def test_raises_error_if_not_supported_release(self):
        factory.make_Node()
        factory.make_custom_boot_resource(name="custom/my-release")
        release = factory.make_name("release")
        error = self.assertRaises(
            ValidationError,
            validate_osystem_and_distro_series,
            "custom",
            release,
        )
        self.assertEqual(
            f"custom/{release} is not a supported operating system and release "
            "combination.",
            error.message,
        )

    def test_returns_osystem_and_release_with_license_key_stripped(self):
        factory.make_Node()
        factory.make_custom_boot_resource(name="custom/my-release")
        self.assertEqual(
            ("custom", "my-release"),
            validate_osystem_and_distro_series("custom", "my-release*"),
        )


class TestGetReleaseVersionFromString(MAASServerTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ubuntu = UbuntuDistroInfo()
        # We can't test with releases older than Precise as they have duplicate
        # names(e.g Wily and Warty) which will break the old style kernel
        # tests.
        try:
            ubuntu_rows = ubuntu._rows
        except AttributeError:
            ubuntu_rows = [row.__dict__ for row in ubuntu._releases]
        valid_releases = [
            row
            for row in ubuntu_rows
            if int(row["version"].split(".")[0]) >= 12
        ]
        release = random.choice(valid_releases)
        # Remove 'LTS' from version if it exists
        version_str = release["version"].split(" ")[0]
        # Convert the version into a list of ints
        version_tuple = tuple(int(seg) for seg in version_str.split("."))

        self.scenarios = (
            (
                "Release name",
                {
                    "string": release["series"],
                    "expected": version_tuple + tuple([0]),
                },
            ),
            (
                "Release version",
                {
                    "string": version_str,
                    "expected": version_tuple + tuple([0]),
                },
            ),
            (
                "Old style HWE kernel",
                {
                    "string": "hwe-%s" % release["series"][0],
                    "expected": version_tuple + tuple([OLD_STYLE_HWE_WEIGHT]),
                },
            ),
            (
                "GA kernel",
                {
                    "string": "ga-%s" % version_str,
                    "expected": version_tuple
                    + tuple([NEW_STYLE_KERNEL_WEIGHT]),
                },
            ),
            (
                "GA low latency kernel",
                {
                    "string": "ga-%s-lowlatency" % version_str,
                    "expected": version_tuple
                    + tuple([NEW_STYLE_KERNEL_WEIGHT + FLAVOURED_WEIGHT]),
                },
            ),
            (
                "GA platform-optimised kernel",
                {
                    "string": "xgene-uboot-mustang-ga-%s" % version_str,
                    "expected": version_tuple
                    + tuple(
                        [NEW_STYLE_KERNEL_WEIGHT + PLATFORM_OPTIMISED_WEIGHT]
                    ),
                },
            ),
            (
                "GA platform-optimised low latency kernel",
                {
                    "string": "xgene-uboot-mustang-ga-%s-lowlatency"
                    % version_str,
                    "expected": version_tuple
                    + tuple(
                        [
                            NEW_STYLE_KERNEL_WEIGHT
                            + FLAVOURED_WEIGHT
                            + PLATFORM_OPTIMISED_WEIGHT
                        ]
                    ),
                },
            ),
            (
                "HWE kernel",
                {
                    "string": "hwe-%s" % version_str,
                    "expected": version_tuple
                    + tuple([HWE_CHANNEL_WEIGHT + NEW_STYLE_KERNEL_WEIGHT]),
                },
            ),
            (
                "HWE edge kernel",
                {
                    "string": "hwe-%s-edge" % version_str,
                    "expected": version_tuple
                    + tuple(
                        [HWE_EDGE_CHANNEL_WEIGHT + NEW_STYLE_KERNEL_WEIGHT]
                    ),
                },
            ),
            (
                "HWE low latency kernel",
                {
                    "string": "hwe-%s-lowlatency" % version_str,
                    "expected": version_tuple
                    + tuple(
                        [
                            HWE_CHANNEL_WEIGHT
                            + NEW_STYLE_KERNEL_WEIGHT
                            + FLAVOURED_WEIGHT
                        ]
                    ),
                },
            ),
            (
                "HWE edge low latency kernel",
                {
                    "string": "hwe-%s-lowlatency-edge" % version_str,
                    "expected": version_tuple
                    + tuple(
                        [
                            HWE_EDGE_CHANNEL_WEIGHT
                            + NEW_STYLE_KERNEL_WEIGHT
                            + FLAVOURED_WEIGHT
                        ]
                    ),
                },
            ),
            (
                "Platform-optimised HWE kernel",
                {
                    "string": "xgene-uboot-mustang-hwe-%s" % version_str,
                    "expected": version_tuple
                    + tuple(
                        [
                            HWE_CHANNEL_WEIGHT
                            + NEW_STYLE_KERNEL_WEIGHT
                            + PLATFORM_OPTIMISED_WEIGHT
                        ]
                    ),
                },
            ),
            (
                "Platform-optimised HWE edge kernel",
                {
                    "string": "xgene-uboot-mustang-hwe-%s-edge" % version_str,
                    "expected": version_tuple
                    + tuple(
                        [
                            HWE_EDGE_CHANNEL_WEIGHT
                            + NEW_STYLE_KERNEL_WEIGHT
                            + PLATFORM_OPTIMISED_WEIGHT
                        ]
                    ),
                },
            ),
            (
                "Platform-optimised HWE low latency kernel",
                {
                    "string": "xgene-uboot-mustang-hwe-%s-lowlatency"
                    % version_str,
                    "expected": version_tuple
                    + tuple(
                        [
                            HWE_CHANNEL_WEIGHT
                            + NEW_STYLE_KERNEL_WEIGHT
                            + FLAVOURED_WEIGHT
                            + PLATFORM_OPTIMISED_WEIGHT
                        ]
                    ),
                },
            ),
            (
                "Platform-optimised HWE edge low latency kernel",
                {
                    "string": "xgene-uboot-mustang-hwe-%s-lowlatency-edge"
                    % version_str,
                    "expected": version_tuple
                    + tuple(
                        [
                            HWE_EDGE_CHANNEL_WEIGHT
                            + NEW_STYLE_KERNEL_WEIGHT
                            + FLAVOURED_WEIGHT
                            + PLATFORM_OPTIMISED_WEIGHT
                        ]
                    ),
                },
            ),
            (
                "Rolling kernel",
                {
                    "string": "hwe-rolling",
                    "expected": tuple(
                        [
                            999,
                            999,
                            HWE_CHANNEL_WEIGHT + NEW_STYLE_KERNEL_WEIGHT,
                        ]
                    ),
                },
            ),
            (
                "Rolling edge kernel",
                {
                    "string": "hwe-rolling-edge",
                    "expected": tuple(
                        [
                            999,
                            999,
                            HWE_EDGE_CHANNEL_WEIGHT + NEW_STYLE_KERNEL_WEIGHT,
                        ]
                    ),
                },
            ),
            (
                "Rolling lowlatency kernel",
                {
                    "string": "hwe-rolling-lowlatency",
                    "expected": tuple(
                        [
                            999,
                            999,
                            HWE_CHANNEL_WEIGHT
                            + NEW_STYLE_KERNEL_WEIGHT
                            + FLAVOURED_WEIGHT,
                        ]
                    ),
                },
            ),
            (
                "Rolling lowlatency edge kernel",
                {
                    "string": "hwe-rolling-lowlatency-edge",
                    "expected": tuple(
                        [
                            999,
                            999,
                            HWE_EDGE_CHANNEL_WEIGHT
                            + NEW_STYLE_KERNEL_WEIGHT
                            + FLAVOURED_WEIGHT,
                        ]
                    ),
                },
            ),
            (
                "Old-style platform-only kernel string",
                {
                    "string": "xgene-uboot-mustang",
                    "expected": tuple(
                        [
                            0,
                            0,
                            PLATFORM_OPTIMISED_WEIGHT
                            + PLATFORM_ONLY_STRING_WEIGHT,
                        ]
                    ),
                },
            ),
            (
                "highbank (old-style platform-only release-like)",
                {
                    "string": "highbank",
                    "expected": tuple(
                        [
                            0,
                            0,
                            PLATFORM_OPTIMISED_WEIGHT
                            + PLATFORM_ONLY_STRING_WEIGHT,
                        ]
                    ),
                },
            ),
        )

    def test_get_release_version_from_string(self):
        self.assertEqual(
            self.expected, get_release_version_from_string(self.string)
        )


class TestReleaseANewerThanB(MAASServerTestCase):
    def test_a_newer_than_b_true(self):
        self.assertTrue(
            release_a_newer_than_b(
                "hwe-rolling",
                factory.make_kernel_string(can_be_release_or_version=True),
            )
        )

    def test_a_equal_to_b_true(self):
        string = factory.make_kernel_string(can_be_release_or_version=True)
        self.assertTrue(release_a_newer_than_b(string, string))

    def test_a_less_than_b_false(self):
        self.assertFalse(
            release_a_newer_than_b(
                factory.make_kernel_string(can_be_release_or_version=True),
                "hwe-rolling",
            )
        )

    def test_accounts_for_edge(self):
        self.assertFalse(
            release_a_newer_than_b("hwe-rolling", "hwe-rolling-edge")
        )

    def test_flavoured_kernel_newer_than_flavourless(self):
        self.assertTrue(
            release_a_newer_than_b("hwe-rolling-lowlatency", "hwe-rolling")
        )
        self.assertFalse(
            release_a_newer_than_b("hwe-rolling", "hwe-rolling-lowlatency")
        )


class TestGetWorkingKernel(MAASServerTestCase):
    def test_get_working_kernel_returns_default_kernel(self):
        self.patch(BootResource.objects, "get_kernels").return_value = [
            "hwe-t",
            "hwe-u",
        ]
        hwe_kernel = get_working_kernel(
            None, None, "amd64/generic", "ubuntu", "trusty"
        )
        self.assertEqual(hwe_kernel, "hwe-t")

    def test_get_working_kernel_set_kernel(self):
        self.patch(BootResource.objects, "get_kernels").return_value = [
            "hwe-t",
            "hwe-v",
        ]
        hwe_kernel = get_working_kernel(
            "hwe-v", None, "amd64/generic", "ubuntu", "trusty"
        )
        self.assertEqual(hwe_kernel, "hwe-v")

    def test_get_working_kernel_accepts_ga_kernel(self):
        self.patch(BootResource.objects, "get_kernels").return_value = [
            "ga-16.04",
        ]
        hwe_kernel = get_working_kernel(
            "ga-16.04", None, "amd64/generic", "ubuntu", "xenial"
        )
        self.assertEqual(hwe_kernel, "ga-16.04")

    def test_get_working_kernel_returns_suitable_kernel_with_nongeneric_arch(
        self,
    ):
        self.patch(BootResource.objects, "get_kernels").return_value = [
            "ga-20.04",
        ]
        result = get_working_kernel(
            "ga-20.04", None, "armhf/hardbank", "ubuntu", "trusty"
        )
        self.assertEqual("ga-20.04", result)

    def test_get_working_kernel_fails_with_missing_hwe_kernel(self):
        exception_raised = False
        self.patch(BootResource.objects, "get_kernels").return_value = [
            "hwe-t",
            "hwe-u",
        ]
        try:
            get_working_kernel(
                "hwe-v", None, "amd64/generic", "ubuntu", "trusty"
            )
        except ValidationError as e:
            self.assertEqual(
                "hwe-v is not available for ubuntu/trusty on amd64/generic.",
                e.message,
            )
            exception_raised = True
        self.assertTrue(exception_raised)

    def test_get_working_kernel_fails_with_old_kernel_and_newer_release(self):
        exception_raised = False
        self.patch(BootResource.objects, "get_kernels").return_value = [
            "hwe-t",
            "hwe-v",
        ]
        try:
            get_working_kernel(
                "hwe-t", None, "amd64/generic", "ubuntu", "vivid"
            )
        except ValidationError as e:
            self.assertEqual(
                "hwe-t is too old to use on ubuntu/vivid.", e.message
            )
            exception_raised = True
        self.assertTrue(exception_raised)

    def test_get_working_kernel_fails_with_old_kern_and_new_min_hwe_kern(self):
        exception_raised = False
        self.patch(BootResource.objects, "get_kernels").return_value = [
            "hwe-t",
            "hwe-v",
        ]
        try:
            get_working_kernel(
                "hwe-t", "hwe-v", "amd64/generic", "ubuntu", "precise"
            )
        except ValidationError as e:
            self.assertEqual(
                "chosen kernel (hwe-t) is older than minimal kernel required by the machine (hwe-v).",
                e.message,
            )
            exception_raised = True
        self.assertTrue(exception_raised)

    def test_get_working_kernel_fails_with_no_avalible_kernels(self):
        exception_raised = False
        self.patch(BootResource.objects, "get_kernels").return_value = [
            "hwe-t",
            "hwe-v",
        ]
        try:
            get_working_kernel(
                "hwe-t", "hwe-v", "amd64/generic", "ubuntu", "precise"
            )
        except ValidationError as e:
            self.assertEqual(
                "chosen kernel (hwe-t) is older than minimal kernel required by the machine (hwe-v).",
                e.message,
            )
            exception_raised = True
        self.assertTrue(exception_raised)

    def test_get_working_kernel_fails_with_old_release_and_newer_hwe_kern(
        self,
    ):
        exception_raised = False
        try:
            get_working_kernel(
                None, "hwe-v", "amd64/generic", "ubuntu", "trusty"
            )
        except ValidationError as e:
            self.assertEqual(
                "trusty has no kernels available which meet"
                + " min_hwe_kernel(hwe-v).",
                e.message,
            )
            exception_raised = True
        self.assertTrue(exception_raised)

    def test_get_working_kernel_always_sets_kern_with_commissionable_os(self):
        self.patch(BootResource.objects, "get_kernels").return_value = [
            "hwe-t",
            "hwe-v",
        ]
        mock_get_config = self.patch(Config.objects, "get_config")
        mock_get_config.return_value = "trusty"
        kernel = get_working_kernel(
            None,
            "hwe-v",
            "%s/generic" % factory.make_name("arch"),
            factory.make_name("osystem"),
            factory.make_name("distro"),
        )
        self.assertThat(mock_get_config, MockAnyCall("commissioning_osystem"))
        self.assertThat(
            mock_get_config, MockAnyCall("commissioning_distro_series")
        )
        self.assertEqual("hwe-v", kernel)

    def test_get_working_kernel_sets_hwe_kern_to_min_hwe_kern_for_edge(self):
        # Regression test for LP:1654412
        import maasserver.utils.osystems as osystems

        mock_get_kernels = self.patch(
            osystems, "get_available_kernels_prioritising_platform"
        )
        mock_get_kernels.return_value = [
            "hwe-16.04",
            "hwe-16.04-edge",
        ]
        arch = factory.make_name("arch")

        kernel = get_working_kernel(
            None, "hwe-16.04-edge", "%s/generic" % arch, "ubuntu", "xenial"
        )

        self.assertEqual("hwe-16.04-edge", kernel)
        mock_get_kernels.assert_called_with(
            arch, "ubuntu/xenial", "generic", kflavor="generic"
        )

    def test_get_working_kernel_uses_base_image_for_lookup_with_custom_images(
        self,
    ):
        factory.make_usable_boot_resource(
            name="ubuntu/bionic",
            architecture="amd64/ga-18.04",
            kflavor="generic",
        )
        custom_resource = factory.make_BootResource(
            name=factory.make_name("name"),
            base_image="ubuntu/bionic",
            architecture="amd64/generic",
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
        )
        osystem = "custom"
        series = custom_resource.name
        kernel = get_working_kernel(
            None, None, custom_resource.architecture, osystem, series
        )
        self.assertEqual("ga-18.04", kernel)


class TestValidateMinHweKernel(MAASServerTestCase):
    def test_validates_kernel(self):
        kernel = factory.make_kernel_string(generic_only=True)
        self.patch(
            BootResource.objects, "get_supported_kernel_compatibility_levels"
        ).return_value = (kernel,)
        self.assertEqual(kernel, validate_min_hwe_kernel(kernel))

    def test_returns_empty_string_when_none(self):
        self.assertEqual("", validate_min_hwe_kernel(None))

    def test_raises_exception_when_not_found(self):
        self.assertRaises(
            ValidationError,
            validate_min_hwe_kernel,
            factory.make_kernel_string(),
        )

    def test_raises_exception_when_lowlatency(self):
        self.assertRaises(
            ValidationError, validate_min_hwe_kernel, "hwe-16.04-lowlatency"
        )


class TestGetReleaseFromDistroInfo(MAASServerTestCase):
    def pick_release(self):
        ubuntu = UbuntuDistroInfo()
        try:
            ubuntu_rows = ubuntu._rows
        except AttributeError:
            ubuntu_rows = [row.__dict__ for row in ubuntu._releases]
        supported_releases = [
            release
            for release in ubuntu_rows
            if int(release["version"].split(".")[0]) >= 12
        ]
        return random.choice(supported_releases)

    def test_finds_by_series(self):
        release = self.pick_release()
        self.assertEqual(
            release, get_release_from_distro_info(release["series"])
        )

    def test_finds_by_series_first_letter(self):
        release = self.pick_release()
        self.assertEqual(
            release, get_release_from_distro_info(release["series"][0])
        )

    def test_finds_by_version(self):
        release = self.pick_release()
        self.assertEqual(
            release, get_release_from_distro_info(release["version"])
        )

    def test_returns_none_when_not_found(self):
        self.assertIsNone(
            get_release_from_distro_info(factory.make_name("string"))
        )


class TestGetReleaseFromDB(MAASServerTestCase):
    def make_boot_source_cache(self):
        # Disable boot sources signals otherwise the test fails due to unrun
        # post-commit tasks at the end of the test.
        self.useFixture(SignalsDisabled("bootsources"))
        ubuntu = UbuntuDistroInfo()
        try:
            ubuntu_rows = ubuntu._rows
        except AttributeError:
            ubuntu_rows = [row.__dict__ for row in ubuntu._releases]
        supported_releases = [
            release
            for release in ubuntu_rows
            if int(release["version"].split(".")[0]) >= 12
        ]
        release = random.choice(supported_releases)
        ga_or_hwe = random.choice(["hwe", "ga"])
        subarch = "{}-{}".format(ga_or_hwe, release["version"].split(" ")[0])
        factory.make_BootSourceCache(
            os="ubuntu",
            arch=factory.make_name("arch"),
            subarch=subarch,
            release=release["series"],
            release_codename=release["codename"],
            release_title=release["version"],
            support_eol=release.get("eol_server", release.get("eol-server")),
        )
        return release

    def test_finds_by_subarch(self):
        release = self.make_boot_source_cache()
        self.assertEqual(
            release["series"],
            get_release_from_db(release["version"].split(" ")[0])["series"],
        )

    def test_finds_by_release(self):
        release = self.make_boot_source_cache()
        self.assertEqual(
            release["version"],
            get_release_from_db(release["series"])["version"],
        )

    def test_finds_by_release_first_letter(self):
        release = self.make_boot_source_cache()
        self.assertEqual(
            release["version"],
            get_release_from_db(release["series"][0])["version"],
        )

    def test_finds_by_version(self):
        release = self.make_boot_source_cache()
        self.assertCountEqual(
            release["series"],
            get_release_from_db(release["version"])["series"],
        )

    def test_returns_none_when_not_found(self):
        self.assertIsNone(get_release_from_db(factory.make_name("string")))


class TestParseSubarchKernelString(MAASTestCase):
    def _expect(
        self, kernel_string, *, channel="", release="", platform="", kflavor=""
    ):
        result = parse_subarch_kernel_string(kernel_string)
        self.assertEqual(
            ParsedKernelString(
                channel=channel,
                release=release,
                platform=platform,
                kflavor=kflavor,
            ),
            result,
        )

    def test_supports_subarch_being_subarch(self):
        self._expect("highbank", platform="highbank")

    def test_supports_subarch_being_multipart_subarch(self):
        self._expect("xgene-uboot-mustang", platform="xgene-uboot-mustang")

    def test_supports_ga_version_format_without_platform(self):
        self._expect(
            "ga-16.04",
            channel="ga",
            release="16.04",
            platform="",
            kflavor="",
        )

    def test_supports_ga_version_flavoured_format_without_platform(self):
        self._expect(
            "ga-16.04-lowlatency",
            channel="ga",
            release="16.04",
            platform="",
            kflavor="lowlatency",
        )

    def test_supports_ga_version_format_with_platform(self):
        self._expect(
            "platform-ga-16.04",
            channel="ga",
            release="16.04",
            platform="platform",
            kflavor="",
        )
        self._expect(
            "multi-part-platform-ga-16.04",
            channel="ga",
            release="16.04",
            platform="multi-part-platform",
            kflavor="",
        )

    def test_supports_ga_version_flavoured_format_with_platform(self):
        self._expect(
            "platform-ga-16.04-lowlatency",
            channel="ga",
            release="16.04",
            platform="platform",
            kflavor="lowlatency",
        )
        self._expect(
            "multi-part-platform-ga-16.04-lowlatency",
            channel="ga",
            release="16.04",
            platform="multi-part-platform",
            kflavor="lowlatency",
        )

    def test_supports_hwe_release_letter(self):
        self._expect(
            "hwe-x", channel="hwe", release="x", platform="", kflavor=""
        )

    def test_supports_hwe_release_letter_flavoured(self):
        self._expect(
            "hwe-x-lowlatency",
            channel="hwe",
            release="x",
            platform="",
            kflavor="lowlatency",
        )

    def test_supports_hwe_release_letter_with_platform(self):
        self._expect(
            "platform-hwe-x",
            channel="hwe",
            release="x",
            platform="platform",
            kflavor="",
        )
        self._expect(
            "multi-part-platform-hwe-x",
            channel="hwe",
            release="x",
            platform="multi-part-platform",
            kflavor="",
        )

    def test_supports_hwe_release_letter_flavoured_with_platform(self):
        self._expect(
            "platform-hwe-x-lowlatency",
            channel="hwe",
            release="x",
            platform="platform",
            kflavor="lowlatency",
        )
        self._expect(
            "multi-part-platform-hwe-x-lowlatency",
            channel="hwe",
            release="x",
            platform="multi-part-platform",
            kflavor="lowlatency",
        )

    def test_supports_hwe_release_version(self):
        self._expect(
            "hwe-16.04",
            channel="hwe",
            release="16.04",
            platform="",
            kflavor="",
        )

    def test_supports_hwe_release_version_flavoured(self):
        self._expect(
            "hwe-16.04-lowlatency",
            channel="hwe",
            release="16.04",
            platform="",
            kflavor="lowlatency",
        )

    def test_supports_hwe_release_version_with_platform(self):
        self._expect(
            "platform-hwe-16.04",
            channel="hwe",
            release="16.04",
            platform="platform",
            kflavor="",
        )
        self._expect(
            "multi-part-platform-hwe-16.04",
            channel="hwe",
            release="16.04",
            platform="multi-part-platform",
            kflavor="",
        )

    def test_supports_hwe_release_version_flavoured_with_platform(self):
        self._expect(
            "platform-hwe-16.04-lowlatency",
            channel="hwe",
            release="16.04",
            platform="platform",
            kflavor="lowlatency",
        )
        self._expect(
            "multi-part-platform-hwe-16.04-lowlatency",
            channel="hwe",
            release="16.04",
            platform="multi-part-platform",
            kflavor="lowlatency",
        )

    def test_supports_hwe_edge_release_version(self):
        self._expect(
            "hwe-16.04-edge",
            channel="hwe-edge",
            release="16.04",
            platform="",
            kflavor="",
        )
        self._expect(
            "hwe-edge-16.04",
            channel="hwe-edge",
            release="16.04",
            platform="",
            kflavor="",
        )

    def test_supports_hwe_edge_release_version_flavoured(self):
        self._expect(
            "hwe-16.04-lowlatency-edge",
            channel="hwe-edge",
            release="16.04",
            platform="",
            kflavor="lowlatency",
        )
        self._expect(
            "hwe-edge-16.04-lowlatency",
            channel="hwe-edge",
            release="16.04",
            platform="",
            kflavor="lowlatency",
        )

    def test_supports_hwe_edge_release_version_with_platform(self):
        self._expect(
            "platform-hwe-16.04-edge",
            channel="hwe-edge",
            release="16.04",
            platform="platform",
            kflavor="",
        )
        self._expect(
            "multi-part-platform-hwe-16.04-edge",
            channel="hwe-edge",
            release="16.04",
            platform="multi-part-platform",
            kflavor="",
        )
        self._expect(
            "platform-hwe-edge-16.04",
            channel="hwe-edge",
            release="16.04",
            platform="platform",
            kflavor="",
        )
        self._expect(
            "multi-part-platform-hwe-edge-16.04",
            channel="hwe-edge",
            release="16.04",
            platform="multi-part-platform",
            kflavor="",
        )

    def test_supports_hwe_edge_release_version_flavoured_with_platform(self):
        self._expect(
            "platform-hwe-16.04-lowlatency-edge",
            channel="hwe-edge",
            release="16.04",
            platform="platform",
            kflavor="lowlatency",
        )
        self._expect(
            "multi-part-platform-hwe-16.04-lowlatency-edge",
            channel="hwe-edge",
            release="16.04",
            platform="multi-part-platform",
            kflavor="lowlatency",
        )
        self._expect(
            "platform-hwe-edge-16.04-lowlatency",
            channel="hwe-edge",
            release="16.04",
            platform="platform",
            kflavor="lowlatency",
        )
        self._expect(
            "multi-part-platform-hwe-edge-16.04-lowlatency",
            channel="hwe-edge",
            release="16.04",
            platform="multi-part-platform",
            kflavor="lowlatency",
        )

    def test_raises_when_multiple_channels_specified(self):
        self.assertRaises(
            InvalidSubarchKernelStringError,
            parse_subarch_kernel_string,
            "hwe-ga-20.04",
        )

    def test_raises_when_no_release(self):
        self.assertRaises(
            ValueError, parse_subarch_kernel_string, "some-platform-hwe"
        )


class TestGetAvailableKernelsPrioritisingPlatform(MAASTestCase):
    def test_correct_kernel_order(self):
        platform_prefix = "test-platform"
        expected_kflavor = factory.make_name("kflavor")
        expected_platform = factory.make_name(platform_prefix)

        platform_optimised = f"{expected_platform}-ga-20.04-{expected_kflavor}"
        platform_generic = f"{platform_prefix}-ga-20.04-{expected_kflavor}"
        generic = f"ga-20.04-{expected_kflavor}"

        arch = factory.make_name("arch")
        name = "ubuntu/whatever"

        def get_kernel_side_effect(
            os_release,
            architecture=None,
            platform=None,
            kflavor=None,
            strict_platform_match=False,
        ):
            if (
                os_release != name
                or architecture != arch
                or kflavor != expected_kflavor
            ):
                return []
            if strict_platform_match and platform == expected_platform:
                return [platform_optimised]
            elif not strict_platform_match and platform == expected_platform:
                return [generic, platform_generic]
            elif not strict_platform_match and platform == "generic":
                return [generic]
            raise Exception("Get kernel mock conditions failed")

        self.patch(
            BootResource.objects, "get_kernels"
        ).side_effect = get_kernel_side_effect

        result = get_available_kernels_prioritising_platform(
            arch=arch,
            os_release=name,
            platform=expected_platform,
            kflavor=expected_kflavor,
        )
        self.assertEqual(
            [platform_optimised, platform_generic, generic], result
        )

    def test_no_generic_kernels_for_some_platforms(self):
        platform_prefix = "test-platform"
        expected_kflavor = factory.make_name("kflavor")
        expected_platform = factory.make_name(platform_prefix)

        platform_optimised = f"{expected_platform}-ga-20.04-{expected_kflavor}"
        platform_generic = f"{platform_prefix}-ga-20.04-{expected_kflavor}"
        generic = f"ga-20.04-{expected_kflavor}"

        arch = factory.make_name("arch")
        name = "ubuntu/whatever"

        def get_kernel_side_effect(
            os_release,
            architecture=None,
            platform=None,
            kflavor=None,
            strict_platform_match=False,
        ):
            if (
                os_release != name
                or architecture != arch
                or kflavor != expected_kflavor
            ):
                return []
            if strict_platform_match and platform == expected_platform:
                return [platform_optimised]
            elif not strict_platform_match and platform == expected_platform:
                # This test emulates generic kernel not having
                # the platform in its "supported_platforms" list...
                return [platform_generic]
            elif not strict_platform_match and platform == "generic":
                # ...but we still need to return the generic kernel
                # when asked to.
                return [generic]
            raise Exception("Get kernel mock conditions failed")

        self.patch(
            BootResource.objects, "get_kernels"
        ).side_effect = get_kernel_side_effect

        result = get_available_kernels_prioritising_platform(
            arch=arch,
            os_release=name,
            platform=expected_platform,
            kflavor=expected_kflavor,
        )
        self.assertEqual([platform_optimised, platform_generic], result)

    def test_generic_platform_shortcut_works(self):
        mock_get_kernels = self.patch(BootResource.objects, "get_kernels")
        arch = factory.make_name("arch") + "/generic"
        kflavor = factory.make_name("kflavor")
        expected_resource = "ga-20.04"
        name = "ubuntu/whatever"
        mock_get_kernels.return_value = [expected_resource]
        result = get_available_kernels_prioritising_platform(
            arch=arch, os_release=name, platform="generic", kflavor=kflavor
        )
        mock_get_kernels.assert_called_once_with(
            name, architecture=arch, platform="generic", kflavor=kflavor
        )
        self.assertEqual([expected_resource], result)
