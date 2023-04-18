# Copyright 2014-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.utils.osystems`."""


from operator import itemgetter
import random

from distro_info import UbuntuDistroInfo
from django.core.exceptions import ValidationError

from maasserver.clusterrpc.testing.osystems import (
    make_rpc_osystem,
    make_rpc_release,
)
from maasserver.enum import BOOT_RESOURCE_TYPE
from maasserver.models import BootResource, Config
from maasserver.models.signals.testing import SignalsDisabled
from maasserver.testing.factory import factory
from maasserver.testing.osystems import make_usable_osystem
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.osystems import (
    FLAVOURED_WEIGHT,
    get_distro_series_initial,
    get_release_from_db,
    get_release_from_distro_info,
    get_release_requires_key,
    get_release_version_from_string,
    HWE_CHANNEL_WEIGHT,
    HWE_EDGE_CHANNEL_WEIGHT,
    InvalidSubarchKernelStringError,
    list_all_releases_requiring_keys,
    list_all_usable_osystems,
    list_all_usable_releases,
    list_commissioning_choices,
    list_osystem_choices,
    list_release_choices,
    make_hwe_kernel_ui_text,
    NOT_OLD_HWE_WEIGHT,
    parse_subarch_kernel_string,
    ParsedKernelString,
    PLATFORM_WEIGHT,
    release_a_newer_than_b,
    validate_hwe_kernel,
    validate_min_hwe_kernel,
    validate_osystem_and_distro_series,
)
from maastesting.matchers import MockAnyCall, MockCalledOnceWith
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

        self.assertCountEqual(
            [
                {
                    "name": "custom",
                    "title": "Custom",
                    "default_commissioning_release": None,
                    "default_release": "",
                    "releases": [
                        {
                            "name": custom_os.name,
                            "title": custom_os.extra["title"],
                            "can_commission": False,
                            "requires_license_key": False,
                        }
                    ],
                },
                {
                    "name": "ubuntu",
                    "title": "Ubuntu",
                    "default_commissioning_release": "focal",
                    "default_release": "focal",
                    "releases": [
                        {
                            "name": "focal",
                            "title": 'Ubuntu 20.04 LTS "Focal Fossa"',
                            "can_commission": True,
                            "requires_license_key": False,
                        }
                    ],
                },
            ],
            list_all_usable_osystems(),
        )

    def test_list_osystem_choices_includes_default(self):
        self.assertEqual(
            [("", "Default OS")],
            list_osystem_choices([], include_default=True),
        )

    def test_list_osystem_choices_doesnt_include_default(self):
        self.assertEqual([], list_osystem_choices([], include_default=False))

    def test_list_osystem_choices_uses_name_and_title(self):
        osystem = make_rpc_osystem()
        self.assertEqual(
            [(osystem["name"], osystem["title"])],
            list_osystem_choices([osystem], include_default=False),
        )

    def test_list_osystem_choices_doesnt_duplicate(self):
        self.assertEqual(
            [("custom", "Custom")],
            list_osystem_choices(
                [
                    {"name": "custom", "title": "Custom"},
                    {"name": "custom", "title": "Custom"},
                ],
                include_default=False,
            ),
        )


class TestReleases(MAASServerTestCase):
    def make_release_choice(self, os_name, release, include_asterisk=False):
        key = "{}/{}".format(os_name, release["name"])
        title = release["title"]
        if not title:
            title = release["name"]
        if include_asterisk:
            return ("%s*" % key, title)
        return (key, title)

    def test_list_all_usable_releases(self):
        custom_os = factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
            extra={"title": factory.make_name("title")},
        )
        factory.make_default_ubuntu_release_bootable()
        # Bootloader to be ignored.
        factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED, bootloader_type="uefi"
        )
        self.assertDictEqual(
            {
                "custom": [
                    {
                        "name": custom_os.name,
                        "title": custom_os.extra["title"],
                        "can_commission": False,
                        "requires_license_key": False,
                    }
                ],
                "ubuntu": [
                    {
                        "name": "focal",
                        "title": 'Ubuntu 20.04 LTS "Focal Fossa"',
                        "can_commission": True,
                        "requires_license_key": False,
                    }
                ],
            },
            dict(list_all_usable_releases()),
        )

    def test_list_release_with_missing_title(self):
        releases = [make_rpc_release(name="xenial"), make_rpc_release()]
        # Simulate missing title
        releases[-1]["title"] = None
        bogus_release_name = releases[-1]["name"]
        for release in releases:
            factory.make_BootResource(
                name="ubuntu/" + release["name"],
                rtype=BOOT_RESOURCE_TYPE.SYNCED,
            )
        self.assertEqual(
            [
                ("ubuntu/xenial", 'Ubuntu 16.04 LTS "Xenial Xerus"'),
                ("ubuntu/" + bogus_release_name, bogus_release_name),
            ],
            list_release_choices(
                list_all_usable_releases(), include_default=False
            ),
        )

    def test_list_all_releases_requiring_keys(self):
        releases = [
            make_rpc_release(requires_license_key=True) for _ in range(3)
        ]
        release_without_license_key = make_rpc_release(
            requires_license_key=False
        )
        osystem = make_rpc_osystem(
            releases=releases + [release_without_license_key]
        )
        self.assertCountEqual(
            releases,
            list_all_releases_requiring_keys([osystem])[osystem["name"]],
        )

    def test_list_all_releases_requiring_keys_sorts(self):
        releases = [
            make_rpc_release(requires_license_key=True) for _ in range(3)
        ]
        release_without_license_key = make_rpc_release(
            requires_license_key=False
        )
        osystem = make_rpc_osystem(
            releases=releases + [release_without_license_key]
        )
        releases = sorted(releases, key=itemgetter("title"))
        self.assertEqual(
            releases,
            list_all_releases_requiring_keys([osystem])[osystem["name"]],
        )

    def test_get_release_requires_key_returns_asterisk_when_required(self):
        release = make_rpc_release(requires_license_key=True)
        self.assertEqual("*", get_release_requires_key(release))

    def test_get_release_requires_key_returns_empty_when_not_required(self):
        release = make_rpc_release(requires_license_key=False)
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
            for release in list_all_usable_releases()["custom"]
        ]
        self.assertCountEqual(
            choices,
            list_release_choices(
                list_all_usable_releases(), include_default=False
            ),
        )

    def test_list_release_choices_fallsback_to_name(self):
        for _ in range(3):
            factory.make_BootResource(name="custom/%s" % factory.make_name())
        releases = list_all_usable_releases()["custom"]
        for release in releases:
            release["title"] = ""
        choices = [
            self.make_release_choice("custom", release) for release in releases
        ]
        self.assertCountEqual(
            choices,
            list_release_choices(
                list_all_usable_releases(), include_default=False
            ),
        )

    def test_list_release_choices_sorts(self):
        for _ in range(3):
            factory.make_BootResource(name="custom/%s" % factory.make_name())
        releases = list_all_usable_releases()["custom"]
        choices = [
            self.make_release_choice("custom", release)
            for release in sorted(releases, key=itemgetter("title"))
        ]
        self.assertEqual(
            choices,
            list_release_choices(
                list_all_usable_releases(), include_default=False
            ),
        )

    def test_list_release_choices_includes_requires_key_asterisk(self):
        factory.make_BootResource(name="windows/win2016")
        releases = list_all_usable_releases()["windows"]
        choices = [
            self.make_release_choice("windows", release, include_asterisk=True)
            for release in releases
        ]
        self.assertCountEqual(
            choices,
            list_release_choices(
                list_all_usable_releases(), include_default=False
            ),
        )

    def test_get_distro_series_initial(self):
        releases = [make_rpc_release() for _ in range(3)]
        osystem = make_rpc_osystem(releases=releases)
        release = random.choice(releases)
        node = factory.make_Node(
            osystem=osystem["name"], distro_series=release["name"]
        )
        self.assertEqual(
            "{}/{}".format(osystem["name"], release["name"]),
            get_distro_series_initial(
                [osystem], node, with_key_required=False
            ),
        )

    def test_get_distro_series_initial_without_key_required(self):
        releases = [
            make_rpc_release(requires_license_key=True) for _ in range(3)
        ]
        osystem = make_rpc_osystem(releases=releases)
        release = random.choice(releases)
        node = factory.make_Node(
            osystem=osystem["name"], distro_series=release["name"]
        )
        self.assertEqual(
            "{}/{}".format(osystem["name"], release["name"]),
            get_distro_series_initial(
                [osystem], node, with_key_required=False
            ),
        )

    def test_get_distro_series_initial_with_key_required(self):
        releases = [
            make_rpc_release(requires_license_key=True) for _ in range(3)
        ]
        osystem = make_rpc_osystem(releases=releases)
        release = random.choice(releases)
        node = factory.make_Node(
            osystem=osystem["name"], distro_series=release["name"]
        )
        self.assertEqual(
            "{}/{}*".format(osystem["name"], release["name"]),
            get_distro_series_initial([osystem], node, with_key_required=True),
        )

    def test_get_distro_series_initial_works_around_conflicting_os(self):
        # Test for bug 1456892.
        releases = [
            make_rpc_release(requires_license_key=True) for _ in range(3)
        ]
        osystem = make_rpc_osystem(releases=releases)
        release = random.choice(releases)
        node = factory.make_Node(
            osystem=osystem["name"], distro_series=release["name"]
        )
        self.assertEqual(
            "{}/{}".format(osystem["name"], release["name"]),
            get_distro_series_initial([], node, with_key_required=True),
        )

    def test_list_commissioning_choices_returns_empty_list_if_not_ubuntu(self):
        osystem = make_rpc_osystem()
        self.assertEqual([], list_commissioning_choices([osystem]))

    def test_list_commissioning_choices_returns_commissioning_releases(self):
        comm_releases = [
            make_rpc_release(can_commission=True) for _ in range(3)
        ]
        comm_releases += [
            make_rpc_release(
                Config.objects.get_config("commissioning_distro_series"),
                can_commission=True,
            )
        ]
        no_comm_release = make_rpc_release()
        osystem = make_rpc_osystem(
            "ubuntu", releases=comm_releases + [no_comm_release]
        )
        choices = [
            (release["name"], release["title"]) for release in comm_releases
        ]
        self.assertCountEqual(choices, list_commissioning_choices([osystem]))

    def test_list_commissioning_choices_returns_sorted(self):
        comm_releases = [
            make_rpc_release(can_commission=True) for _ in range(3)
        ]
        comm_releases += [
            make_rpc_release(
                Config.objects.get_config("commissioning_distro_series"),
                can_commission=True,
            )
        ]
        osystem = make_rpc_osystem("ubuntu", releases=comm_releases)
        comm_releases = sorted(comm_releases, key=itemgetter("title"))
        choices = [
            (release["name"], release["title"]) for release in comm_releases
        ]
        self.assertEqual(choices, list_commissioning_choices([osystem]))

    def test_list_commissioning_choices_returns_current_selection(self):
        comm_releases = [
            make_rpc_release(can_commission=True) for _ in range(3)
        ]
        osystem = make_rpc_osystem("ubuntu", releases=comm_releases)
        comm_releases = sorted(comm_releases, key=itemgetter("title"))
        commissioning_series, _ = Config.objects.get_or_create(
            name="commissioning_distro_series"
        )
        commissioning_series.value = factory.make_name("commissioning_series")
        commissioning_series.save()
        choices = [
            (
                commissioning_series.value,
                "%s (No image available)" % commissioning_series.value,
            )
        ] + [(release["name"], release["title"]) for release in comm_releases]
        self.assertEqual(choices, list_commissioning_choices([osystem]))

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
        osystem = make_usable_osystem(self)
        release = factory.make_name("release")
        error = self.assertRaises(
            ValidationError,
            validate_osystem_and_distro_series,
            osystem["name"],
            release,
        )
        self.assertEqual(
            "%s/%s is not a supported operating system and release "
            "combination." % (osystem["name"], release),
            error.message,
        )

    def test_returns_osystem_and_release_with_license_key_stripped(self):
        factory.make_Node()
        osystem = make_usable_osystem(self)
        release = osystem["default_release"]
        self.assertEqual(
            (osystem["name"], release),
            validate_osystem_and_distro_series(osystem["name"], release + "*"),
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
                    "expected": version_tuple + tuple([0]),
                },
            ),
            (
                "GA kernel",
                {
                    "string": "ga-%s" % version_str,
                    "expected": version_tuple + tuple([NOT_OLD_HWE_WEIGHT]),
                },
            ),
            (
                "GA low latency kernel",
                {
                    "string": "ga-%s-lowlatency" % version_str,
                    "expected": version_tuple
                    + tuple([NOT_OLD_HWE_WEIGHT + FLAVOURED_WEIGHT]),
                },
            ),
            (
                "GA platform-optimised kernel",
                {
                    "string": "xgene-uboot-mustang-ga-%s" % version_str,
                    "expected": version_tuple
                    + tuple([NOT_OLD_HWE_WEIGHT + PLATFORM_WEIGHT]),
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
                            NOT_OLD_HWE_WEIGHT
                            + FLAVOURED_WEIGHT
                            + PLATFORM_WEIGHT
                        ]
                    ),
                },
            ),
            (
                "HWE kernel",
                {
                    "string": "hwe-%s" % version_str,
                    "expected": version_tuple
                    + tuple([HWE_CHANNEL_WEIGHT + NOT_OLD_HWE_WEIGHT]),
                },
            ),
            (
                "HWE edge kernel",
                {
                    "string": "hwe-%s-edge" % version_str,
                    "expected": version_tuple
                    + tuple([HWE_EDGE_CHANNEL_WEIGHT + NOT_OLD_HWE_WEIGHT]),
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
                            + NOT_OLD_HWE_WEIGHT
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
                            + NOT_OLD_HWE_WEIGHT
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
                            + NOT_OLD_HWE_WEIGHT
                            + PLATFORM_WEIGHT
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
                            + NOT_OLD_HWE_WEIGHT
                            + PLATFORM_WEIGHT
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
                            + NOT_OLD_HWE_WEIGHT
                            + FLAVOURED_WEIGHT
                            + PLATFORM_WEIGHT
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
                            + NOT_OLD_HWE_WEIGHT
                            + FLAVOURED_WEIGHT
                            + PLATFORM_WEIGHT
                        ]
                    ),
                },
            ),
            (
                "Rolling kernel",
                {
                    "string": "hwe-rolling",
                    "expected": tuple(
                        [999, 999, HWE_CHANNEL_WEIGHT + NOT_OLD_HWE_WEIGHT]
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
                            HWE_EDGE_CHANNEL_WEIGHT + NOT_OLD_HWE_WEIGHT,
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
                            + NOT_OLD_HWE_WEIGHT
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
                            + NOT_OLD_HWE_WEIGHT
                            + FLAVOURED_WEIGHT,
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


class TestValidateHweKernel(MAASServerTestCase):
    def test_validate_hwe_kernel_returns_default_kernel(self):
        self.patch(
            BootResource.objects, "get_usable_hwe_kernels"
        ).return_value = ("hwe-t", "hwe-u")
        hwe_kernel = validate_hwe_kernel(
            None, None, "amd64/generic", "ubuntu", "trusty"
        )
        self.assertEqual(hwe_kernel, "hwe-t")

    def test_validate_hwe_kernel_set_kernel(self):
        self.patch(
            BootResource.objects, "get_usable_hwe_kernels"
        ).return_value = ("hwe-t", "hwe-v")
        hwe_kernel = validate_hwe_kernel(
            "hwe-v", None, "amd64/generic", "ubuntu", "trusty"
        )
        self.assertEqual(hwe_kernel, "hwe-v")

    def test_validate_hwe_kernel_accepts_ga_kernel(self):
        self.patch(
            BootResource.objects, "get_usable_hwe_kernels"
        ).return_value = ("ga-16.04",)
        hwe_kernel = validate_hwe_kernel(
            "ga-16.04", None, "amd64/generic", "ubuntu", "xenial"
        )
        self.assertEqual(hwe_kernel, "ga-16.04")

    def test_validate_hwe_kernel_fails_with_nongeneric_arch_and_kernel(self):
        exception_raised = False
        try:
            validate_hwe_kernel(
                "hwe-v", None, "armfh/hardbank", "ubuntu", "trusty"
            )
        except ValidationError as e:
            self.assertEqual(
                "Subarchitecture(hardbank) must be generic when setting "
                + "hwe_kernel.",
                e.message,
            )
            exception_raised = True
        self.assertTrue(exception_raised)

    def test_validate_hwe_kernel_fails_with_missing_hwe_kernel(self):
        exception_raised = False
        self.patch(
            BootResource.objects, "get_usable_hwe_kernels"
        ).return_value = ("hwe-t", "hwe-u")
        try:
            validate_hwe_kernel(
                "hwe-v", None, "amd64/generic", "ubuntu", "trusty"
            )
        except ValidationError as e:
            self.assertEqual(
                "hwe-v is not available for ubuntu/trusty on amd64/generic.",
                e.message,
            )
            exception_raised = True
        self.assertTrue(exception_raised)

    def test_validate_hwe_kernel_fails_with_old_kernel_and_newer_release(self):
        exception_raised = False
        self.patch(
            BootResource.objects, "get_usable_hwe_kernels"
        ).return_value = ("hwe-t", "hwe-v")
        try:
            validate_hwe_kernel(
                "hwe-t", None, "amd64/generic", "ubuntu", "vivid"
            )
        except ValidationError as e:
            self.assertEqual(
                "hwe-t is too old to use on ubuntu/vivid.", e.message
            )
            exception_raised = True
        self.assertTrue(exception_raised)

    def test_validate_hwe_kern_fails_with_old_kern_and_new_min_hwe_kern(self):
        exception_raised = False
        self.patch(
            BootResource.objects, "get_usable_hwe_kernels"
        ).return_value = ("hwe-t", "hwe-v")
        try:
            validate_hwe_kernel(
                "hwe-t", "hwe-v", "amd64/generic", "ubuntu", "precise"
            )
        except ValidationError as e:
            self.assertEqual(
                "hwe_kernel(hwe-t) is older than min_hwe_kernel(hwe-v).",
                e.message,
            )
            exception_raised = True
        self.assertTrue(exception_raised)

    def test_validate_hwe_kernel_fails_with_no_avalible_kernels(self):
        exception_raised = False
        self.patch(
            BootResource.objects, "get_usable_hwe_kernels"
        ).return_value = ("hwe-t", "hwe-v")
        try:
            validate_hwe_kernel(
                "hwe-t", "hwe-v", "amd64/generic", "ubuntu", "precise"
            )
        except ValidationError as e:
            self.assertEqual(
                "hwe_kernel(hwe-t) is older than min_hwe_kernel(hwe-v).",
                e.message,
            )
            exception_raised = True
        self.assertTrue(exception_raised)

    def test_validate_hwe_kern_fails_with_old_release_and_newer_hwe_kern(self):
        exception_raised = False
        try:
            validate_hwe_kernel(
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

    def test_validate_hwe_kern_always_sets_kern_with_commissionable_os(self):
        self.patch(
            BootResource.objects, "get_usable_hwe_kernels"
        ).return_value = ("hwe-t", "hwe-v")
        mock_get_config = self.patch(Config.objects, "get_config")
        mock_get_config.return_value = "trusty"
        kernel = validate_hwe_kernel(
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

    def test_validate_hwe_kern_sets_hwe_kern_to_min_hwe_kern_for_edge(self):
        # Regression test for LP:1654412
        mock_get_usable_hwe_kernels = self.patch(
            BootResource.objects, "get_usable_hwe_kernels"
        )
        mock_get_usable_hwe_kernels.return_value = (
            "hwe-16.04",
            "hwe-16.04-edge",
        )
        arch = factory.make_name("arch")

        kernel = validate_hwe_kernel(
            None, "hwe-16.04-edge", "%s/generic" % arch, "ubuntu", "xenial"
        )

        self.assertEqual("hwe-16.04-edge", kernel)
        self.assertThat(
            mock_get_usable_hwe_kernels,
            MockCalledOnceWith("ubuntu/xenial", arch, "generic"),
        )

    def test_validate_hwe_kern_uses_base_image_for_lookup_with_custom_images(
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
        kernel = validate_hwe_kernel(
            None, None, custom_resource.architecture, osystem, series
        )
        self.assertEqual("ga-18.04", kernel)


class TestValidateMinHweKernel(MAASServerTestCase):
    def test_validates_kernel(self):
        kernel = factory.make_kernel_string(generic_only=True)
        self.patch(
            BootResource.objects, "get_supported_hwe_kernels"
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
