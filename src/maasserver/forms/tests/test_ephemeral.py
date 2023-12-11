# Copyright 2015-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for commission form."""

import random

from maasserver.enum import (
    NODE_STATUS,
    NODE_TYPE,
    NODE_TYPE_CHOICES,
    POWER_STATE,
)
from maasserver.forms.ephemeral import CommissionForm, TestForm
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from metadataserver.enum import SCRIPT_TYPE


class TestTestForm(MAASServerTestCase):
    def test_doesnt_require_anything(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED, interface=True)
        user = factory.make_admin()
        form = TestForm(instance=node, user=user, data={})
        self.assertTrue(form.is_valid(), form.errors)

    def test_not_allowed_in_bad_state(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYING, interface=True)
        user = factory.make_admin()
        form = TestForm(instance=node, user=user, data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual(
            {
                "__all__": [
                    "Test is not available because of the current state "
                    "of the node."
                ]
            },
            form.errors,
        )

    def test_calls_start_testing_if_already_on(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYED,
            power_state=POWER_STATE.ON,
            interface=True,
        )
        user = factory.make_admin()
        mock_start_testing = self.patch_autospec(node, "start_testing")
        form = TestForm(instance=node, user=user, data={})
        self.assertTrue(form.is_valid(), form.errors)
        node = form.save()
        mock_start_testing.assert_called_once_with(user, False, [], {})

    def test_calls_start_testing_with_options(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED, interface=True)
        user = factory.make_admin()
        enable_ssh = factory.pick_bool()
        testing_scripts = [
            factory.make_Script(script_type=SCRIPT_TYPE.TESTING).name
            for _ in range(3)
        ]
        mock_start_testing = self.patch_autospec(node, "start_testing")
        form = TestForm(
            instance=node,
            user=user,
            data={
                "enable_ssh": enable_ssh,
                "testing_scripts": ",".join(testing_scripts),
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        node = form.save()
        self.assertIsNotNone(node)
        mock_start_testing.assert_called_once_with(
            user, enable_ssh, testing_scripts, {}
        )

    def test_class_start_testing_with_storage_param(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYED, with_boot_disk=False, interface=True
        )
        bd = factory.make_PhysicalBlockDevice(node=node)
        user = factory.make_admin()
        script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING,
            parameters={"storage": {"type": "storage"}},
        )
        mock_start_testing = self.patch_autospec(node, "start_testing")
        input = random.choice(
            [
                str(bd.id),
                bd.name,
                bd.model,
                bd.serial,
                f"{bd.model}:{bd.serial}",
            ]
            + bd.tags
        )
        form = TestForm(
            instance=node,
            user=user,
            data={"testing_scripts": script.name, "storage": input},
        )
        self.assertTrue(form.is_valid(), form.errors)
        node = form.save()
        self.assertIsNotNone(node)
        mock_start_testing.assert_called_once_with(
            user, False, [script.name], {script.name: {"storage": input}}
        )

    def test_class_start_testing_with_storage_param_errors(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED, interface=True)
        user = factory.make_admin()
        script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING,
            parameters={"storage": {"type": "storage"}},
        )
        self.patch_autospec(node, "start_testing")
        form = TestForm(
            instance=node,
            user=user,
            data={
                "testing_scripts": script.name,
                "storage": factory.make_name("bad"),
            },
        )
        self.assertFalse(form.is_valid())

    def test_class_start_testing_with_interface_param(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED, interface=False)
        interface = factory.make_Interface(node=node)
        user = factory.make_admin()
        script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING,
            parameters={"interface": {"type": "interface"}},
        )
        mock_start_testing = self.patch_autospec(node, "start_testing")
        input = random.choice(
            [
                str(interface.id),
                interface.name,
                str(interface.mac_address),
                interface.vendor,
                interface.product,
                f"{interface.vendor}:{interface.product}",
            ]
            + interface.tags
        )
        form = TestForm(
            instance=node,
            user=user,
            data={"testing_scripts": script.name, "interface": input},
        )
        self.assertTrue(form.is_valid(), form.errors)
        node = form.save()
        self.assertIsNotNone(node)
        mock_start_testing.assert_called_once_with(
            user, False, [script.name], {script.name: {"interface": input}}
        )

    def test_class_start_testing_with_interface_param_errors(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED, interface=True)
        user = factory.make_admin()
        script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING,
            parameters={"interface": {"type": "interface"}},
        )
        self.patch_autospec(node, "start_testing")
        form = TestForm(
            instance=node,
            user=user,
            data={
                "testing_scripts": script.name,
                "interface": factory.make_name("bad"),
            },
        )
        self.assertFalse(form.is_valid())

    def test_class_start_testing_with_runtime_param(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED, interface=True)
        user = factory.make_admin()
        script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING,
            parameters={"runtime": {"type": "runtime"}},
        )
        mock_start_testing = self.patch_autospec(node, "start_testing")
        input = random.choice(["168:00:00", "10080:00", 604800])
        form = TestForm(
            instance=node,
            user=user,
            data={"testing_scripts": script.name, "runtime": input},
        )
        self.assertTrue(form.is_valid(), form.errors)
        node = form.save()
        self.assertIsNotNone(node)
        mock_start_testing.assert_called_once_with(
            user, False, [script.name], {script.name: {"runtime": 604800}}
        )

    def test_class_start_testing_with_runtime_param_errors(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED, interface=True)
        user = factory.make_admin()
        script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING,
            parameters={"runtime": {"type": "runtime"}},
        )
        self.patch_autospec(node, "start_testing")
        form = TestForm(
            instance=node,
            user=user,
            data={
                "testing_scripts": script.name,
                "runtime": factory.make_name("bad"),
            },
        )
        self.assertFalse(form.is_valid())

    def test_class_start_testing_with_url_param(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED, interface=True)
        user = factory.make_admin()
        script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING,
            parameters={"url": {"type": "url"}},
        )
        mock_start_testing = self.patch_autospec(node, "start_testing")
        input = factory.make_url(scheme="http")
        form = TestForm(
            instance=node,
            user=user,
            data={"testing_scripts": script.name, "url": input},
        )
        self.assertTrue(form.is_valid(), form.errors)
        node = form.save()
        self.assertIsNotNone(node)
        mock_start_testing.assert_called_once_with(
            user, False, [script.name], {script.name: {"url": input}}
        )

    def test_class_start_testing_with_string_param(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED, interface=True)
        user = factory.make_admin()
        script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING,
            parameters={"string": {"type": "string"}},
        )
        mock_start_testing = self.patch_autospec(node, "start_testing")
        input = factory.make_name("string")
        form = TestForm(
            instance=node,
            user=user,
            data={"testing_scripts": script.name, "string": input},
        )
        self.assertTrue(form.is_valid(), form.errors)
        node = form.save()
        self.assertIsNotNone(node)
        mock_start_testing.assert_called_once_with(
            user, False, [script.name], {script.name: {"string": input}}
        )

    def test_class_start_testing_with_password_param(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED, interface=True)
        user = factory.make_admin()
        script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING,
            parameters={"password": {"type": "password"}},
        )
        mock_start_testing = self.patch_autospec(node, "start_testing")
        input = factory.make_name("password")
        form = TestForm(
            instance=node,
            user=user,
            data={"testing_scripts": script.name, "password": input},
        )
        self.assertTrue(form.is_valid(), form.errors)
        node = form.save()
        self.assertIsNotNone(node)
        mock_start_testing.assert_called_once_with(
            user, False, [script.name], {script.name: {"password": input}}
        )

    def test_class_start_testing_with_choice_param(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED, interface=True)
        user = factory.make_admin()
        script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING,
            parameters={"choice": {"type": "choice", "choices": [1, 2, 3]}},
        )
        mock_start_testing = self.patch_autospec(node, "start_testing")
        input = random.randint(1, 3)
        form = TestForm(
            instance=node,
            user=user,
            data={"testing_scripts": script.name, "choice": input},
        )
        self.assertTrue(form.is_valid(), form.errors)
        node = form.save()
        self.assertIsNotNone(node)
        mock_start_testing.assert_called_once_with(
            user,
            False,
            [script.name],
            {script.name: {"choice": str(input)}},
        )

    def test_class_start_testing_with_boolean_param(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED, interface=True)
        user = factory.make_admin()
        script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING,
            parameters={
                "arg": {"type": "boolean", "argument_format": "--arg"}
            },
        )
        mock_start_testing = self.patch_autospec(node, "start_testing")
        form = TestForm(
            instance=node,
            user=user,
            data={"testing_scripts": script.name, "arg": True},
        )
        self.assertTrue(form.is_valid(), form.errors)
        node = form.save()
        self.assertIsNotNone(node)
        mock_start_testing.assert_called_once_with(
            user,
            False,
            [script.name],
            {script.name: {"arg": True}},
        )

    def test_class_start_testing_can_override_global_param(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED, interface=True)
        bd = factory.make_PhysicalBlockDevice(node=node)
        user = factory.make_admin()
        global_script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING,
            parameters={"storage": {"type": "storage"}},
        )
        script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING,
            parameters={"storage": {"type": "storage"}},
        )
        mock_start_testing = self.patch_autospec(node, "start_testing")
        input = random.choice(
            [
                str(bd.id),
                bd.name,
                bd.model,
                bd.serial,
                f"{bd.model}:{bd.serial}",
            ]
            + bd.tags
        )
        form = TestForm(
            instance=node,
            user=user,
            data={
                "testing_scripts": f"{global_script.name},{script.name}",
                "storage": "all",
                "%s_storage" % global_script.name: input,
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        node = form.save()
        self.assertIsNotNone(node)
        mock_start_testing.assert_called_once_with(
            user,
            False,
            [global_script.name, script.name],
            {
                script.name: {"storage": "all"},
                global_script.name: {"storage": input},
            },
        )

    def test_validates_testing_scripts(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED, interface=True)
        user = factory.make_admin()
        form = TestForm(
            instance=node,
            user=user,
            data={"testing_scripts": factory.make_name("script")},
        )
        self.assertFalse(form.is_valid())

    def test_testing_scripts_cannt_be_none(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED, interface=True)
        user = factory.make_admin()
        form = TestForm(
            instance=node, user=user, data={"testing_scripts": "none"}
        )
        self.assertFalse(form.is_valid())

    def test_cannt_run_destructive_test_on_deployed_machine(self):
        script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING, destructive=True
        )
        node = factory.make_Machine(
            status=NODE_STATUS.DEPLOYED, interface=True
        )
        user = factory.make_admin()
        form = TestForm(
            instance=node, user=user, data={"testing_scripts": script.name}
        )
        self.assertFalse(form.is_valid())

    def test_cannt_run_destructive_test_on_non_machine(self):
        script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING, destructive=True
        )
        node = factory.make_Node(
            node_type=factory.pick_choice(
                NODE_TYPE_CHOICES, but_not=[NODE_TYPE.MACHINE]
            ),
            interface=True,
        )
        user = factory.make_admin()
        form = TestForm(
            instance=node, user=user, data={"testing_scripts": script.name}
        )
        self.assertFalse(form.is_valid())


class TestCommissionForm(MAASServerTestCase):
    def test_doesnt_require_anything(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY,
            power_state=POWER_STATE.OFF,
            interface=True,
        )
        user = factory.make_admin()
        form = CommissionForm(instance=node, user=user, data={})
        self.assertTrue(form.is_valid(), form.errors)

    def test_not_allowed_in_bad_state(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING,
            power_state=POWER_STATE.OFF,
            interface=True,
        )
        user = factory.make_admin()
        form = CommissionForm(instance=node, user=user, data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual(
            {
                "__all__": [
                    "Commission is not available because of the current state "
                    "of the node."
                ]
            },
            form.errors,
        )

    def test_calls_start_commissioning_if_already_on(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY,
            power_state=POWER_STATE.ON,
            interface=True,
        )
        user = factory.make_admin()
        mock_start_commissioning = self.patch_autospec(
            node, "start_commissioning"
        )
        form = CommissionForm(instance=node, user=user, data={})
        self.assertTrue(form.is_valid(), form.errors)
        node = form.save()
        mock_start_commissioning.assert_called_once_with(
            user,
            enable_ssh=False,
            skip_bmc_config=False,
            skip_networking=False,
            skip_storage=False,
            commissioning_scripts=[],
            testing_scripts=[],
            script_input={},
        )

    def test_calls_start_commissioning_with_options(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY,
            power_state=POWER_STATE.OFF,
            interface=True,
        )
        user = factory.make_admin()
        commissioning_scripts = [
            factory.make_Script(script_type=SCRIPT_TYPE.COMMISSIONING).name
            for _ in range(3)
        ]
        testing_scripts = [
            factory.make_Script(script_type=SCRIPT_TYPE.TESTING).name
            for _ in range(3)
        ]
        mock_start_commissioning = self.patch_autospec(
            node, "start_commissioning"
        )
        form = CommissionForm(
            instance=node,
            user=user,
            data={
                "enable_ssh": True,
                "skip_bmc_config": True,
                "skip_networking": True,
                "skip_storage": True,
                "commissioning_scripts": ",".join(commissioning_scripts),
                "testing_scripts": ",".join(testing_scripts),
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        node = form.save()
        self.assertIsNotNone(node)
        mock_start_commissioning.assert_called_once_with(
            user,
            enable_ssh=True,
            skip_bmc_config=True,
            skip_networking=True,
            skip_storage=True,
            commissioning_scripts=commissioning_scripts,
            testing_scripts=testing_scripts,
            script_input={},
        )

    def test_class_start_commissioning_with_storage_param(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY,
            with_boot_disk=False,
            interface=True,
        )
        commissioning_bd = factory.make_PhysicalBlockDevice(node=node)
        testing_bd = factory.make_PhysicalBlockDevice(node=node)
        user = factory.make_admin()
        commissioning_script = factory.make_Script(
            script_type=SCRIPT_TYPE.COMMISSIONING,
            parameters={"storage": {"type": "storage"}},
        )
        testing_script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING,
            parameters={"storage": {"type": "storage"}},
        )
        mock_start_commissioning = self.patch_autospec(
            node, "start_commissioning"
        )
        commissioning_input = random.choice(
            [
                str(commissioning_bd.id),
                commissioning_bd.name,
                commissioning_bd.model,
                commissioning_bd.serial,
                f"{commissioning_bd.model}:{commissioning_bd.serial}",
            ]
            + commissioning_bd.tags
        )
        testing_input = random.choice(
            [
                str(testing_bd.id),
                testing_bd.name,
                testing_bd.model,
                testing_bd.serial,
                f"{testing_bd.model}:{testing_bd.serial}",
            ]
            + testing_bd.tags
        )
        form = CommissionForm(
            instance=node,
            user=user,
            data={
                "commissioning_scripts": commissioning_script.name,
                "testing_scripts": testing_script.name,
                "%s_storage" % commissioning_script.name: commissioning_input,
                "%s_storage" % testing_script.name: testing_input,
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        node = form.save()
        self.assertIsNotNone(node)
        mock_start_commissioning.assert_called_once_with(
            user,
            False,
            False,
            False,
            False,
            [commissioning_script.name],
            [testing_script.name],
            {
                commissioning_script.name: {"storage": commissioning_input},
                testing_script.name: {"storage": testing_input},
            },
        )

    def test_class_start_commissioning_with_storage_param_errors(self):
        node = factory.make_Node(status=NODE_STATUS.READY, interface=True)
        user = factory.make_admin()
        commissioning_script = factory.make_Script(
            script_type=SCRIPT_TYPE.COMMISSIONING,
            parameters={"storage": {"type": "storage"}},
        )
        testing_script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING,
            parameters={"storage": {"type": "storage"}},
        )
        self.patch_autospec(node, "start_commissioning")
        form = CommissionForm(
            instance=node,
            user=user,
            data={
                "commissioning_scripts": commissioning_script.name,
                "testing_scripts": testing_script.name,
                "%s_storage"
                % commissioning_script.name: factory.make_name("bad"),
                "%s_storage" % testing_script.name: factory.make_name("bad"),
            },
        )
        self.assertFalse(form.is_valid())

    def test_class_start_commissioning_with_interface_param(self):
        node = factory.make_Node(status=NODE_STATUS.READY, interface=False)
        commissioning_interface = factory.make_Interface(node=node)
        testing_interface = factory.make_Interface(node=node)
        user = factory.make_admin()
        commissioning_script = factory.make_Script(
            script_type=SCRIPT_TYPE.COMMISSIONING,
            parameters={"interface": {"type": "interface"}},
        )
        testing_script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING,
            parameters={"interface": {"type": "interface"}},
        )
        mock_start_commissioning = self.patch_autospec(
            node, "start_commissioning"
        )
        commissioning_input = random.choice(
            [
                str(commissioning_interface.id),
                commissioning_interface.name,
                str(commissioning_interface.mac_address),
                commissioning_interface.vendor,
                commissioning_interface.product,
                "%s:%s"
                % (
                    commissioning_interface.vendor,
                    commissioning_interface.product,
                ),
            ]
            + commissioning_interface.tags
        )
        testing_input = random.choice(
            [
                str(testing_interface.id),
                testing_interface.name,
                str(testing_interface.mac_address),
                testing_interface.vendor,
                testing_interface.product,
                "%s:%s"
                % (testing_interface.vendor, testing_interface.product),
            ]
            + testing_interface.tags
        )
        form = CommissionForm(
            instance=node,
            user=user,
            data={
                "commissioning_scripts": commissioning_script.name,
                "testing_scripts": testing_script.name,
                "%s_interface"
                % commissioning_script.name: commissioning_input,
                "%s_interface" % testing_script.name: testing_input,
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        node = form.save()
        self.assertIsNotNone(node)
        mock_start_commissioning.assert_called_once_with(
            user,
            False,
            False,
            False,
            False,
            [commissioning_script.name],
            [testing_script.name],
            {
                commissioning_script.name: {"interface": commissioning_input},
                testing_script.name: {"interface": testing_input},
            },
        )

    def test_class_start_commissioning_with_interface_param_errors(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED, interface=True)
        user = factory.make_admin()
        commissioning_script = factory.make_Script(
            script_type=SCRIPT_TYPE.COMMISSIONING,
            parameters={"interface": {"type": "interface"}},
        )
        testing_script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING,
            parameters={"interface": {"type": "interface"}},
        )
        self.patch_autospec(node, "start_commissioning")
        form = CommissionForm(
            instance=node,
            user=user,
            data={
                "commissioning_scripts": commissioning_script.name,
                "testing_scripts": testing_script.name,
                "%s_interface"
                % commissioning_script.name: factory.make_name("bad"),
                "%s_interface" % testing_script.name: factory.make_name("bad"),
            },
        )
        self.assertFalse(form.is_valid())

    def test_class_start_commissioning_with_runtime_param(self):
        node = factory.make_Node(status=NODE_STATUS.READY, interface=True)
        user = factory.make_admin()
        commissioning_script = factory.make_Script(
            script_type=SCRIPT_TYPE.COMMISSIONING,
            parameters={"runtime": {"type": "runtime"}},
        )
        testing_script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING,
            parameters={"runtime": {"type": "runtime"}},
        )
        mock_start_commissioning = self.patch_autospec(
            node, "start_commissioning"
        )
        commissioning_input = random.choice(["168:00:00", "10080:00", 604800])
        testing_input = random.choice(["168:00:00", "10080:00", 604800])
        form = CommissionForm(
            instance=node,
            user=user,
            data={
                "commissioning_scripts": commissioning_script.name,
                "testing_scripts": testing_script.name,
                "%s_runtime" % commissioning_script.name: commissioning_input,
                "%s_runtime" % testing_script.name: testing_input,
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        node = form.save()
        self.assertIsNotNone(node)
        mock_start_commissioning.assert_called_once_with(
            user,
            False,
            False,
            False,
            False,
            [commissioning_script.name],
            [testing_script.name],
            {
                commissioning_script.name: {"runtime": 604800},
                testing_script.name: {"runtime": 604800},
            },
        )

    def test_class_start_commissioning_with_runtime_param_errors(self):
        node = factory.make_Node(status=NODE_STATUS.READY, interface=True)
        user = factory.make_admin()
        commissioning_script = factory.make_Script(
            script_type=SCRIPT_TYPE.COMMISSIONING,
            parameters={"runtime": {"type": "runtime"}},
        )
        testing_script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING,
            parameters={"runtime": {"type": "runtime"}},
        )
        self.patch_autospec(node, "start_commissioning")
        form = CommissionForm(
            instance=node,
            user=user,
            data={
                "commissioning_scripts": commissioning_script.name,
                "testing_scripts": testing_script.name,
                "%s_runtime"
                % commissioning_script.name: factory.make_name("bad"),
                "%s_runtime" % testing_script.name: factory.make_name("bad"),
            },
        )
        self.assertFalse(form.is_valid())

    def test_class_start_commissioning_with_url_param(self):
        node = factory.make_Node(status=NODE_STATUS.READY, interface=True)
        user = factory.make_admin()
        commissioning_script = factory.make_Script(
            script_type=SCRIPT_TYPE.COMMISSIONING,
            parameters={"url": {"type": "url"}},
        )
        testing_script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING,
            parameters={"url": {"type": "url"}},
        )
        mock_start_commissioning = self.patch_autospec(
            node, "start_commissioning"
        )
        commissioning_input = factory.make_url(scheme="http")
        testing_input = factory.make_url(scheme="http")
        form = CommissionForm(
            instance=node,
            user=user,
            data={
                "commissioning_scripts": commissioning_script.name,
                "testing_scripts": testing_script.name,
                "%s_url" % commissioning_script.name: commissioning_input,
                "%s_url" % testing_script.name: testing_input,
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        node = form.save()
        self.assertIsNotNone(node)
        mock_start_commissioning.assert_called_once_with(
            user,
            False,
            False,
            False,
            False,
            [commissioning_script.name],
            [testing_script.name],
            {
                commissioning_script.name: {"url": commissioning_input},
                testing_script.name: {"url": testing_input},
            },
        )

    def test_class_start_commissioning_can_override_global_param(self):
        node = factory.make_Node(status=NODE_STATUS.READY, interface=True)
        commissioning_bd = factory.make_PhysicalBlockDevice(node=node)
        testing_bd = factory.make_PhysicalBlockDevice(node=node)
        user = factory.make_admin()
        global_commissioning_script = factory.make_Script(
            script_type=SCRIPT_TYPE.COMMISSIONING,
            parameters={"storage": {"type": "storage"}},
        )
        commissioning_script = factory.make_Script(
            script_type=SCRIPT_TYPE.COMMISSIONING,
            parameters={"storage": {"type": "storage"}},
        )
        global_testing_script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING,
            parameters={"storage": {"type": "storage"}},
        )
        testing_script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING,
            parameters={"storage": {"type": "storage"}},
        )
        mock_start_commissioning = self.patch_autospec(
            node, "start_commissioning"
        )
        commissioning_input = random.choice(
            [
                str(commissioning_bd.id),
                commissioning_bd.name,
                commissioning_bd.model,
                commissioning_bd.serial,
                f"{commissioning_bd.model}:{commissioning_bd.serial}",
            ]
            + commissioning_bd.tags
        )
        testing_input = random.choice(
            [
                str(testing_bd.id),
                testing_bd.name,
                testing_bd.model,
                testing_bd.serial,
                f"{testing_bd.model}:{testing_bd.serial}",
            ]
            + testing_bd.tags
        )
        form = CommissionForm(
            instance=node,
            user=user,
            data={
                "commissioning_scripts": "%s,%s"
                % (
                    global_commissioning_script.name,
                    commissioning_script.name,
                ),
                "testing_scripts": "%s,%s"
                % (global_testing_script.name, testing_script.name),
                "storage": "all",
                "%s_storage" % commissioning_script.name: commissioning_input,
                "%s_storage" % testing_script.name: testing_input,
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        node = form.save()
        self.assertIsNotNone(node)
        mock_start_commissioning.assert_called_once_with(
            user,
            False,
            False,
            False,
            False,
            [global_commissioning_script.name, commissioning_script.name],
            [global_testing_script.name, testing_script.name],
            {
                global_commissioning_script.name: {"storage": "all"},
                commissioning_script.name: {"storage": commissioning_input},
                global_testing_script.name: {"storage": "all"},
                testing_script.name: {"storage": testing_input},
            },
        )

    def test_validates_commissioning_scripts(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY,
            power_state=POWER_STATE.OFF,
            interface=True,
        )
        user = factory.make_admin()
        form = CommissionForm(
            instance=node,
            user=user,
            data={"commissioning_scripts": factory.make_name("script")},
        )
        self.assertFalse(form.is_valid())

    def test_validates_testing_scripts(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, power_state=POWER_STATE.OFF
        )
        user = factory.make_admin()
        form = CommissionForm(
            instance=node,
            user=user,
            data={"testing_scripts": factory.make_name("script")},
        )
        self.assertFalse(form.is_valid())

    def test_allows_setting_testing_scripts_to_none(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY,
            power_state=POWER_STATE.OFF,
            interface=True,
        )
        mock_start_commissioning = self.patch_autospec(
            node, "start_commissioning"
        )
        user = factory.make_admin()
        form = CommissionForm(
            instance=node, user=user, data={"testing_scripts": "none"}
        )
        self.assertTrue(form.is_valid(), form.errors)
        node = form.save()
        self.assertIsNotNone(node)
        mock_start_commissioning.assert_called_once_with(
            user,
            enable_ssh=False,
            skip_bmc_config=False,
            skip_networking=False,
            skip_storage=False,
            commissioning_scripts=[],
            testing_scripts=["none"],
            script_input={},
        )
