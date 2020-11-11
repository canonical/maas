# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for VLAN API."""


import http.client
import json
import random

from django.conf import settings
from django.urls import reverse
from testtools.matchers import ContainsDict, Equals, Is, Not

from maasserver.models import Space
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory, RANDOM
from maasserver.utils.orm import reload_object


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
    def test_handler_path(self):
        fabric = factory.make_Fabric()
        self.assertEqual(
            "/MAAS/api/2.0/fabrics/%s/vlans/" % (fabric.id),
            get_vlans_uri(fabric),
        )

    def test_read(self):
        fabric = factory.make_Fabric()
        for vid in range(1, 4):
            factory.make_VLAN(vid=vid, fabric=fabric)
        uri = get_vlans_uri(fabric)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        expected_ids = [vlan.vid for vlan in fabric.vlan_set.all()]
        result_ids = [
            vlan["vid"]
            for vlan in json.loads(
                response.content.decode(settings.DEFAULT_CHARSET)
            )
        ]
        self.assertItemsEqual(expected_ids, result_ids)

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

    def test_read(self):
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(fabric=fabric)
        uri = get_vlan_uri(vlan)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_vlan = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertThat(
            parsed_vlan,
            ContainsDict(
                {
                    "id": Equals(vlan.id),
                    "name": Equals(vlan.get_name()),
                    "vid": Equals(vlan.vid),
                    "fabric": Equals(fabric.get_name()),
                    "fabric_id": Equals(fabric.id),
                    "resource_uri": Equals(get_vlan_uri(vlan)),
                }
            ),
        )

    def test_read_with_fabric(self):
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(fabric=fabric)
        uri = get_vlan_uri(vlan, fabric)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_vlan = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertThat(
            parsed_vlan,
            ContainsDict(
                {
                    "id": Equals(vlan.id),
                    "name": Equals(vlan.get_name()),
                    "vid": Equals(vlan.vid),
                    "fabric": Equals(fabric.get_name()),
                    "resource_uri": Equals(get_vlan_uri(vlan)),
                }
            ),
        )

    def test_read_with_space(self):
        space = factory.make_Space()
        vlan = factory.make_VLAN(space=space)
        uri = get_vlan_uri(vlan, vlan.fabric)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_vlan = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertThat(
            parsed_vlan,
            ContainsDict(
                {
                    "id": Equals(vlan.id),
                    "name": Equals(vlan.get_name()),
                    "vid": Equals(vlan.vid),
                    "space": Equals(space.get_name()),
                    "resource_uri": Equals(get_vlan_uri(vlan)),
                }
            ),
        )

    def test_read_without_space_returns_undefined_space(self):
        vlan = factory.make_VLAN(space=None)
        uri = get_vlan_uri(vlan, vlan.fabric)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_vlan = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertThat(
            parsed_vlan,
            ContainsDict(
                {
                    "id": Equals(vlan.id),
                    "name": Equals(vlan.get_name()),
                    "vid": Equals(vlan.vid),
                    "space": Equals(Space.UNDEFINED),
                    "resource_uri": Equals(get_vlan_uri(vlan)),
                }
            ),
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
        self.assertThat(vlan.space, Not(Is(None)))
        uri = get_vlan_uri(vlan, fabric)
        response = self.client.put(uri, {"space": ""})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_vlan = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        vlan = reload_object(vlan)
        self.assertThat(vlan.space, Is(None))
        self.assertThat(parsed_vlan["space"], Equals(Space.UNDEFINED))

    def test_update_with_undefined_space_clears_space(self):
        self.become_admin()
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(fabric=fabric, space=RANDOM)
        self.assertThat(vlan.space, Not(Is(None)))
        uri = get_vlan_uri(vlan, fabric)
        response = self.client.put(uri, {"space": Space.UNDEFINED})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_vlan = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        vlan = reload_object(vlan)
        self.assertThat(vlan.space, Is(None))
        self.assertThat(parsed_vlan["space"], Equals(Space.UNDEFINED))

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

    def test_delete_400_when_invalid_url(self):
        factory.make_Fabric()
        self.become_admin()
        uri = reverse("vlan_handler", args=[" ", " "])
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
