# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `Switch` API."""

import http.client
import json

from django.conf import settings
from django.urls import reverse

from maascommon.enums.interface import InterfaceType
from maasserver.auth.tests.test_auth import OpenFGAMockMixin
from maasserver.enum import BOOT_RESOURCE_TYPE
from maasserver.sqlalchemy import service_layer
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasservicelayer.builders.switches import SwitchBuilder


def _parse(response):
    return json.loads(response.content.decode(settings.DEFAULT_CHARSET))


class TestSwitchesAPI(APITestCase.ForUser):
    """Tests for the Switches collection endpoint."""

    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/switches/", reverse("switches_handler")
        )

    def test_list_returns_empty_by_default(self):
        response = self.client.get(reverse("switches_handler"))
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed = _parse(response)
        self.assertEqual(0, len(parsed))

    def test_list_returns_switches(self):
        # Create switches using service layer
        switch1 = service_layer.services.switches.create(SwitchBuilder())
        switch2 = service_layer.services.switches.create(SwitchBuilder())

        response = self.client.get(reverse("switches_handler"))
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed = _parse(response)
        self.assertEqual(2, len(parsed))
        self.assertIn(switch1.id, [s["id"] for s in parsed])
        self.assertIn(switch2.id, [s["id"] for s in parsed])

    def test_create_requires_admin(self):
        response = self.client.post(
            reverse("switches_handler"),
            {"mac_address": factory.make_mac_address()},
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_create_requires_mac_address(self):
        self.become_admin()
        response = self.client.post(reverse("switches_handler"), {})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        parsed = _parse(response)
        self.assertIn("mac_address", parsed)

    def test_create_without_existing_interface(self):
        self.become_admin()
        mac = factory.make_mac_address()

        response = self.client.post(
            reverse("switches_handler"), {"mac_address": mac}
        )

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed = _parse(response)
        self.assertIn("id", parsed)
        self.assertIn("resource_uri", parsed)
        self.assertIsNone(parsed["target_image_id"])

    def test_create_with_unknown_interface(self):
        self.become_admin()
        mac = factory.make_mac_address()

        # Create an UNKNOWN interface that can be claimed
        vlan = factory.make_VLAN()
        service_layer.services.interfaces.create_unkwnown_interface(
            mac, vlan.id
        )

        response = self.client.post(
            reverse("switches_handler"), {"mac_address": mac}
        )

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed = _parse(response)
        self.assertIn("id", parsed)

    def test_create_with_assigned_interface_returns_400(self):
        self.become_admin()
        # Create an interface assigned to a node
        interface = factory.make_Interface(iftype=InterfaceType.PHYSICAL)

        response = self.client.post(
            reverse("switches_handler"),
            {"mac_address": str(interface.mac_address)},
        )

        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        parsed = _parse(response)
        self.assertIn("mac_address", parsed)

    def test_create_with_image(self):
        self.become_admin()
        mac = factory.make_mac_address()
        # Create a boot resource
        boot_resource = factory.make_BootResource(
            name="onie/sonic-4.0",
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
            architecture="amd64/generic",
        )

        response = self.client.post(
            reverse("switches_handler"),
            {"mac_address": mac, "image": "sonic-4.0"},
        )

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed = _parse(response)
        self.assertEqual(boot_resource.id, parsed["target_image_id"])

    def test_create_with_full_image_name(self):
        self.become_admin()
        mac = factory.make_mac_address()
        boot_resource = factory.make_BootResource(
            name="onie/mellanox-3.8.0",
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
            architecture="amd64/generic",
        )

        response = self.client.post(
            reverse("switches_handler"),
            {"mac_address": mac, "image": "onie/mellanox-3.8.0"},
        )

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed = _parse(response)
        self.assertEqual(boot_resource.id, parsed["target_image_id"])

    def test_create_with_invalid_image_returns_400(self):
        self.become_admin()
        mac = factory.make_mac_address()

        response = self.client.post(
            reverse("switches_handler"),
            {"mac_address": mac, "image": "nonexistent"},
        )

        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        parsed = _parse(response)
        self.assertIn("image", parsed)


class TestSwitchAPI(APITestCase.ForUser):
    """Tests for the Switch single-resource endpoint."""

    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/switches/1/",
            reverse("switch_handler", args=[1]),
        )

    def test_read(self):
        # Create a switch with an image
        boot_resource = factory.make_BootResource(
            name="onie/sonic-4.0",
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
            architecture="amd64/generic",
        )
        switch = service_layer.services.switches.create(
            SwitchBuilder(target_image_id=boot_resource.id)
        )

        response = self.client.get(reverse("switch_handler", args=[switch.id]))

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed = _parse(response)
        self.assertEqual(switch.id, parsed["id"])
        self.assertEqual(boot_resource.id, parsed["target_image_id"])
        self.assertEqual("onie/sonic-4.0", parsed["target_image"])

    def test_read_404(self):
        response = self.client.get(reverse("switch_handler", args=[999]))
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_update_requires_admin(self):
        switch = service_layer.services.switches.create(SwitchBuilder())
        response = self.client.put(
            reverse("switch_handler", args=[switch.id]), {"image": "sonic-4.0"}
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_update(self):
        self.become_admin()
        # Create a switch without an image
        switch = service_layer.services.switches.create(SwitchBuilder())

        # Create a boot resource
        boot_resource = factory.make_BootResource(
            name="onie/mellanox-3.8.0",
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
            architecture="amd64/generic",
        )

        response = self.client.put(
            reverse("switch_handler", args=[switch.id]),
            {"image": "mellanox-3.8.0"},
        )

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed = _parse(response)
        self.assertEqual(boot_resource.id, parsed["target_image_id"])
        self.assertEqual("onie/mellanox-3.8.0", parsed["target_image"])

    def test_update_404(self):
        self.become_admin()
        response = self.client.put(
            reverse("switch_handler", args=[999]), {"image": "sonic-4.0"}
        )
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_delete_requires_admin(self):
        switch = service_layer.services.switches.create(SwitchBuilder())
        response = self.client.delete(
            reverse("switch_handler", args=[switch.id])
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_delete(self):
        self.become_admin()
        switch = service_layer.services.switches.create(SwitchBuilder())

        response = self.client.delete(
            reverse("switch_handler", args=[switch.id])
        )

        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )
        # Verify it's actually deleted
        deleted_switch = (
            service_layer.services.switches.get_one_with_target_image(
                switch.id
            )
        )
        self.assertIsNone(deleted_switch)

    def test_delete_404(self):
        self.become_admin()
        response = self.client.delete(reverse("switch_handler", args=[999]))
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )


class TestSwitchesOpenFGAIntegration(OpenFGAMockMixin, APITestCase.ForUser):
    """Tests for OpenFGA permission integration."""

    def test_create_requires_can_edit_global_entities(self):
        self.openfga_client.can_edit_global_entities.return_value = True
        mac = factory.make_mac_address()

        response = self.client.post(
            reverse("switches_handler"), {"mac_address": mac}
        )

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.openfga_client.can_edit_global_entities.assert_called_once_with(
            self.user
        )

    def test_update_requires_can_edit_global_entities(self):
        self.openfga_client.can_edit_global_entities.return_value = True
        switch = service_layer.services.switches.create(SwitchBuilder())
        factory.make_BootResource(
            name="onie/sonic-4.0",
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
            architecture="amd64/generic",
        )

        response = self.client.put(
            reverse("switch_handler", args=[switch.id]), {"image": "sonic-4.0"}
        )

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.openfga_client.can_edit_global_entities.assert_called_once_with(
            self.user
        )

    def test_delete_requires_can_edit_global_entities(self):
        self.openfga_client.can_edit_global_entities.return_value = True
        switch = service_layer.services.switches.create(SwitchBuilder())

        response = self.client.delete(
            reverse("switch_handler", args=[switch.id])
        )

        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )
        self.openfga_client.can_edit_global_entities.assert_called_once_with(
            self.user
        )
