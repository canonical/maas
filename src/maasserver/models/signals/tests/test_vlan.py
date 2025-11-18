# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the behaviour of VLAN signals."""

from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_WORKFLOW_NAME,
    ConfigureDHCPParam,
)
import maasserver.models.signals.vlan as vlan_signals_module
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import post_commit_hooks


class TestPostSaveVLANSignal(MAASServerTestCase):
    def test_save_vlan_triggers_dhcp_workflow_if_dhcp_on(self):
        start_workflow_mock = self.patch(vlan_signals_module, "start_workflow")
        with post_commit_hooks:
            rack_controller = factory.make_RackController()
            vlan = factory.make_VLAN(
                dhcp_on=True, primary_rack=rack_controller
            )
        start_workflow_mock.assert_called_once_with(
            workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
            param=ConfigureDHCPParam(system_ids=[], vlan_ids=[vlan.id]),
            task_queue="region",
        )

    def test_save_vlan_triggers_dhcp_workflow_if_dhcp_relay(self):
        start_workflow_mock = self.patch(vlan_signals_module, "start_workflow")
        with post_commit_hooks:
            rack_controller = factory.make_RackController()
            relay_vlan = factory.make_VLAN(
                dhcp_on=True, primary_rack=rack_controller
            )
            start_workflow_mock.reset_mock()
            vlan = factory.make_VLAN(relay_vlan=relay_vlan)
        start_workflow_mock.assert_called_once_with(
            workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
            param=ConfigureDHCPParam(system_ids=[], vlan_ids=[vlan.id]),
            task_queue="region",
        )

    def test_save_vlan_does_not_trigger_dhcp_workflow_if_dhcp_off(self):
        start_workflow_mock = self.patch(vlan_signals_module, "start_workflow")
        factory.make_VLAN(dhcp_on=False)
        start_workflow_mock.assert_not_called()


class TestPostDeleteVLANSignal(MAASServerTestCase):
    def test_delete_vlan_triggers_dhcp_workflow_if_dhcp_on(self):
        start_workflow_mock = self.patch(vlan_signals_module, "start_workflow")
        with post_commit_hooks:
            primary_rack_controller = factory.make_RackController()
            secondary_rack_controller = factory.make_RackController()
            vlan = factory.make_VLAN(
                dhcp_on=True,
                primary_rack=primary_rack_controller,
                secondary_rack=secondary_rack_controller,
            )
            start_workflow_mock.reset_mock()
            vlan.delete()
        start_workflow_mock.assert_called_once_with(
            workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
            param=ConfigureDHCPParam(
                vlan_ids=[],
                system_ids=[
                    primary_rack_controller.system_id,
                    secondary_rack_controller.system_id,
                ],
            ),
            task_queue="region",
        )

    def test_delete_vlan_triggers_dhcp_workflow_if_relay_on(self):
        start_workflow_mock = self.patch(vlan_signals_module, "start_workflow")
        with post_commit_hooks:
            rack_controller = factory.make_RackController()
            relay_vlan = factory.make_VLAN(
                dhcp_on=True, primary_rack=rack_controller
            )
            vlan = factory.make_VLAN(dhcp_on=False, relay_vlan=relay_vlan)
            start_workflow_mock.reset_mock()
            vlan.delete()
        start_workflow_mock.assert_called_once_with(
            workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
            param=ConfigureDHCPParam(system_ids=[], vlan_ids=[relay_vlan.id]),
            task_queue="region",
        )


class TestUpdateVLANSignal(MAASServerTestCase):
    def test_update_vlan_dhcp_on_triggers_workflow(self):
        start_workflow_mock = self.patch(vlan_signals_module, "start_workflow")
        with post_commit_hooks:
            vlan = factory.make_VLAN(dhcp_on=False)
            start_workflow_mock.reset_mock()
            vlan.dhcp_on = True
            vlan.save()
        start_workflow_mock.assert_called_once_with(
            workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
            param=ConfigureDHCPParam(system_ids=[], vlan_ids=[vlan.id]),
            task_queue="region",
        )

    def test_update_vlan_dhcp_off_triggers_workflow(self):
        start_workflow_mock = self.patch(vlan_signals_module, "start_workflow")
        with post_commit_hooks:
            vlan = factory.make_VLAN(dhcp_on=True)
            start_workflow_mock.reset_mock()
            vlan.dhcp_on = False
            vlan.save()
        start_workflow_mock.assert_called_once_with(
            workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
            param=ConfigureDHCPParam(system_ids=[], vlan_ids=[vlan.id]),
            task_queue="region",
        )

    def test_update_vlan_mtu_triggers_workflow(self):
        start_workflow_mock = self.patch(vlan_signals_module, "start_workflow")
        with post_commit_hooks:
            vlan = factory.make_VLAN(dhcp_on=True, mtu=1500)
            start_workflow_mock.reset_mock()
            vlan.mtu = 9000
            vlan.save()
        start_workflow_mock.assert_called_once_with(
            workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
            param=ConfigureDHCPParam(system_ids=[], vlan_ids=[vlan.id]),
            task_queue="region",
        )

    def test_update_vlan_relay_vlan_triggers_workflow(self):
        start_workflow_mock = self.patch(vlan_signals_module, "start_workflow")
        rack_controller = factory.make_RackController()
        with post_commit_hooks:
            relay_vlan1 = factory.make_VLAN(
                dhcp_on=True, primary_rack=rack_controller
            )
            relay_vlan2 = factory.make_VLAN(
                dhcp_on=True, primary_rack=rack_controller
            )
            vlan = factory.make_VLAN(relay_vlan=relay_vlan1)
            start_workflow_mock.reset_mock()
            vlan.relay_vlan = relay_vlan2
            vlan.save()

        start_workflow_mock.assert_called_once_with(
            workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
            param=ConfigureDHCPParam(
                system_ids=[], vlan_ids=[relay_vlan1.id, vlan.id]
            ),
            task_queue="region",
        )

    def test_update_vlan_racks(self):
        start_workflow_mock = self.patch(vlan_signals_module, "start_workflow")
        primary_rack_controller = factory.make_RackController()
        secondary_rack_controller = factory.make_RackController()

        new_primary_rack_controller = factory.make_RackController()
        new_secondary_rack_controller = factory.make_RackController()

        with post_commit_hooks:
            vlan = factory.make_VLAN(
                dhcp_on=True,
                primary_rack=primary_rack_controller,
                secondary_rack=secondary_rack_controller,
            )
            start_workflow_mock.reset_mock()
            vlan.primary_rack = new_primary_rack_controller
            vlan.secondary_rack = new_secondary_rack_controller
            vlan.save()

        start_workflow_mock.assert_called_once_with(
            workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
            param=ConfigureDHCPParam(
                system_ids=[
                    primary_rack_controller.system_id,
                    secondary_rack_controller.system_id,
                    new_primary_rack_controller.system_id,
                    new_secondary_rack_controller.system_id,
                ],
                vlan_ids=[vlan.id],
            ),
            task_queue="region",
        )

    def test_update_vlan_mtu_when_dhcp_off_does_not_trigger_workflow(self):
        start_workflow_mock = self.patch(vlan_signals_module, "start_workflow")

        with post_commit_hooks:
            vlan = factory.make_VLAN(dhcp_on=False, mtu=1500)
            vlan.mtu = 9000
            vlan.save()

        start_workflow_mock.assert_not_called()
