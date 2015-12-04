# Copyright 2015 Canonical Ltd.  This software is licensed under the
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

    def test__not_allowed_if_on(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, power_state=POWER_STATE.ON)
        user = factory.make_admin()
        form = CommissionForm(instance=node, user=user, data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual({
            '__all__': [
                "Commission is not available because of the node is currently "
                "powered on."],
            }, form.errors)

    def test__calls_start_commissioning_with_options(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY, power_state=POWER_STATE.OFF)
        user = factory.make_admin()
        mock_start_commissioning = self.patch_autospec(
            node, "start_commissioning")
        form = CommissionForm(instance=node, user=user, data={
            "enable_ssh": True,
            "skip_networking": True,
            "skip_storage": True,
            })
        self.assertTrue(form.is_valid(), form.errors)
        node = form.save()
        self.assertIsNotNone(node)
        self.assertThat(
            mock_start_commissioning,
            MockCalledOnceWith(
                user, enable_ssh=True, skip_networking=True,
                skip_storage=True))
