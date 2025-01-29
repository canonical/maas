# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import random

from django.core.exceptions import ValidationError
from django.db.models import ProtectedError

from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_WORKFLOW_NAME,
    ConfigureDHCPParam,
)
from maasserver.enum import INTERFACE_TYPE
from maasserver.models import vlan as vlan_module
from maasserver.models.interface import PhysicalInterface, VLANInterface
from maasserver.models.notification import Notification
from maasserver.models.vlan import VLAN
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import post_commit_hooks, reload_object


class TestVLANManager(MAASServerTestCase):
    def test_default_specifier_matches_vid(self):
        # Note: this is for backward compatibility with the previous iteration
        # of constraints, which used vlan:<number> to mean VID, not represent
        # a database ID.
        with post_commit_hooks:
            factory.make_VLAN()
            vlan = factory.make_VLAN()
            factory.make_VLAN()
        vid = vlan.vid
        self.assertCountEqual(
            VLAN.objects.filter_by_specifiers("%s" % vid), [vlan]
        )

    def test_default_specifier_matches_name(self):
        with post_commit_hooks:
            factory.make_VLAN()
            vlan = factory.make_VLAN(name="infinite-improbability")
            factory.make_VLAN()
        self.assertCountEqual(
            VLAN.objects.filter_by_specifiers("infinite-improbability"), [vlan]
        )

    def test_name_specifier_matches_name(self):
        with post_commit_hooks:
            factory.make_VLAN()
            vlan = factory.make_VLAN(name="infinite-improbability")
            factory.make_VLAN()
        self.assertCountEqual(
            VLAN.objects.filter_by_specifiers("name:infinite-improbability"),
            [vlan],
        )

    def test_vid_specifier_matches_vid(self):
        with post_commit_hooks:
            factory.make_VLAN()
            vlan = factory.make_VLAN()
            vid = vlan.vid
            factory.make_VLAN()
        self.assertCountEqual(
            VLAN.objects.filter_by_specifiers("vid:%d" % vid), [vlan]
        )

    def test_space_specifier_matches_space_by_name(self):
        with post_commit_hooks:
            factory.make_VLAN()
            space = factory.make_Space()
            vlan = factory.make_VLAN(space=space)
            factory.make_VLAN()
        self.assertCountEqual(
            VLAN.objects.filter_by_specifiers("space:%s" % space.name), [vlan]
        )

    def test_space_specifier_matches_space_by_id(self):
        with post_commit_hooks:
            factory.make_VLAN()
            space = factory.make_Space()
            vlan = factory.make_VLAN(space=space)
            factory.make_VLAN()
        self.assertCountEqual(
            VLAN.objects.filter_by_specifiers("space:%s" % space.id), [vlan]
        )

    def test_class_specifier_matches_attached_subnet(self):
        with post_commit_hooks:
            factory.make_VLAN()
            vlan = factory.make_VLAN()
            subnet = factory.make_Subnet(vlan=vlan)
            factory.make_VLAN()
        self.assertCountEqual(
            VLAN.objects.filter_by_specifiers("subnet:%s" % subnet.id), [vlan]
        )

    def test_class_specifier_matches_attached_fabric(self):
        with post_commit_hooks:
            factory.make_Fabric()
            fabric = factory.make_Fabric(name="rack42")
            factory.make_VLAN()
            vlan = factory.make_VLAN(fabric=fabric)
            factory.make_VLAN()
        self.assertCountEqual(
            VLAN.objects.filter_by_specifiers(
                "fabric:%s,vid:%d" % (fabric.name, vlan.vid)
            ),
            [vlan],
        )

    def test_create_calls_configure_dhcp_workflow_if_dhcp_on(self):
        with post_commit_hooks:
            fabric = factory.make_Fabric()
            start_workflow = self.patch(
                vlan_module, "start_workflow"
            )  # patching here to ignore default VLAN created with fabric
            VLAN.objects.create(dhcp_on=False, vid=1, fabric_id=fabric.id)
            start_workflow.assert_not_called()
            vlan = VLAN.objects.create(
                dhcp_on=True, vid=2, fabric_id=fabric.id
            )
        start_workflow.assert_called_once_with(
            workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
            param=ConfigureDHCPParam(vlan_ids=[vlan.id]),
            task_queue="region",
        )


class TestVLAN(MAASServerTestCase):
    def test_delete_relay_vlan_doesnt_delete_vlan(self):
        with post_commit_hooks:
            relay_vlan = factory.make_VLAN()
            vlan = factory.make_VLAN(relay_vlan=relay_vlan)
            relay_vlan.delete()
        vlan = reload_object(vlan)
        self.assertIsNotNone(vlan)
        self.assertIsNone(vlan.relay_vlan)

    def test_delete_primary_rack_fails(self):
        rack = factory.make_RackController()
        with post_commit_hooks:
            vlan = factory.make_VLAN(primary_rack=rack)
        self.assertRaises(ProtectedError, rack.delete)
        vlan = reload_object(vlan)
        self.assertIsNotNone(vlan)
        self.assertEqual(vlan.primary_rack, rack)

    def test_get_name_for_default_vlan_is_untagged(self):
        fabric = factory.make_Fabric()
        self.assertEqual("untagged", fabric.get_default_vlan().get_name())

    def test_get_name_for_set_name(self):
        name = factory.make_name("name")
        vlan = factory.make_VLAN(name=name)
        self.assertEqual(name, vlan.get_name())

    def test_get_name_for_unnamed_vlan(self):
        vlan = factory.make_VLAN()
        self.assertEqual(None, vlan.get_name())

    def test_creates_vlan(self):
        name = factory.make_name("name")
        vid = random.randint(3, 55)
        fabric = factory.make_Fabric()
        vlan = VLAN(vid=vid, name=name, fabric=fabric)

        with post_commit_hooks:
            vlan.save()

        self.assertEqual(vlan.vid, vid)
        self.assertEqual(vlan.name, name)

    def test_is_fabric_default_detects_default_vlan(self):
        fabric = factory.make_Fabric()
        factory.make_VLAN(fabric=fabric)
        vlan = fabric.vlan_set.all().order_by("id").first()
        self.assertTrue(vlan.is_fabric_default())

    def test_is_fabric_default_detects_non_default_vlan(self):
        vlan = factory.make_VLAN()
        self.assertFalse(vlan.is_fabric_default())

    def test_cant_delete_default_vlan(self):
        name = factory.make_name("name")
        fabric = factory.make_Fabric(name=name)
        with self.assertRaisesRegex(
            ValidationError, "This VLAN is the default VLAN in the fabric"
        ):
            fabric.get_default_vlan().delete()

    def test_manager_get_default_vlan_returns_dflt_vlan_of_dflt_fabric(self):
        factory.make_Fabric()
        vlan = VLAN.objects.get_default_vlan()
        self.assertTrue(vlan.is_fabric_default())
        self.assertTrue(vlan.fabric.is_default())

    def test_vlan_interfaces_are_deleted_when_related_vlan_is_deleted(self):
        node = factory.make_Node()
        parent = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        vlan = factory.make_VLAN()
        interface = factory.make_Interface(
            INTERFACE_TYPE.VLAN, vlan=vlan, parents=[parent]
        )
        vlan.delete()
        self.assertCountEqual(
            [], VLANInterface.objects.filter(id=interface.id)
        )

    def test_interfaces_are_reconnected_when_vlan_is_deleted(self):
        node = factory.make_Node()
        vlan = factory.make_VLAN()
        fabric = vlan.fabric
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=vlan
        )
        vlan.delete()
        reconnected_interfaces = PhysicalInterface.objects.filter(
            id=interface.id
        )
        self.assertCountEqual([interface], reconnected_interfaces)
        reconnected_interface = reconnected_interfaces[0]
        self.assertEqual(reconnected_interface.vlan, fabric.get_default_vlan())

    def test_raises_integrity_error_if_reconnecting_fails(self):
        # Here we test a corner case: we test that the DB refuses to
        # leave an interface without a VLAN in case the reconnection
        # fails when a VLAN is deleted.
        vlan = factory.make_VLAN()
        # Break 'manage_connected_interfaces'.
        self.patch(vlan, "manage_connected_interfaces")
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL, vlan=vlan)
        with self.assertRaisesRegex(ProtectedError, "Interface.vlan"):
            vlan.delete()

    def test_subnets_are_reconnected_when_vlan_is_deleted(self):
        with post_commit_hooks:
            fabric = factory.make_Fabric()
            vlan = factory.make_VLAN(fabric=fabric)
            print(vlan.dhcp_on)
            subnet = factory.make_Subnet(vlan=vlan)
            vlan.delete()
        self.assertEqual(reload_object(subnet).vlan, fabric.get_default_vlan())

    def tests_creates_notification_when_no_dhcp(self):
        Notification.objects.filter(ident="dhcp_disabled_all_vlans").delete()
        factory.make_VLAN(dhcp_on=False)
        self.assertTrue(
            Notification.objects.filter(
                ident="dhcp_disabled_all_vlans"
            ).exists()
        )

    def tests_deletes_notification_once_there_is_dhcp(self):
        Notification.objects.filter(ident="dhcp_disabled_all_vlans").delete()
        with post_commit_hooks:
            # Force the notification to exist
            vlan = factory.make_VLAN(dhcp_on=False)
            # Now clear it.
            vlan.dhcp_on = True
            vlan.save()
        self.assertFalse(
            Notification.objects.filter(
                ident="dhcp_disabled_all_vlans"
            ).exists()
        )

    def test_connected_rack_controllers(self):
        with post_commit_hooks:
            vlan = factory.make_VLAN()
            racks = [factory.make_RackController(vlan=vlan) for _ in range(3)]
        self.assertCountEqual(racks, vlan.connected_rack_controllers())

    def test_update_calls_configure_dhcp_workflow(self):
        start_workflow = self.patch(vlan_module, "start_workflow")
        vlan = factory.make_VLAN(dhcp_on=False)
        vlan.dhcp_on = True
        vlan.mtu = 1800
        with post_commit_hooks:
            vlan.save()
        start_workflow.assert_called_once_with(
            workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
            param=ConfigureDHCPParam(vlan_ids=[vlan.id]),
            task_queue="region",
        )

    def test_delete_calls_configure_dhcp_workflow(self):
        start_workflow = self.patch(vlan_module, "start_workflow")
        primary_rack = factory.make_RackController()
        secondary_rack = factory.make_RackController()
        with post_commit_hooks:
            vlan = factory.make_VLAN(
                dhcp_on=True,
                primary_rack=primary_rack,
                secondary_rack=secondary_rack,
            )
            vlan.delete()

        start_workflow.assert_called_with(
            workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
            param=ConfigureDHCPParam(
                system_ids=[primary_rack.system_id, secondary_rack.system_id]
            ),
            task_queue="region",
        )


class TestVLANVidValidation(MAASServerTestCase):
    scenarios = [
        ("0", {"vid": 0, "valid": True}),
        ("12", {"vid": 12, "valid": True}),
        ("250", {"vid": 250, "valid": True}),
        ("3000", {"vid": 3000, "valid": True}),
        ("4095", {"vid": 4095, "valid": False}),
        ("4094", {"vid": 4094, "valid": True}),
        ("-23", {"vid": -23, "valid": False}),
        ("4096", {"vid": 4096, "valid": False}),
        ("10000", {"vid": 10000, "valid": False}),
    ]

    def test_validates_vid(self):
        fabric = factory.make_Fabric()
        # Update the VID of the default VLAN so that it doesn't clash with
        # the VIDs we're testing here.
        default_vlan = fabric.get_default_vlan()
        default_vlan.vid = 999

        with post_commit_hooks:
            default_vlan.save()

            name = factory.make_name("name")
            vlan = VLAN(vid=self.vid, name=name, fabric=fabric)
            if self.valid:
                # No exception.
                self.assertIsNone(vlan.save())

            else:
                self.assertRaises(ValidationError, vlan.save)


class TestVLANMTUValidation(MAASServerTestCase):
    scenarios = [
        ("551", {"mtu": 551, "valid": False}),
        ("552", {"mtu": 552, "valid": True}),
        ("65535", {"mtu": 65535, "valid": True}),
        ("65536", {"mtu": 65536, "valid": False}),
    ]

    def test_validates_mtu(self):
        vlan = factory.make_VLAN()
        vlan.mtu = self.mtu

        with post_commit_hooks:
            if self.valid:
                # No exception.
                self.assertIsNone(vlan.save())
            else:
                self.assertRaises(ValidationError, vlan.save)
