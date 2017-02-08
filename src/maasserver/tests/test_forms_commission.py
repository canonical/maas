# Copyright 2015-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for commission form."""

__all__ = []

from maasserver.enum import (
    NODE_STATUS,
    POWER_STATE,
)
from maasserver.forms_commission import CommissionForm
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import MockCalledOnceWith
from metadataserver.enum import SCRIPT_TYPE


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
