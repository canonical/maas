# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for VLAN API."""


import http.client
import json
import random

from django.conf import settings
from django.urls import reverse

from maasserver.models import Space, VLAN
from maasserver.models import vlan as vlan_module
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory, RANDOM
from maasserver.utils.orm import post_commit_hooks, reload_object
from maastesting.djangotestcase import CountQueries


def get_vlans_uri(fabric):
    """Return a Fabric's VLAN's URI on the API."""
    return reverse("vlans_handler", args=[fabric.id])


def get_vlan_uri(vlan, fabric=None):
    """Return a Fabric VLAN URI on the API."""
    if fabric is None:
        return reverse("vlanid_handler", args=[vlan.id])
    else:
        fabric = vlan.fabric
        return reverse("vlan_handler", args=[fabric.id, vlan.vid])


class TestVlansAPI(APITestCase.ForUser):
    def setUp(self):
        super().setUp()
        self.patch(vlan_module, "post_commit_do")

    def test_handler_path(self):
        fabric = factory.make_Fabric()
        self.assertEqual(
            "/MAAS/api/2.0/fabrics/%s/vlans/" % (fabric.id),
            get_vlans_uri(fabric),
        )

    def test_read(self):
        def make_vlan():
            space = factory.make_Space()
            subnet = factory.make_Subnet(fabric=fabric, space=space)
            primary_rack = factory.make_RackController()
            factory.make_Interface(node=primary_rack, subnet=subnet)
            secondary_rack = factory.make_RackController()
            factory.make_Interface(node=secondary_rack, subnet=subnet)
            relay_vlan = factory.make_VLAN()
            vlan = subnet.vlan
            vlan.dhcp_on = True
            vlan.primary_rack = primary_rack
            vlan.secondary_rack = secondary_rack
            vlan.relay_vlan = relay_vlan
            vlan.save()

        def serialize_vlan(vlan):
            return {
                "id": vlan.id,
                "name": vlan.get_name(),
                "vid": vlan.vid,
                "fabric": vlan.fabric.name,
                "fabric_id": vlan.fabric_id,
                "mtu": vlan.mtu,
                "primary_rack": (
                    vlan.primary_rack.system_id if vlan.primary_rack else None
                ),
                "secondary_rack": (
                    vlan.secondary_rack.system_id
                    if vlan.secondary_rack
                    else None
                ),
                "dhcp_on": vlan.dhcp_on,
                "external_dhcp": None,
                "relay_vlan": (
                    serialize_vlan(vlan.relay_vlan)
                    if vlan.relay_vlan
                    else None
                ),
                "space": vlan.space.name if vlan.space else "undefined",
                "resource_uri": f"/MAAS/api/2.0/vlans/{vlan.id}/",
            }

        fabric = factory.make_Fabric()
        make_vlan()

        uri = get_vlans_uri(fabric)
        with CountQueries() as counter:
            response = self.client.get(uri)
        base_count = counter.count

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        result = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        # It's three VLANs, since when creating a fabric, a default VLAN
        # is always created.
        vlans = {vlan.id: vlan for vlan in VLAN.objects.filter(fabric=fabric)}
        self.assertEqual(2, len(result))
        for serialized_vlan in result:
            vlan = vlans[serialized_vlan["id"]]
            self.assertEqual(serialize_vlan(vlan), serialized_vlan)

        make_vlan()
        with CountQueries() as counter:
            response = self.client.get(uri)
        # XXX: These really should be equal.
        self.assertEqual(base_count + 7, counter.count)
        self.assertEqual((base_count, counter.count), (25, 32))

    def test_create(self):
        self.become_admin()
        fabric = factory.make_Fabric()
        vlan_name = factory.make_name("fabric")
        vid = random.randint(1, 1000)
        mtu = random.randint(552, 1500)
        uri = get_vlans_uri(fabric)
        response = self.client.post(
            uri, {"name": vlan_name, "vid": vid, "mtu": mtu}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        response_data = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(vlan_name, response_data["name"])
        self.assertEqual(vid, response_data["vid"])
        self.assertEqual(mtu, response_data["mtu"])

    def test_create_with_relay_vlan(self):
        self.become_admin()
        fabric = factory.make_Fabric()
        vlan_name = factory.make_name("fabric")
        vid = random.randint(1, 1000)
        mtu = random.randint(552, 1500)
        relay_vlan = factory.make_VLAN()
        uri = get_vlans_uri(fabric)
        response = self.client.post(
            uri,
            {
                "name": vlan_name,
                "vid": vid,
                "mtu": mtu,
                "relay_vlan": relay_vlan.id,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        response_data = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(vlan_name, response_data["name"])
        self.assertEqual(vid, response_data["vid"])
        self.assertEqual(mtu, response_data["mtu"])
        self.assertEqual(relay_vlan.vid, response_data["relay_vlan"]["vid"])

    def test_create_without_space(self):
        self.become_admin()
        fabric = factory.make_Fabric()
        vlan_name = factory.make_name("fabric")
        vid = random.randint(1, 1000)
        mtu = random.randint(552, 1500)
        uri = get_vlans_uri(fabric)
        response = self.client.post(
            uri, {"name": vlan_name, "vid": vid, "mtu": mtu}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        response_data = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(vlan_name, response_data["name"])
        self.assertEqual(vid, response_data["vid"])
        self.assertEqual(mtu, response_data["mtu"])
        self.assertEqual(Space.UNDEFINED, response_data["space"])

    def test_create_with_space(self):
        self.become_admin()
        fabric = factory.make_Fabric()
        vlan_name = factory.make_name("fabric")
        vid = random.randint(1, 1000)
        mtu = random.randint(552, 1500)
        space = factory.make_Space()
        uri = get_vlans_uri(fabric)
        response = self.client.post(
            uri, {"name": vlan_name, "vid": vid, "mtu": mtu, "space": space.id}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        response_data = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(vlan_name, response_data["name"])
        self.assertEqual(vid, response_data["vid"])
        self.assertEqual(mtu, response_data["mtu"])
        self.assertEqual(space.name, response_data["space"])

    def test_create_admin_only(self):
        fabric = factory.make_Fabric()
        vlan_name = factory.make_name("fabric")
        vid = random.randint(1, 1000)
        uri = get_vlans_uri(fabric)
        response = self.client.post(uri, {"name": vlan_name, "vid": vid})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_create_requires_vid(self):
        self.become_admin()
        fabric = factory.make_Fabric()
        uri = get_vlans_uri(fabric)
        response = self.client.post(uri, {})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(
            {
                "vid": [
                    "This field is required.",
                    "VID must be between 0 and 4094.",
                ]
            },
            json.loads(response.content.decode(settings.DEFAULT_CHARSET)),
        )


class TestVlanAPI(APITestCase.ForUser):
    def test_handler_path(self):
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(fabric=fabric)
        self.assertEqual(
            "/MAAS/api/2.0/vlans/%s/" % vlan.id, get_vlan_uri(vlan)
        )

    def test_read_basic(self):
        fabric = factory.make_Fabric(name="my-fabric")
        vlan = factory.make_VLAN(
            fabric=fabric, name="my-vlan", vid=123, mtu=1234
        )
        uri = get_vlan_uri(vlan)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_vlan = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(
            parsed_vlan,
            {
                "id": vlan.id,
                "name": "my-vlan",
                "vid": 123,
                "fabric": "my-fabric",
                "fabric_id": fabric.id,
                "mtu": 1234,
                "primary_rack": None,
                "secondary_rack": None,
                "dhcp_on": False,
                "external_dhcp": None,
                "relay_vlan": None,
                "space": "undefined",
                "resource_uri": f"/MAAS/api/2.0/vlans/{vlan.id}/",
            },
        )

    def test_read_with_space(self):
        space = factory.make_Space(name="my-space")
        vlan = factory.make_VLAN(space=space)
        uri = get_vlan_uri(vlan, vlan.fabric)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_vlan = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(parsed_vlan["space"], "my-space")

    def test_read_with_dhcp(self):
        subnet = factory.make_Subnet()
        primary_rack = factory.make_RackController()
        factory.make_Interface(node=primary_rack, subnet=subnet)
        secondary_rack = factory.make_RackController()
        factory.make_Interface(node=secondary_rack, subnet=subnet)
        vlan = subnet.vlan
        vlan.dhcp_on = True
        vlan.primary_rack = primary_rack
        vlan.secondary_rack = secondary_rack

        with post_commit_hooks:
            vlan.save()

        uri = get_vlan_uri(vlan, vlan.fabric)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_vlan = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertTrue(parsed_vlan["dhcp_on"])
        self.assertEqual(primary_rack.system_id, parsed_vlan["primary_rack"])
        self.assertEqual(
            secondary_rack.system_id, parsed_vlan["secondary_rack"]
        )

    def test_read_with_relay_vlan(self):
        relay_vlan = factory.make_VLAN(name="my-relay")
        vlan = factory.make_VLAN(relay_vlan=relay_vlan)
        uri = get_vlan_uri(vlan, vlan.fabric)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_vlan = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(
            {
                "id": relay_vlan.id,
                "name": "my-relay",
                "vid": relay_vlan.vid,
                "fabric": relay_vlan.fabric.name,
                "fabric_id": relay_vlan.fabric_id,
                "mtu": relay_vlan.mtu,
                "primary_rack": None,
                "secondary_rack": None,
                "dhcp_on": False,
                "external_dhcp": None,
                "relay_vlan": None,
                "space": "undefined",
                "resource_uri": f"/MAAS/api/2.0/vlans/{relay_vlan.id}/",
            },
            parsed_vlan["relay_vlan"],
        )

    def test_read_404_when_bad_id(self):
        fabric = factory.make_Fabric()
        uri = reverse(
            "vlan_handler", args=[fabric.id, random.randint(100, 1000)]
        )
        response = self.client.get(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_update(self):
        self.become_admin()
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(fabric=fabric)
        uri = get_vlan_uri(vlan)
        new_name = factory.make_name("vlan")
        new_vid = random.randint(1, 1000)
        response = self.client.put(uri, {"name": new_name, "vid": new_vid})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_vlan = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        vlan = reload_object(vlan)
        self.assertEqual(new_name, parsed_vlan["name"])
        self.assertEqual(new_name, vlan.name)
        self.assertEqual(new_vid, parsed_vlan["vid"])
        self.assertEqual(new_vid, vlan.vid)

    def test_update_sets_relay_vlan(self):
        self.become_admin()
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(fabric=fabric)
        uri = get_vlan_uri(vlan)
        relay_vlan = factory.make_VLAN()
        response = self.client.put(uri, {"relay_vlan": relay_vlan.id})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_vlan = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        vlan = reload_object(vlan)
        self.assertEqual(relay_vlan.vid, parsed_vlan["relay_vlan"]["vid"])
        self.assertEqual(relay_vlan, vlan.relay_vlan)

    def test_update_with_fabric(self):
        self.become_admin()
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(fabric=fabric)
        uri = get_vlan_uri(vlan, fabric)
        new_name = factory.make_name("vlan")
        new_vid = random.randint(1, 1000)
        response = self.client.put(uri, {"name": new_name, "vid": new_vid})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_vlan = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        vlan = reload_object(vlan)
        self.assertEqual(new_name, parsed_vlan["name"])
        self.assertEqual(new_name, vlan.name)
        self.assertEqual(new_vid, parsed_vlan["vid"])
        self.assertEqual(new_vid, vlan.vid)

    def test_update_with_empty_space_clears_space(self):
        self.become_admin()
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(fabric=fabric, space=RANDOM)
        self.assertIsNotNone(vlan.space)
        uri = get_vlan_uri(vlan, fabric)
        response = self.client.put(uri, {"space": ""})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_vlan = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        vlan = reload_object(vlan)
        self.assertIsNone(vlan.space)
        self.assertEqual(Space.UNDEFINED, parsed_vlan["space"])

    def test_update_with_undefined_space_clears_space(self):
        self.become_admin()
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(fabric=fabric, space=RANDOM)
        self.assertIsNotNone(vlan.space)
        uri = get_vlan_uri(vlan, fabric)
        response = self.client.put(uri, {"space": Space.UNDEFINED})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_vlan = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        vlan = reload_object(vlan)
        self.assertIsNone(vlan.space)
        self.assertEqual(Space.UNDEFINED, parsed_vlan["space"])

    def test_update_admin_only(self):
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(fabric=fabric)
        uri = get_vlan_uri(vlan)
        new_name = factory.make_name("vlan")
        response = self.client.put(uri, {"name": new_name})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_update_400_when_bad_primary_rack(self):
        self.become_admin()
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(fabric=fabric)
        uri = get_vlan_uri(vlan)
        response = self.client.put(
            uri, {"primary_rack": factory.make_name("primary_rack")}
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_update_400_when_bad_secondary_rack(self):
        self.become_admin()
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(fabric=fabric)
        uri = get_vlan_uri(vlan)
        response = self.client.put(
            uri, {"secondary_rack": factory.make_name("secondary_rack")}
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_delete_deletes_vlan(self):
        self.become_admin()
        vlan = factory.make_VLAN()
        uri = get_vlan_uri(vlan)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )
        self.assertIsNone(reload_object(vlan))

    def test_delete_with_fabric_deletes_vlan(self):
        self.become_admin()
        vlan = factory.make_VLAN()
        uri = get_vlan_uri(vlan, vlan.fabric)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )
        self.assertIsNone(reload_object(vlan))

    def test_delete_403_when_not_admin(self):
        vlan = factory.make_VLAN()
        uri = get_vlan_uri(vlan)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )
        self.assertIsNotNone(reload_object(vlan))

    def test_delete_403_when_not_admin_using_fabric_vid(self):
        vlan = factory.make_VLAN()
        uri = get_vlan_uri(vlan, vlan.fabric)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )
        self.assertIsNotNone(reload_object(vlan))

    def test_delete_404_when_invalid_id(self):
        self.become_admin()
        uri = reverse("vlanid_handler", args=[random.randint(100, 1000)])
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_delete_404_when_invalid_fabric_vid(self):
        fabric = factory.make_Fabric()
        self.become_admin()
        uri = reverse(
            "vlan_handler", args=[fabric.id, random.randint(100, 1000)]
        )
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )
