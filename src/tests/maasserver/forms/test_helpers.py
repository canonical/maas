# Copyright 2014-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Gap-free tests for `maasserver.forms` helpers, split out of the legacy
`src/maasserver/forms/tests/test_helpers.py`: the legacy `TestMAASModelForm`
class stays there under nose (idea 002), while this class runs under
pytest."""

from maasserver.enum import BOOT_RESOURCE_TYPE
from maasserver.forms import (
    AdminMachineWithMACAddressesForm,
    get_machine_create_form,
    list_all_usable_architectures,
    MachineWithPowerAndMACAddressesForm,
    pick_default_architecture,
    remove_None_values,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestHelpers(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        self.region = factory.make_RegionController()

    def make_usable_boot_resource(self, arch=None, subarch=None):
        """Create a set of boot resources, so the architecture becomes usable.

        This will make the resources' architecture show up in the list of
        usable architectures.
        """
        if arch is None:
            arch = factory.make_name("arch")
        if subarch is None:
            subarch = factory.make_name("subarch")
        for purpose in ["install", "commissioning"]:  # noqa: B007
            architecture = f"{arch}/{subarch}"
            factory.make_usable_boot_resource(
                rtype=BOOT_RESOURCE_TYPE.SYNCED, architecture=architecture
            )

    def test_list_all_usable_architectures_combines(self):
        arches = [
            (factory.make_name("arch"), factory.make_name("subarch"))
            for _ in range(3)
        ]
        expected = []
        for arch, subarch in arches:
            self.make_usable_boot_resource(arch=arch, subarch=subarch)
            expected.append(f"{arch}/{subarch}")
            expected.append(f"{arch}/generic")
        self.assertCountEqual(expected, list_all_usable_architectures())

    def test_list_all_usable_architectures_sorts_output(self):
        arches = [
            (factory.make_name("arch"), factory.make_name("subarch"))
            for _ in range(3)
        ]
        expected = []
        for arch, subarch in arches:
            self.make_usable_boot_resource(arch=arch, subarch=subarch)
            expected.append(f"{arch}/{subarch}")
            expected.append(f"{arch}/generic")

        self.assertCountEqual(expected, list_all_usable_architectures())

    def test_list_all_usable_architectures_returns_no_duplicates(self):
        arch = factory.make_name("arch")
        subarch = factory.make_name("subarch")
        self.make_usable_boot_resource(arch=arch, subarch=subarch)
        self.make_usable_boot_resource(arch=arch, subarch=subarch)
        self.assertEqual(
            [f"{arch}/generic", f"{arch}/{subarch}"],
            list_all_usable_architectures(),
        )

    def test_pick_default_architecture_returns_empty_if_no_options(self):
        self.assertEqual("", pick_default_architecture([]))

    def test_pick_default_architecture_prefers_i386_generic_if_usable(self):
        self.assertEqual(
            "i386/generic",
            pick_default_architecture(
                ["amd64/generic", "i386/generic", "mips/generic"]
            ),
        )

    def test_pick_default_architecture_falls_back_to_first_option(self):
        arches = [factory.make_name("arch") for _ in range(5)]
        self.assertEqual(arches[0], pick_default_architecture(arches))

    def test_remove_None_values_removes_None_values_in_dict(self):
        random_input = factory.make_string()
        self.assertEqual(
            {random_input: random_input},
            remove_None_values(
                {random_input: random_input, factory.make_string(): None}
            ),
        )

    def test_remove_None_values_leaves_empty_dict_untouched(self):
        self.assertEqual({}, remove_None_values({}))

    def test_get_machine_create_form_if_non_admin(self):
        user = factory.make_User()
        self.assertEqual(
            MachineWithPowerAndMACAddressesForm, get_machine_create_form(user)
        )

    def test_get_machine_create_form_if_admin(self):
        admin = factory.make_admin()
        self.assertEqual(
            AdminMachineWithMACAddressesForm, get_machine_create_form(admin)
        )
