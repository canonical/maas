# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from crochet import TimeoutError

from maasserver import forms
from maasserver.clusterrpc.driver_parameters import get_driver_choices
from maasserver.enum import BOOT_RESOURCE_TYPE, NODE_STATUS
from maasserver.forms import (
    AdminMachineForm,
    AdminMachineWithMACAddressesForm,
    BLANK_CHOICE,
    MachineForm,
    pick_default_architecture,
)
from maasserver.models import NodeKey
from maasserver.testing.architecture import (
    make_usable_architecture,
    patch_usable_architectures,
)
from maasserver.testing.factory import factory
from maasserver.testing.osystems import (
    make_osystem_with_releases,
    make_usable_osystem,
    patch_usable_osystems,
)
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import post_commit_hooks
from provisioningserver.certificates import Certificate
from provisioningserver.rpc.exceptions import (
    NoConnectionsAvailable,
    NoSuchOperatingSystem,
)
from provisioningserver.testing.certificates import get_sample_cert
from provisioningserver.testing.os import make_osystem


class FakeRequest:
    def __init__(self, user):
        self.user = user


class TestMachineForm(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        self.region = factory.make_RegionController()

    def test_contains_limited_set_of_fields(self):
        form = MachineForm()

        self.assertEqual(
            {
                "hostname",
                "domain",
                "architecture",
                "osystem",
                "distro_series",
                "license_key",
                "disable_ipv4",
                "swap_size",
                "min_hwe_kernel",
                "hwe_kernel",
                "install_rackd",
                "ephemeral_deploy",
                "enable_hw_sync",
                "commission",
                "enable_kernel_crash_dump",
            },
            form.fields.keys(),
        )

    def test_accepts_usable_architecture(self):
        arch = make_usable_architecture(self)
        form = MachineForm(
            data={"hostname": factory.make_name("host"), "architecture": arch}
        )
        self.assertTrue(form.is_valid(), form._errors)

    def test_rejects_unusable_architecture(self):
        patch_usable_architectures(self)
        form = MachineForm(
            data={
                "hostname": factory.make_name("host"),
                "architecture": factory.make_name("arch"),
            }
        )
        self.assertFalse(form.is_valid())
        self.assertEqual({"architecture"}, form._errors.keys())

    def test_starts_with_default_architecture(self):
        arches = sorted(factory.make_name("arch") for _ in range(5))
        patch_usable_architectures(self, arches)
        form = MachineForm()
        self.assertEqual(
            pick_default_architecture(arches),
            form.fields["architecture"].initial,
        )

    def test_form_validates_hwe_kernel_by_passing_invalid_config(self):
        user = factory.make_User()
        self.client.login(user=user)
        node = factory.make_Node(owner=user)
        osystem, releases = make_usable_osystem(self)
        form = MachineForm(
            data={
                "hostname": factory.make_name("host"),
                "architecture": make_usable_architecture(self),
                "osystem": osystem,
                "min_hwe_kernel": "hwe-t",
                "hwe_kernel": "hwe-p",
            },
            instance=node,
        )
        self.assertFalse(form.is_valid())

    def test_form_validates_min_hwe_kernel_by_passing_invalid_config(self):
        node = factory.make_Node(min_hwe_kernel="hwe-t")
        form = MachineForm(instance=node)
        self.assertFalse(form.is_valid())

    def test_adds_blank_default_when_no_arches_available(self):
        patch_usable_architectures(self, [])
        form = MachineForm()
        self.assertEqual([BLANK_CHOICE], form.fields["architecture"].choices)

    def test_accepts_osystem(self):
        user = factory.make_User()
        self.client.login(user=user)
        node = factory.make_Node(owner=user)
        osystem, releases = make_usable_osystem(self)
        form = MachineForm(
            data={
                "hostname": factory.make_name("host"),
                "architecture": make_usable_architecture(self),
                "osystem": osystem,
            },
            instance=node,
        )
        self.assertTrue(form.is_valid(), form._errors)

    def test_rejects_invalid_osystem(self):
        user = factory.make_User()
        self.client.login(user=user)
        node = factory.make_Node(owner=user)
        patch_usable_osystems(self)
        form = MachineForm(
            data={
                "hostname": factory.make_name("host"),
                "architecture": make_usable_architecture(self),
                "osystem": factory.make_name("os"),
            },
            instance=node,
        )
        self.assertFalse(form.is_valid())
        self.assertEqual({"osystem"}, form._errors.keys())

    def test_starts_with_default_osystem(self):
        user = factory.make_User()
        self.client.login(user=user)
        node = factory.make_Node(owner=user)
        osystems = [make_osystem_with_releases(self) for _ in range(5)]
        patch_usable_osystems(self, osystems)
        form = MachineForm(instance=node)
        self.assertEqual("", form.fields["osystem"].initial)

    def test_accepts_osystem_distro_series(self):
        user = factory.make_User()
        self.client.login(user=user)
        node = factory.make_Node(owner=user)
        osystem, releases = make_usable_osystem(self)
        release = releases[0]
        form = MachineForm(
            data={
                "hostname": factory.make_name("host"),
                "architecture": make_usable_architecture(self),
                "osystem": osystem,
                "distro_series": f"{osystem}/{release}",
            },
            instance=node,
        )
        self.assertTrue(form.is_valid(), form._errors)

    def test_rejects_invalid_osystem_distro_series(self):
        user = factory.make_User()
        self.client.login(user=user)
        node = factory.make_Node(owner=user)
        osystem, releases = make_usable_osystem(self)
        release = factory.make_name("release")
        form = MachineForm(
            data={
                "hostname": factory.make_name("host"),
                "architecture": make_usable_architecture(self),
                "osystem": osystem,
                "distro_series": f"{osystem}/{release}",
            },
            instance=node,
        )
        self.assertFalse(form.is_valid())
        self.assertEqual({"distro_series"}, form._errors.keys())

    def test_set_distro_series_accepts_short_distro_series(self):
        user = factory.make_User()
        self.client.login(user=user)
        node = factory.make_Node(owner=user)
        release = factory.make_name("release")
        make_usable_osystem(
            self, releases=[release + "6", release + "0", release + "3"]
        )
        form = MachineForm(
            data={
                "hostname": factory.make_name("host"),
                "architecture": make_usable_architecture(self),
            },
            instance=node,
        )
        form.set_distro_series(release)
        with post_commit_hooks:
            form.save()
        self.assertEqual(release + "6", node.distro_series)

    def test_set_distro_series_accepts_short_alias_series(self):
        user = factory.make_User()
        self.client.login(user=user)
        node = factory.make_Node(owner=user)
        release = factory.make_name("release")
        alias = factory.make_name("alias")
        make_usable_osystem(
            self,
            releases=[release],
            aliases=[alias],
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
        )
        form = MachineForm(
            data={
                "hostname": factory.make_name("host"),
                "architecture": make_usable_architecture(self),
            },
            instance=node,
        )
        form.set_distro_series(alias)
        with post_commit_hooks:
            form.save()
        self.assertEqual(release, node.distro_series)

    def test_set_distro_series_accepts_full_alias_series(self):
        user = factory.make_User()
        self.client.login(user=user)
        node = factory.make_Node(owner=user)
        release = "noble"
        alias = "24.04"
        make_usable_osystem(
            self,
            osystem_name="ubuntu",
            releases=[release],
            aliases=[alias],
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
        )
        form = MachineForm(
            data={
                "hostname": factory.make_name("host"),
                "architecture": make_usable_architecture(self),
            },
            instance=node,
        )
        form.set_distro_series(f"ubuntu/{alias}")
        with post_commit_hooks:
            form.save()
        self.assertEqual(release, node.distro_series)

    def test_set_distro_series_doesnt_allow_short_ubuntu_series(self):
        user = factory.make_User()
        self.client.login(user=user)
        node = factory.make_Node(owner=user)
        make_usable_osystem(self, osystem_name="ubuntu", releases=["trusty"])
        form = MachineForm(
            data={
                "hostname": factory.make_name("host"),
                "architecture": make_usable_architecture(self),
            },
            instance=node,
        )
        form.set_distro_series("trust")
        self.assertFalse(form.is_valid())

    def test_starts_with_default_distro_series(self):
        user = factory.make_User()
        self.client.login(user=user)
        node = factory.make_Node(owner=user)
        osystems = [make_osystem_with_releases(self) for _ in range(5)]
        patch_usable_osystems(self, osystems)
        form = MachineForm(instance=node)
        self.assertEqual("", form.fields["distro_series"].initial)

    def test_rejects_mismatch_osystem_distro_series(self):
        user = factory.make_User()
        self.client.login(user=user)
        node = factory.make_Node(owner=user)
        osystem, releases = make_usable_osystem(self)
        release = releases[0]
        invalid = factory.make_name("invalid_os")
        form = MachineForm(
            data={
                "hostname": factory.make_name("host"),
                "architecture": make_usable_architecture(self),
                "osystem": osystem,
                "distro_series": f"{invalid}/{release}",
            },
            instance=node,
        )
        self.assertFalse(form.is_valid())
        self.assertEqual({"distro_series"}, form._errors.keys())

    def test_rejects_enable_hw_sync_on_non_linux_osystem(self):
        user = factory.make_User()
        self.client.login(user=user)
        machine = factory.make_Machine(owner=user)
        osystem, releases = make_usable_osystem(self)
        release = releases[0]
        form = MachineForm(
            data={
                "hostname": factory.make_name("host"),
                "architecture": make_usable_architecture(self),
                "enable_hw_sync": True,
                "osystem": osystem,
                "distro_series": f"{osystem}/{release}",
            },
            instance=machine,
        )
        self.assertFalse(form.is_valid())
        self.assertEqual({"enable_hw_sync"}, form._errors.keys())

    def test_accepts_enable_hw_sync_on_linux_osystem(self):
        user = factory.make_User()
        self.client.login(user=user)
        machine = factory.make_Machine(owner=user)
        release_names = ("noble", "8", "8", "my-custom")
        osystem_names = ("ubuntu", "centos", "rhel", "custom")
        for osystem_name, release_name in zip(osystem_names, release_names):
            make_usable_osystem(
                self, osystem_name=osystem_name, releases=[release_name]
            )
            form = MachineForm(
                data={
                    "hostname": factory.make_name("host"),
                    "architecture": make_usable_architecture(self),
                    "enable_hw_sync": True,
                    "osystem": osystem_name,
                    "distro_series": f"{osystem_name}/{release_name}",
                },
                instance=machine,
            )
            self.assertTrue(form.is_valid(), form._errors.keys())

    def test_rejects_when_validate_license_key_returns_False(self):
        user = factory.make_User()
        self.client.login(user=user)
        node = factory.make_Node(owner=user)
        osystem = factory.make_name("osystem")
        release = factory.make_name("release")
        distro_series = f"{osystem}/{release}"
        make_osystem(self, osystem, [release])
        factory.make_BootResource(name=distro_series)
        license_key = factory.make_name("key")
        mock_validate = self.patch(forms, "validate_license_key")
        mock_validate.return_value = False
        form = MachineForm(
            data={
                "hostname": factory.make_name("host"),
                "architecture": make_usable_architecture(self),
                "osystem": osystem,
                "distro_series": distro_series,
                "license_key": license_key,
            },
            instance=node,
        )
        self.assertFalse(form.is_valid())
        self.assertEqual({"license_key"}, form._errors.keys())

    def test_rejects_when_validate_license_key_for_returns_False(self):
        user = factory.make_User()
        self.client.login(user=user)
        node = factory.make_Node(owner=user)
        osystem = factory.make_name("osystem")
        release = factory.make_name("release")
        distro_series = f"{osystem}/{release}"
        make_osystem(self, osystem, [release])
        factory.make_BootResource(name=distro_series)
        license_key = factory.make_name("key")
        mock_validate_for = self.patch(forms, "validate_license_key")
        mock_validate_for.return_value = False
        form = MachineForm(
            data={
                "architecture": make_usable_architecture(self),
                "osystem": osystem,
                "distro_series": distro_series,
                "license_key": license_key,
            },
            instance=node,
        )
        self.assertFalse(form.is_valid())
        self.assertEqual({"license_key"}, form._errors.keys())

    def test_rejects_when_validate_license_key_for_raise_no_connection(self):
        user = factory.make_User()
        self.client.login(user=user)
        node = factory.make_Node(owner=user)
        osystem = factory.make_name("osystem")
        release = factory.make_name("release")
        distro_series = f"{osystem}/{release}"
        make_osystem(self, osystem, [release])
        factory.make_BootResource(name=distro_series)
        license_key = factory.make_name("key")
        mock_validate_for = self.patch(forms, "validate_license_key")
        mock_validate_for.side_effect = NoConnectionsAvailable()
        form = MachineForm(
            data={
                "architecture": make_usable_architecture(self),
                "osystem": osystem,
                "distro_series": distro_series,
                "license_key": license_key,
            },
            instance=node,
        )
        self.assertFalse(form.is_valid())
        self.assertEqual({"license_key"}, form._errors.keys())

    def test_rejects_when_validate_license_key_for_raise_timeout(self):
        user = factory.make_User()
        self.client.login(user=user)
        node = factory.make_Node(owner=user)
        osystem = factory.make_name("osystem")
        release = factory.make_name("release")
        distro_series = f"{osystem}/{release}"
        make_osystem(self, osystem, [release])
        factory.make_BootResource(name=distro_series)
        license_key = factory.make_name("key")
        mock_validate_for = self.patch(forms, "validate_license_key")
        mock_validate_for.side_effect = TimeoutError()
        form = MachineForm(
            data={
                "architecture": make_usable_architecture(self),
                "osystem": osystem,
                "distro_series": distro_series,
                "license_key": license_key,
            },
            instance=node,
        )
        self.assertFalse(form.is_valid())
        self.assertEqual({"license_key"}, form._errors.keys())

    def test_rejects_when_validate_license_key_for_raise_no_os(self):
        user = factory.make_User()
        self.client.login(user=user)
        node = factory.make_Node(owner=user)
        osystem = factory.make_name("osystem")
        release = factory.make_name("release")
        distro_series = f"{osystem}/{release}"
        make_osystem(self, osystem, [release])
        factory.make_BootResource(name=distro_series)
        license_key = factory.make_name("key")
        mock_validate_for = self.patch(forms, "validate_license_key")
        mock_validate_for.side_effect = NoSuchOperatingSystem()
        form = MachineForm(
            data={
                "architecture": make_usable_architecture(self),
                "osystem": osystem,
                "distro_series": distro_series,
                "license_key": license_key,
            },
            instance=node,
        )
        self.assertFalse(form.is_valid())
        self.assertEqual({"license_key"}, form._errors.keys())

    def test_rejects_invalid_osystem_and_distro_series(self):
        user = factory.make_User()
        self.client.login(user=user)
        node = factory.make_Node(owner=user)
        osystem = factory.make_name("osystem")
        release = factory.make_name("release")
        distro_series = f"{osystem}/{release}"
        make_osystem(self, osystem, [release])

        form = MachineForm(
            data={
                "architecture": make_usable_architecture(self),
                "osystem": osystem,
                "distro_series": distro_series,
            },
            instance=node,
        )
        self.assertFalse(form.is_valid())

    def test_accepts_osystem_and_distro_series_if_deployed(self):
        user = factory.make_User()
        self.client.login(user=user)
        node = factory.make_Node(owner=user, status=NODE_STATUS.DEPLOYED)
        osystem = factory.make_name("osystem")
        release = factory.make_name("release")
        distro_series = f"{osystem}/{release}"
        make_osystem(self, osystem, [release])

        form = MachineForm(
            data={
                "architecture": make_usable_architecture(self),
                "osystem": osystem,
                "distro_series": distro_series,
            },
            instance=node,
        )
        self.assertTrue(form.is_valid(), form._errors)


class TestAdminMachineForm(MAASServerTestCase):
    def test_AdminMachineForm_contains_limited_set_of_fields(self):
        user = factory.make_User()
        self.client.login(user=user)
        node = factory.make_Node(owner=user)
        form = AdminMachineForm(instance=node)

        self.assertEqual(
            {
                "hostname",
                "description",
                "domain",
                "architecture",
                "osystem",
                "distro_series",
                "license_key",
                "disable_ipv4",
                "swap_size",
                "min_hwe_kernel",
                "hwe_kernel",
                "install_rackd",
                "ephemeral_deploy",
                "cpu_count",
                "memory",
                "zone",
                "power_parameters",
                "power_type",
                "pool",
                "commission",
                "enable_hw_sync",
                "enable_kernel_crash_dump",
            },
            form.fields.keys(),
        )

    def test_AdminMachineForm_populates_power_type_choices(self):
        form = AdminMachineForm()
        self.assertEqual(
            [""] + [choice[0] for choice in get_driver_choices()],
            [choice[0] for choice in form.fields["power_type"].choices],
        )

    def test_AdminMachineForm_new_machine_deployed(self):
        hostname = factory.make_string()
        user = factory.make_admin()
        form = AdminMachineForm(
            request=FakeRequest(user),
            data={
                "hostname": hostname,
                "deployed": True,
            },
        )
        self.assertTrue(form.is_valid())
        node = form.save()
        self.assertEqual(node.status, NODE_STATUS.DEPLOYED)
        self.assertEqual(user, node.owner)

    def test_AdminMachineForm_new_machine_no_deployed_no_owner(self):
        hostname = factory.make_string()
        user = factory.make_admin()
        form = AdminMachineForm(
            request=FakeRequest(user),
            data={
                "hostname": hostname,
                "architecture": make_usable_architecture(self),
                "power_type": "ipmi",
                "power_parameters_field": factory.make_string(),
                "power_parameters_skip_check": "true",
            },
        )
        self.assertTrue(form.is_valid(), form.errors)

        with post_commit_hooks:
            node = form.save()
        self.assertEqual(node.status, NODE_STATUS.NEW)
        self.assertIsNone(node.owner)

    def test_AdminMachineForm_populates_power_type_initial(self):
        node = factory.make_Node()
        form = AdminMachineForm(instance=node)
        self.assertEqual(node.power_type, form.fields["power_type"].initial)

    def test_AdminMachineForm_changes_power_parameters_with_skip_check(self):
        node = factory.make_Node(interface=True)
        hostname = factory.make_string()
        power_type = factory.pick_power_type(but_not=["lxd"])
        power_parameters_field = factory.make_string()
        arch = make_usable_architecture(self)
        form = AdminMachineForm(
            data={
                "hostname": hostname,
                "architecture": arch,
                "power_type": power_type,
                "power_parameters_field": power_parameters_field,
                "power_parameters_skip_check": "true",
            },
            instance=node,
        )

        with post_commit_hooks:
            form.save()

        self.assertEqual(
            (hostname, power_type, {"field": power_parameters_field}),
            (node.hostname, node.power_type, node.get_power_parameters()),
        )

    def test_AdminMachineForm_doesnt_changes_power_parameters(self):
        power_parameters = {"test": factory.make_name("test")}
        node = factory.make_Node(power_parameters=power_parameters)
        hostname = factory.make_string()
        arch = make_usable_architecture(self)
        form = AdminMachineForm(
            data={
                "hostname": hostname,
                "architecture": arch,
                "power_parameters_skip_check": "true",
            },
            instance=node,
        )

        with post_commit_hooks:
            node = form.save()
        self.assertEqual(power_parameters, node.get_power_parameters())

    def test_AdminMachineForm_doesnt_change_power_type(self):
        power_type = factory.pick_power_type(but_not=["lxd"])
        node = factory.make_Node(power_type=power_type)
        hostname = factory.make_string()
        arch = make_usable_architecture(self)
        form = AdminMachineForm(
            data={
                "hostname": hostname,
                "architecture": arch,
                "power_parameters_skip_check": "true",
            },
            instance=node,
        )

        with post_commit_hooks:
            node = form.save()
        self.assertEqual(power_type, node.power_type)

    def test_AdminMachineForm_changes_power_type(self):
        node = factory.make_Node(interface=True)
        hostname = factory.make_string()
        power_type = factory.pick_power_type(but_not=["lxd"])
        arch = make_usable_architecture(self)
        form = AdminMachineForm(
            data={
                "hostname": hostname,
                "architecture": arch,
                "power_type": power_type,
                "power_parameters_skip_check": "true",
            },
            instance=node,
        )

        with post_commit_hooks:
            node = form.save()
        self.assertEqual(power_type, node.power_type)

    def test_AdminMachineForm_needs_interface_for_power_types(self):
        node = factory.make_Node(power_type=None)
        arch = make_usable_architecture(self)
        form = AdminMachineForm(
            data={
                "architecture": arch,
                "power_type": "manual",
                "power_parameters_skip_check": "true",
            },
            instance=node,
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            dict(form.errors),
            {
                "power_type": [
                    "Can't set power type to manual without network interfaces"
                ]
            },
        )

    def test_AdminMachineForm_creates_scriptset_for_deployed(self):
        hostname = factory.make_string()
        user = factory.make_admin()
        form = AdminMachineForm(
            request=FakeRequest(user),
            data={
                "hostname": hostname,
                "deployed": True,
            },
        )

        with post_commit_hooks:
            machine = form.save()
        self.assertIsNotNone(machine.current_commissioning_script_set)

    def test_AdminMachineForm_creates_node_token_for_deployed(self):
        hostname = factory.make_string()
        user = factory.make_admin()
        form = AdminMachineForm(
            request=FakeRequest(user),
            data={
                "hostname": hostname,
                "deployed": True,
            },
        )

        with post_commit_hooks:
            machine = form.save()
        self.assertTrue(NodeKey.objects.filter(node=machine).exists())


class TestAdminMachineWithMACAddressForm(MAASServerTestCase):
    def test_generate_certs_for_lxd_power_type(self):
        sample_cert = get_sample_cert()
        self.patch_autospec(forms, "generate_certificate").return_value = (
            sample_cert
        )
        hostname = factory.make_string()
        form = AdminMachineWithMACAddressesForm(
            data={
                "architecture": make_usable_architecture(self),
                "hostname": hostname,
                "mac_addresses": [factory.make_mac_address()],
                "power_type": "lxd",
                "power_parameters": {
                    "power_address": "1.2.3.4",
                    "instance_name": hostname,
                },
            },
        )
        self.assertTrue(form.is_valid())

        with post_commit_hooks:
            machine = form.save()

        power_params = machine.bmc.get_power_parameters()
        self.assertIn("certificate", power_params)
        self.assertIn("key", power_params)
        cert = Certificate.from_pem(
            power_params["certificate"], power_params["key"]
        )
        self.assertEqual(cert.cn(), sample_cert.cn())
        # cert/key are not per-instance parameters
        self.assertNotIn(
            "certificate", machine.get_instance_power_parameters()
        )
        self.assertNotIn("key", machine.get_instance_power_parameters())
