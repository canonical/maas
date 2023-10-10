# Copyright 2015-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from unittest.mock import sentinel

from distro_info import UbuntuDistroInfo
import petname

from maasserver.enum import (
    BOND_LACP_RATE_CHOICES,
    BOND_MODE_CHOICES,
    BOND_XMIT_HASH_POLICY_CHOICES,
    BOOT_RESOURCE_TYPE,
    NODE_TYPE,
)
from maasserver.models import Config, ControllerInfo, PackageRepository
from maasserver.models.signals.testing import SignalsDisabled
from maasserver.node_action import ACTIONS_DICT
from maasserver.secrets import SecretManager
from maasserver.testing.factory import factory
from maasserver.testing.osystems import make_osystem_with_releases
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.base import DATETIME_FORMAT, dehydrate_datetime
from maasserver.websockets.handlers import general
from maasserver.websockets.handlers.general import GeneralHandler
from provisioningserver.boot import BootMethodRegistry
from provisioningserver.testing.certificates import get_sample_cert
from provisioningserver.utils.snap import SnapVersionsInfo
from provisioningserver.utils.version import MAASVersion


class TestGeneralHandler(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        factory.make_RegionController()
        # Disable boot sources signals otherwise the test fails due to unrun
        # post-commit tasks at the end of the test.
        self.useFixture(SignalsDisabled("bootsources"))

    def dehydrate_actions(self, actions, node_type=None):
        return [
            {
                "name": name,
                "title": action.display,
                "sentence": action.display_sentence,
                "type": action.action_type,
            }
            for name, action in actions.items()
            if node_type is None or node_type in action.for_type
        ]

    def make_boot_sources(self):
        kernels = []
        ubuntu = UbuntuDistroInfo()
        # LP: #1711191 - distro-info 0.16+ no longer returns dictionaries or
        # lists, and it now returns objects instead. As such, we need to
        # handle both cases for backwards compatibility.
        try:
            ubuntu_rows = ubuntu._rows
        except AttributeError:
            ubuntu_rows = [row.__dict__ for row in ubuntu._releases]
        for row in ubuntu_rows:
            release_year = int(row["version"].split(".")[0])
            if release_year < 12:
                continue
            elif release_year < 16:
                style = row["series"][0]
            else:
                style = row["version"]
            for kflavor in [
                "generic",
                "lowlatency",
                "edge",
                "lowlatency-edge",
            ]:
                if kflavor == "generic":
                    kernel = "hwe-%s" % style
                else:
                    kernel = f"hwe-{style}-{kflavor}"
                arch = factory.make_name("arch")
                architecture = f"{arch}/{kernel}"
                release = row["series"].split(" ")[0]
                factory.make_usable_boot_resource(
                    name="ubuntu/" + release,
                    kflavor=kflavor,
                    extra={"subarches": kernel},
                    architecture=architecture,
                    rtype=BOOT_RESOURCE_TYPE.SYNCED,
                )
                factory.make_BootSourceCache(
                    os="ubuntu", arch=arch, subarch=kernel, release=release
                )
                kernels.append((kernel, f"{release} ({kernel})"))
        return kernels

    def test_architectures(self):
        arches = []
        for _ in range(3):
            arch = factory.make_name("arch")
            subarch = factory.make_name("subarch")
            arches.append(f"{arch}/generic")
            arches.append(f"{arch}/{subarch}")
        for arch in arches:
            factory.make_usable_boot_resource(architecture=arch)
        handler = GeneralHandler(factory.make_User(), {}, None)
        self.assertCountEqual(arches, handler.architectures({}))

    def test_known_architectures(self):
        handler = GeneralHandler(factory.make_User(), {}, None)
        self.assertEqual(
            PackageRepository.objects.get_known_architectures(),
            handler.known_architectures({}),
        )

    def test_pockets_to_disable(self):
        handler = GeneralHandler(factory.make_User(), {}, None)
        self.assertEqual(
            PackageRepository.objects.get_pockets_to_disable(),
            handler.pockets_to_disable({}),
        )

    def test_components_to_disable(self):
        handler = GeneralHandler(factory.make_User(), {}, None)
        self.assertEqual(
            PackageRepository.objects.get_components_to_disable(),
            handler.components_to_disable({}),
        )

    def test_hwe_kernels(self):
        expected_output = self.make_boot_sources()
        handler = GeneralHandler(factory.make_User(), {}, None)
        self.assertCountEqual(
            expected_output,
            handler.hwe_kernels({}),
        )

    def test_hwe_min_kernels(self):
        expected_output = self.make_boot_sources()
        handler = GeneralHandler(factory.make_User(), {}, None)
        self.assertCountEqual(
            expected_output,
            handler.min_hwe_kernels({}),
        )

    def test_osinfo(self):
        handler = GeneralHandler(factory.make_User(), {}, None)
        osystem = make_osystem_with_releases(self)
        releases = [
            (
                "{}/{}".format(osystem["name"], release["name"]),
                release["title"],
            )
            for release in osystem["releases"]
        ]
        self.patch(general, "list_osystem_choices").return_value = [
            (osystem["name"], osystem["title"])
        ]
        self.patch(general, "list_release_choices").return_value = releases
        expected_osinfo = {
            "osystems": [(osystem["name"], osystem["title"])],
            "releases": releases,
            "kernels": {
                "ubuntu": {"focal": [("hwe-20.04", "focal (hwe-20.04)")]}
            },
            "default_osystem": Config.objects.get_config("default_osystem"),
            "default_release": Config.objects.get_config(
                "default_distro_series"
            ),
        }
        self.assertEqual(expected_osinfo, handler.osinfo({}))

    def test_machine_actions_for_admin(self):
        handler = GeneralHandler(factory.make_admin(), {}, None)
        actions_expected = self.dehydrate_actions(
            ACTIONS_DICT, NODE_TYPE.MACHINE
        )
        self.assertCountEqual(actions_expected, handler.machine_actions({}))

    def test_machine_actions_for_non_admin(self):
        handler = GeneralHandler(factory.make_User(), {}, None)
        self.assertCountEqual(
            {
                "release",
                "mark-broken",
                "on",
                "deploy",
                "acquire",
                "off",
                "lock",
                "unlock",
            },
            [action["name"] for action in handler.machine_actions({})],
        )

    def test_device_actions_for_admin(self):
        handler = GeneralHandler(factory.make_admin(), {}, None)
        self.assertCountEqual(
            {"set-zone", "delete"},
            [action["name"] for action in handler.device_actions({})],
        )

    def test_device_actions_for_non_admin(self):
        handler = GeneralHandler(factory.make_User(), {}, None)
        self.assertCountEqual(
            {"set-zone", "delete"},
            [action["name"] for action in handler.device_actions({})],
        )

    def test_region_controller_actions_for_admin(self):
        handler = GeneralHandler(factory.make_admin(), {}, None)
        self.assertCountEqual(
            {"set-zone", "delete"},
            [
                action["name"]
                for action in handler.region_controller_actions({})
            ],
        )

    def test_region_controller_actions_for_non_admin(self):
        handler = GeneralHandler(factory.make_User(), {}, None)
        self.assertEqual([], handler.region_controller_actions({}))

    def test_rack_controller_actions_for_admin(self):
        handler = GeneralHandler(factory.make_admin(), {}, None)
        self.assertCountEqual(
            [
                "delete",
                "import-images",
                "off",
                "on",
                "set-zone",
                "test",
                "override-failed-testing",
            ],
            [action["name"] for action in handler.rack_controller_actions({})],
        )

    def test_rack_controller_actions_for_non_admin(self):
        handler = GeneralHandler(factory.make_User(), {}, None)
        self.assertEqual([], handler.rack_controller_actions({}))

    def test_region_and_rack_controller_actions_for_admin(self):
        handler = GeneralHandler(factory.make_admin(), {}, None)
        self.assertCountEqual(
            ["set-zone", "delete", "import-images"],
            [
                action["name"]
                for action in handler.region_and_rack_controller_actions({})
            ],
        )

    def test_region_and_rack_controller_actions_for_non_admin(self):
        handler = GeneralHandler(factory.make_User(), {}, None)
        self.assertEqual([], handler.region_and_rack_controller_actions({}))

    def test_random_hostname_checks_hostname_existence(self):
        existing_node = factory.make_Node(hostname="hostname")
        hostnames = [existing_node.hostname, "new-hostname"]
        self.patch(petname, "Generate").side_effect = hostnames
        handler = GeneralHandler(factory.make_User(), {}, None)
        self.assertEqual("new-hostname", handler.random_hostname({}))

    def test_bond_options(self):
        handler = GeneralHandler(factory.make_User(), {}, None)
        self.assertEqual(
            {
                "modes": BOND_MODE_CHOICES,
                "lacp_rates": BOND_LACP_RATE_CHOICES,
                "xmit_hash_policies": BOND_XMIT_HASH_POLICY_CHOICES,
            },
            handler.bond_options({}),
        )

    def test_version(self):
        handler = GeneralHandler(factory.make_User(), {}, None)
        self.patch_autospec(
            general, "get_maas_version"
        ).return_value = MAASVersion.from_string("1.2.3~rc1")
        self.assertEqual(handler.version({}), "1.2.3~rc1")

    def test_target_version(self):
        controller = factory.make_RackController()
        ControllerInfo.objects.set_versions_info(
            controller,
            SnapVersionsInfo(
                current={
                    "version": "3.0.0~beta2-123-g.asdf",
                    "revision": "1234",
                },
                update={
                    "version": "3.0.0~beta3-456-g.cafe",
                    "revision": "5678",
                },
                channel="3.0/beta",
            ),
        )
        handler = GeneralHandler(factory.make_User(), {}, None)
        result = handler.target_version({})
        self.assertEqual(result["version"], "3.0.0~beta3-456-g.cafe")
        self.assertEqual(result["snap_channel"], "3.0/beta")
        self.assertIsNotNone(result["first_reported"])

    def test_target_version_snap_cohort(self):
        controller = factory.make_RackController()
        ControllerInfo.objects.set_versions_info(
            controller,
            SnapVersionsInfo(
                current={
                    "version": "3.0.0~beta2-123-g.asdf",
                    "revision": "1234",
                },
                channel="3.0/beta",
                cohort="abc",
            ),
        )
        handler = GeneralHandler(factory.make_User(), {}, None)
        result = handler.target_version({})
        self.assertEqual(result["snap_cohort"], "abc")

    def test_power_types(self):
        handler = GeneralHandler(factory.make_User(), {}, None)
        self.patch_autospec(
            general, "get_all_power_types"
        ).return_value = sentinel.types
        self.assertEqual(sentinel.types, handler.power_types({}))

    def test_release_options(self):
        handler = GeneralHandler(factory.make_User(), {}, None)
        erase = factory.pick_bool()
        secure_erase = factory.pick_bool()
        quick_erase = factory.pick_bool()
        Config.objects.set_config("enable_disk_erasing_on_release", erase)
        Config.objects.set_config("disk_erase_with_secure_erase", secure_erase)
        Config.objects.set_config("disk_erase_with_quick_erase", quick_erase)
        self.assertEqual(
            {
                "erase": erase,
                "secure_erase": secure_erase,
                "quick_erase": quick_erase,
            },
            handler.release_options({}),
        )

    def test_known_boot_architectures(self):
        handler = GeneralHandler(factory.make_User(), {}, None)
        self.assertEqual(
            [
                {
                    "name": boot_method.name,
                    "bios_boot_method": boot_method.bios_boot_method,
                    "bootloader_arches": "/".join(
                        boot_method.bootloader_arches
                    ),
                    "arch_octet": boot_method.arch_octet,
                    "protocol": (
                        "http"
                        if boot_method.http_url or boot_method.user_class
                        else "tftp"
                    ),
                }
                for _, boot_method in BootMethodRegistry
                if boot_method.arch_octet or boot_method.user_class
            ],
            handler.known_boot_architectures({}),
        )

    def test_generate_certificate_no_name(self):
        Config.objects.set_config("maas_name", "mymaas")
        handler = GeneralHandler(factory.make_User(), {}, None)
        mock_generate_certificate = self.patch_autospec(
            general, "generate_certificate"
        )
        handler.generate_client_certificate({})
        mock_generate_certificate.assert_called_once_with("mymaas")

    def test_generate_certificate_with_name(self):
        Config.objects.set_config("maas_name", "mymaas")
        handler = GeneralHandler(factory.make_User(), {}, None)
        mock_generate_certificate = self.patch_autospec(
            general, "generate_certificate"
        )
        handler.generate_client_certificate({"object_name": "mypod"})
        mock_generate_certificate.assert_called_once_with("mypod@mymaas")

    def test_generate_certificate_metadata(self):
        cert = get_sample_cert()
        handler = GeneralHandler(factory.make_User(), {}, None)
        self.patch(general, "generate_certificate").return_value = cert
        result = handler.generate_client_certificate({})
        self.assertEqual(result["fingerprint"], cert.cert_hash())
        self.assertEqual(
            result["expiration"], cert.expiration().strftime(DATETIME_FORMAT)
        )

    def test_tls_certificate(self):
        cert = get_sample_cert()
        SecretManager().set_composite_secret(
            "tls",
            {
                "key": cert.private_key_pem(),
                "cert": cert.certificate_pem(),
            },
        )
        handler = GeneralHandler(factory.make_User(), {}, None)
        result = handler.tls_certificate({})

        self.assertEqual(cert.cn(), result["CN"])
        self.assertEqual(cert.certificate_pem(), result["certificate"])
        self.assertEqual(
            dehydrate_datetime(cert.expiration()), result["expiration"]
        )
        self.assertEqual(cert.cert_hash(), result["fingerprint"])

        # ensure we don't leak anything else
        allowed_keys = ["CN", "certificate", "expiration", "fingerprint"]
        self.assertCountEqual(result.keys(), allowed_keys)

    def test_tls_certificate_tls_disabled(self):
        handler = GeneralHandler(factory.make_User(), {}, None)
        result = handler.tls_certificate({})

        self.assertIsNone(result)

    def test_vault_enabled(self):
        Config.objects.set_config("vault_enabled", True)
        handler = GeneralHandler(factory.make_User(), {}, None)
        result = handler.vault_enabled({})
        self.assertTrue(result)

    def test_vault_disabled(self):
        Config.objects.set_config("vault_enabled", False)
        handler = GeneralHandler(factory.make_User(), {}, None)
        result = handler.vault_enabled({})
        self.assertFalse(result)

    def test_vault_not_specified(self):
        handler = GeneralHandler(factory.make_User(), {}, None)
        result = handler.vault_enabled({})
        self.assertFalse(result)
