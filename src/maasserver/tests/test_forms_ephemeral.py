# Copyright 2015-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for commission form."""

__all__ = []


from maasserver.enum import (
    NODE_STATUS,
    NODE_TYPE,
    NODE_TYPE_CHOICES,
    POWER_STATE,
)
from maasserver.forms_ephemeral import (
    CommissionForm,
    TestForm,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import MockCalledOnceWith
from metadataserver.enum import SCRIPT_TYPE


class TestTestForm(MAASServerTestCase):

    def test__doesnt_require_anything(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED)
        user = factory.make_admin()
        form = TestForm(instance=node, user=user, data={})
        self.assertTrue(form.is_valid(), form.errors)

    def test__not_allowed_in_bad_state(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYING)
        user = factory.make_admin()
        form = TestForm(instance=node, user=user, data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual({
            '__all__': [
                "Test is not available because of the current state "
                "of the node."],
            }, form.errors)

    def test__calls_start_testing_if_already_on(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYED, power_state=POWER_STATE.ON)
        user = factory.make_admin()
        mock_start_testing = self.patch_autospec(node, "start_testing")
        form = TestForm(instance=node, user=user, data={})
        self.assertTrue(form.is_valid(), form.errors)
        node = form.save()
        self.assertThat(
            mock_start_testing,
            MockCalledOnceWith(user, enable_ssh=False, testing_scripts=[]))

    def test__calls_start_testing_with_options(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED)
        user = factory.make_admin()
        enable_ssh = factory.pick_bool()
        testing_scripts = [
            factory.make_Script(script_type=SCRIPT_TYPE.TESTING).name
            for _ in range(3)
        ]
        mock_start_testing = self.patch_autospec(node, "start_testing")
        form = TestForm(instance=node, user=user, data={
            "enable_ssh": enable_ssh,
            'testing_scripts': ','.join(testing_scripts),
            })
        self.assertTrue(form.is_valid(), form.errors)
        node = form.save()
        self.assertIsNotNone(node)
        self.assertThat(
            mock_start_testing,
            MockCalledOnceWith(
                user, enable_ssh=enable_ssh, testing_scripts=testing_scripts))

    def test__validates_testing_scripts(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED)
        user = factory.make_admin()
        form = TestForm(instance=node, user=user, data={
            'testing_scripts': factory.make_name('script'),
            })
        self.assertFalse(form.is_valid())

    def test__testing_scripts_cannt_be_none(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED)
        user = factory.make_admin()
        form = TestForm(instance=node, user=user, data={
            'testing_scripts': 'none',
            })
        self.assertFalse(form.is_valid())

    def test__cannt_run_destructive_test_on_deployed_machine(self):
        script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING, destructive=True)
        node = factory.make_Machine(status=NODE_STATUS.DEPLOYED)
        user = factory.make_admin()
        form = TestForm(instance=node, user=user, data={
            'testing_scripts': script.name,
            })
        self.assertFalse(form.is_valid())

    def test__cannt_run_destructive_test_on_non_machine(self):
        script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING, destructive=True)
        node = factory.make_Node(
            node_type=factory.pick_choice(
                NODE_TYPE_CHOICES, but_not=[NODE_TYPE.MACHINE]))
        user = factory.make_admin()
        form = TestForm(instance=node, user=user, data={
            'testing_scripts': script.name,
            })
        self.assertFalse(form.is_valid())


class TestCommissionForm(MAASServerTestCase):

    def test__doesnt_require_anything(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, power_state=POWER_STATE.OFF)
        user = factory.make_admin()
        form = CommissionForm(instance=node, user=user, data={})
        self.assertTrue(form.is_valid(), form.errors)

    def test__not_allowed_in_bad_state(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING, power_state=POWER_STATE.OFF)
        user = factory.make_admin()
        form = CommissionForm(instance=node, user=user, data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual({
            '__all__': [
                "Commission is not available because of the current state "
                "of the node."],
            }, form.errors)

    def test__calls_start_commissioning_if_already_on(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, power_state=POWER_STATE.ON)
        user = factory.make_admin()
        mock_start_commissioning = self.patch_autospec(
            node, "start_commissioning")
        form = CommissionForm(instance=node, user=user, data={})
        self.assertTrue(form.is_valid(), form.errors)
        node = form.save()
        self.assertThat(
            mock_start_commissioning,
            MockCalledOnceWith(
                user, enable_ssh=False, skip_networking=False,
                skip_storage=False, commissioning_scripts=[],
                testing_scripts=[]))

    def test__calls_start_commissioning_with_options(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, power_state=POWER_STATE.OFF)
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
            node, 'start_commissioning')
        form = CommissionForm(instance=node, user=user, data={
            'enable_ssh': True,
            'skip_networking': True,
            'skip_storage': True,
            'commissioning_scripts': ','.join(commissioning_scripts),
            'testing_scripts': ','.join(testing_scripts),
            })
        self.assertTrue(form.is_valid(), form.errors)
        node = form.save()
        self.assertIsNotNone(node)
        self.assertThat(
            mock_start_commissioning,
            MockCalledOnceWith(
                user, enable_ssh=True, skip_networking=True, skip_storage=True,
                commissioning_scripts=commissioning_scripts,
                testing_scripts=testing_scripts))

    def test__validates_commissioning_scripts(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, power_state=POWER_STATE.OFF)
        user = factory.make_admin()
        form = CommissionForm(instance=node, user=user, data={
            'commissioning_scripts': factory.make_name('script'),
            })
        self.assertFalse(form.is_valid())

    def test__validates_testing_scripts(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, power_state=POWER_STATE.OFF)
        user = factory.make_admin()
        form = CommissionForm(instance=node, user=user, data={
            'testing_scripts': factory.make_name('script'),
            })
        self.assertFalse(form.is_valid())

    def test__allows_setting_testing_scripts_to_none(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, power_state=POWER_STATE.OFF)
        mock_start_commissioning = self.patch_autospec(
            node, 'start_commissioning')
        user = factory.make_admin()
        form = CommissionForm(instance=node, user=user, data={
            'testing_scripts': 'none',
            })
        self.assertTrue(form.is_valid(), form.errors)
        node = form.save()
        self.assertIsNotNone(node)
        self.assertThat(
            mock_start_commissioning,
            MockCalledOnceWith(
                user, enable_ssh=False, skip_networking=False,
                skip_storage=False, commissioning_scripts=[],
                testing_scripts=['none']))
