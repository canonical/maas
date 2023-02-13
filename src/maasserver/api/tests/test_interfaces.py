# Copyright 2015-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import http.client
import random

from django.urls import reverse
from testtools.matchers import (
    ContainsDict,
    Equals,
    MatchesDict,
    MatchesListwise,
    MatchesSetwise,
)

from maasserver.enum import (
    INTERFACE_LINK_TYPE,
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_STATUS,
    NODE_STATUS_CHOICES,
    NODE_TYPE,
)
from maasserver.models import Interface
from maasserver.models.vlan import DEFAULT_MTU
from maasserver.testing.api import APITestCase, APITransactionTestCase
from maasserver.testing.factory import factory
from maasserver.utils.converters import json_load_bytes
from maasserver.utils.orm import reload_object
from maastesting.djangotestcase import count_queries

EDITABLE_STATUSES = (
    NODE_STATUS.NEW,
    NODE_STATUS.READY,
    NODE_STATUS.FAILED_TESTING,
    NODE_STATUS.ALLOCATED,
    NODE_STATUS.BROKEN,
)

BLOCKED_STATUSES = (
    status
    for status, _ in NODE_STATUS_CHOICES
    if status not in EDITABLE_STATUSES
)


def get_interfaces_uri(node):
    """Return a interfaces URI on the API."""
    return reverse("interfaces_handler", args=[node.system_id])


def get_interface_uri(interface, node=None):
    """Return a interface URI on the API."""
    if isinstance(interface, Interface):
        if node is None:
            node = interface.get_node()
        interface = interface.id
    return reverse("interface_handler", args=[node.system_id, interface])


def serialize_vlan(vlan):
    return {
        "id": vlan.id,
        "dhcp_on": vlan.dhcp_on,
        "external_dhcp": vlan.external_dhcp,
        "fabric": vlan.fabric.get_name(),
        "fabric_id": vlan.fabric_id,
        "mtu": vlan.mtu,
        "primary_rack": None,
        "secondary_rack": None,
        "space": "undefined" if not vlan.space else vlan.space.get_name(),
        "vid": vlan.vid,
        "name": vlan.get_name(),
        "relay_vlan": None,
        "resource_uri": f"/MAAS/api/2.0/vlans/{vlan.id}/",
    }


def serialize_subnet(subnet):
    return {
        "name": subnet.name,
        "id": subnet.id,
        "vlan": serialize_vlan(subnet.vlan),
        "description": "",
        "cidr": subnet.cidr,
        "rdns_mode": subnet.rdns_mode,
        "gateway_ip": subnet.gateway_ip,
        "dns_servers": subnet.dns_servers,
        "allow_dns": subnet.allow_dns,
        "allow_proxy": subnet.allow_proxy,
        "active_discovery": subnet.active_discovery,
        "managed": subnet.managed,
        "disabled_boot_architectures": subnet.disabled_boot_architectures,
        "space": "undefined" if not subnet.space else subnet.space.get_name(),
        "resource_uri": f"/MAAS/api/2.0/subnets/{subnet.id}/",
    }


def make_complex_interface(node, name=None):
    """Makes interface with parents and children."""
    fabric = factory.make_Fabric()
    vlan_5 = factory.make_VLAN(vid=5, fabric=fabric)
    nic_0 = factory.make_Interface(
        INTERFACE_TYPE.PHYSICAL, vlan=vlan_5, node=node
    )
    nic_1 = factory.make_Interface(
        INTERFACE_TYPE.PHYSICAL, vlan=vlan_5, node=node
    )
    parents = [nic_0, nic_1]
    bond_interface = factory.make_Interface(
        INTERFACE_TYPE.BOND,
        mac_address=nic_0.mac_address,
        vlan=vlan_5,
        parents=parents,
        name=name,
    )
    vlan_10 = factory.make_VLAN(vid=10, fabric=fabric)
    vlan_nic_10 = factory.make_Interface(
        INTERFACE_TYPE.VLAN, vlan=vlan_10, parents=[bond_interface]
    )
    vlan_11 = factory.make_VLAN(vid=11, fabric=fabric)
    vlan_nic_11 = factory.make_Interface(
        INTERFACE_TYPE.VLAN, vlan=vlan_11, parents=[bond_interface]
    )
    return bond_interface, parents, [vlan_nic_10, vlan_nic_11]


class TestInterfacesAPI(APITestCase.ForUser):
    def test_handler_path(self):
        node = factory.make_Node()
        self.assertEqual(
            "/MAAS/api/2.0/nodes/%s/interfaces/" % (node.system_id),
            get_interfaces_uri(node),
        )

    def test_read(self):
        node = factory.make_Node()
        bond, parents, children = make_complex_interface(node)
        uri = get_interfaces_uri(node)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        expected_ids = [nic.id for nic in [bond] + parents + children]
        result_ids = [nic["id"] for nic in json_load_bytes(response.content)]
        self.assertCountEqual(expected_ids, result_ids)

    def test_read_physical_includes_numa_node(self):
        numa_node = factory.make_NUMANode()
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL, numa_node=numa_node)
        uri = get_interfaces_uri(numa_node.node)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        [interface] = json_load_bytes(response.content)
        self.assertEqual(interface["numa_node"], numa_node.index)

    def test_read_includes_sriov_max_vf(self):
        node = factory.make_Node()
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, sriov_max_vf=16
        )
        uri = get_interfaces_uri(node)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        [interface] = json_load_bytes(response.content)
        self.assertEqual(interface["sriov_max_vf"], 16)

    def test_read_on_device(self):
        parent = factory.make_Node()
        device = factory.make_Device(owner=self.user, parent=parent)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=device
        )
        uri = get_interfaces_uri(device)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertEqual(
            interface.id, json_load_bytes(response.content)[0]["id"]
        )

    def test_read_uses_constant_number_of_queries(self):
        node = factory.make_Node()
        bond1, parents1, children1 = make_complex_interface(node)
        uri = get_interfaces_uri(node)

        num_queries1, response1 = count_queries(self.client.get, uri)

        bond2, parents2, children2 = make_complex_interface(node)
        num_queries2, response2 = count_queries(self.client.get, uri)

        # Make sure the responses are ok as it's not useful to compare the
        # number of queries if they are not.
        parsed_result_1 = json_load_bytes(response1.content)
        parsed_result_2 = json_load_bytes(response2.content)
        self.assertEqual(
            [
                http.client.OK,
                http.client.OK,
                len([bond1] + parents1 + children1),
                len(
                    [bond1, bond2]
                    + parents1
                    + parents2
                    + children1
                    + children2
                ),
            ],
            [
                response1.status_code,
                response2.status_code,
                len(parsed_result_1),
                len(parsed_result_2),
            ],
        )
        self.assertEqual(num_queries1, num_queries2)

    def test_create_physical(self):
        self.become_admin()
        for status in EDITABLE_STATUSES:
            node = factory.make_Node(status=status)
            mac = factory.make_mac_address()
            name = factory.make_name("eth")
            vlan = factory.make_VLAN()
            tags = [factory.make_name("tag") for _ in range(3)]
            uri = get_interfaces_uri(node)
            response = self.client.post(
                uri,
                {
                    "op": "create_physical",
                    "mac_address": mac,
                    "name": name,
                    "vlan": vlan.id,
                    "tags": ",".join(tags),
                },
            )

            self.assertEqual(
                http.client.OK, response.status_code, response.content
            )
            self.assertThat(
                json_load_bytes(response.content),
                ContainsDict(
                    {
                        "mac_address": Equals(mac),
                        "name": Equals(name),
                        "vlan": ContainsDict({"id": Equals(vlan.id)}),
                        "type": Equals("physical"),
                        "tags": Equals(tags),
                        "enabled": Equals(True),
                    }
                ),
            )

    def test_create_physical_on_device(self):
        parent = factory.make_Node()
        device = factory.make_Device(owner=self.user, parent=parent)
        mac = factory.make_mac_address()
        name = factory.make_name("eth")
        vlan = factory.make_VLAN()
        tags = [factory.make_name("tag") for _ in range(3)]
        uri = get_interfaces_uri(device)
        response = self.client.post(
            uri,
            {
                "op": "create_physical",
                "mac_address": mac,
                "name": name,
                "vlan": vlan.id,
                "tags": ",".join(tags),
            },
        )

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertThat(
            json_load_bytes(response.content),
            ContainsDict(
                {
                    "mac_address": Equals(mac),
                    "name": Equals(name),
                    "vlan": ContainsDict({"id": Equals(vlan.id)}),
                    "type": Equals("physical"),
                    "tags": Equals(tags),
                    "enabled": Equals(True),
                }
            ),
        )

    def test_create_physical_disabled(self):
        self.become_admin()
        for status in EDITABLE_STATUSES:
            node = factory.make_Node(status=status)
            mac = factory.make_mac_address()
            name = factory.make_name("eth")
            vlan = factory.make_VLAN()
            tags = [factory.make_name("tag") for _ in range(3)]
            uri = get_interfaces_uri(node)
            response = self.client.post(
                uri,
                {
                    "op": "create_physical",
                    "mac_address": mac,
                    "name": name,
                    "vlan": vlan.id,
                    "tags": ",".join(tags),
                    "enabled": False,
                },
            )

            self.assertEqual(
                http.client.OK, response.status_code, response.content
            )
            self.assertThat(
                json_load_bytes(response.content),
                ContainsDict(
                    {
                        "mac_address": Equals(mac),
                        "name": Equals(name),
                        "vlan": ContainsDict({"id": Equals(vlan.id)}),
                        "type": Equals("physical"),
                        "tags": Equals(tags),
                        "enabled": Equals(False),
                    }
                ),
            )

    def test_create_physical_requires_admin(self):
        node = factory.make_Node()
        mac = factory.make_mac_address()
        name = factory.make_name("eth")
        vlan = factory.make_VLAN()
        uri = get_interfaces_uri(node)
        response = self.client.post(
            uri,
            {
                "op": "create_physical",
                "mac_address": mac,
                "name": name,
                "vlan": vlan.id,
            },
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_create_physical_409_when_invalid_status(self):
        self.become_admin()
        for status in BLOCKED_STATUSES:
            node = factory.make_Node(status=status)
            mac = factory.make_mac_address()
            name = factory.make_name("eth")
            vlan = factory.make_VLAN()
            uri = get_interfaces_uri(node)
            response = self.client.post(
                uri,
                {
                    "op": "create_physical",
                    "mac_address": mac,
                    "name": name,
                    "vlan": vlan.id,
                },
            )
            self.assertEqual(
                http.client.CONFLICT, response.status_code, response.content
            )

    def test_create_physical_requires_mac(self):
        self.become_admin()
        node = factory.make_Node(
            status=random.choice(EDITABLE_STATUSES), bmc=factory.make_BMC()
        )
        uri = get_interfaces_uri(node)
        response = self.client.post(uri, {"op": "create_physical"})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(
            {"mac_address": ["This field is required."]},
            json_load_bytes(response.content),
        )

    def test_create_physical_doesnt_allow_mac_already_register(self):
        self.become_admin()
        node = factory.make_Node(status=random.choice(EDITABLE_STATUSES))
        interface_on_other_node = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL
        )
        name = factory.make_name("eth")
        vlan = factory.make_VLAN()
        uri = get_interfaces_uri(node)
        response = self.client.post(
            uri,
            {
                "op": "create_physical",
                "mac_address": "%s" % interface_on_other_node.mac_address,
                "name": name,
                "vlan": vlan.id,
            },
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(
            {
                "mac_address": [
                    "This MAC address is already in use by %s."
                    % (interface_on_other_node.get_log_string())
                ]
            },
            json_load_bytes(response.content),
        )

    def test_create_bond(self):
        self.become_admin()
        for status in EDITABLE_STATUSES:
            node = factory.make_Node(status=status)
            vlan = factory.make_VLAN()
            parent_1_iface = factory.make_Interface(
                INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=node
            )
            parent_2_iface = factory.make_Interface(
                INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=node
            )
            name = factory.make_name("bond")
            tags = [factory.make_name("tag") for _ in range(3)]
            uri = get_interfaces_uri(node)
            response = self.client.post(
                uri,
                {
                    "op": "create_bond",
                    "mac_address": "%s" % parent_1_iface.mac_address,
                    "name": name,
                    "vlan": vlan.id,
                    "parents": [parent_1_iface.id, parent_2_iface.id],
                    "tags": ",".join(tags),
                },
            )

            self.assertEqual(
                http.client.OK, response.status_code, response.content
            )
            parsed_interface = json_load_bytes(response.content)
            self.assertThat(
                parsed_interface,
                ContainsDict(
                    {
                        "mac_address": Equals(
                            "%s" % parent_1_iface.mac_address
                        ),
                        "name": Equals(name),
                        "vlan": ContainsDict({"id": Equals(vlan.id)}),
                        "type": Equals("bond"),
                        "tags": Equals(tags),
                    }
                ),
            )
            self.assertCountEqual(
                [parent_1_iface.name, parent_2_iface.name],
                parsed_interface["parents"],
            )

    def test_create_bond_404_on_device(self):
        parent = factory.make_Node()
        device = factory.make_Node(
            owner=self.user, parent=parent, node_type=NODE_TYPE.DEVICE
        )
        uri = get_interfaces_uri(device)
        response = self.client.post(uri, {"op": "create_bond"})
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_create_bond_requires_admin(self):
        node = factory.make_Node()
        vlan = factory.make_VLAN()
        parent_1_iface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=node
        )
        parent_2_iface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=node
        )
        name = factory.make_name("bond")
        uri = get_interfaces_uri(node)
        response = self.client.post(
            uri,
            {
                "op": "create_bond",
                "mac": "%s" % parent_1_iface.mac_address,
                "name": name,
                "vlan": vlan.id,
                "parents": [parent_1_iface.id, parent_2_iface.id],
            },
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_create_bond_409_when_invalid_status(self):
        self.become_admin()
        for status in BLOCKED_STATUSES:
            node = factory.make_Node(status=status)
            vlan = factory.make_VLAN()
            parent_1_iface = factory.make_Interface(
                INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=node
            )
            parent_2_iface = factory.make_Interface(
                INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=node
            )
            name = factory.make_name("bond")
            uri = get_interfaces_uri(node)
            response = self.client.post(
                uri,
                {
                    "op": "create_bond",
                    "mac": "%s" % parent_1_iface.mac_address,
                    "name": name,
                    "vlan": vlan.id,
                    "parents": [parent_1_iface.id, parent_2_iface.id],
                },
            )
            self.assertEqual(
                http.client.CONFLICT, response.status_code, response.content
            )

    def test_create_bond_requires_name_vlan_and_parents(self):
        self.become_admin()
        node = factory.make_Node(status=random.choice(EDITABLE_STATUSES))
        uri = get_interfaces_uri(node)
        response = self.client.post(uri, {"op": "create_bond"})

        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(
            {
                "mac_address": ["This field cannot be blank."],
                "name": ["This field is required."],
                "parents": ["A bond interface must have one or more parents."],
            },
            json_load_bytes(response.content),
        )

    def test_create_vlan(self):
        self.become_admin()
        node = factory.make_Node(status=random.choice(EDITABLE_STATUSES))
        untagged_vlan = factory.make_VLAN()
        parent_iface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=untagged_vlan, node=node
        )
        tagged_vlan = factory.make_VLAN()
        tags = [factory.make_name("tag") for _ in range(3)]
        uri = get_interfaces_uri(node)
        response = self.client.post(
            uri,
            {
                "op": "create_vlan",
                "vlan": tagged_vlan.id,
                "parent": parent_iface.id,
                "tags": ",".join(tags),
            },
        )

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_interface = json_load_bytes(response.content)
        self.assertThat(
            parsed_interface,
            ContainsDict(
                {
                    "mac_address": Equals("%s" % parent_iface.mac_address),
                    "vlan": ContainsDict({"id": Equals(tagged_vlan.id)}),
                    "type": Equals("vlan"),
                    "parents": Equals([parent_iface.name]),
                    "tags": Equals(tags),
                }
            ),
        )

    def test_create_vlan_404_on_device(self):
        parent = factory.make_Node()
        device = factory.make_Node(
            owner=self.user, parent=parent, node_type=NODE_TYPE.DEVICE
        )
        uri = get_interfaces_uri(device)
        response = self.client.post(uri, {"op": "create_vlan"})
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_create_vlan_requires_admin(self):
        node = factory.make_Node(status=random.choice(EDITABLE_STATUSES))
        untagged_vlan = factory.make_VLAN()
        parent_iface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=untagged_vlan, node=node
        )
        tagged_vlan = factory.make_VLAN()
        uri = get_interfaces_uri(node)
        response = self.client.post(
            uri,
            {
                "op": "create_vlan",
                "vlan": tagged_vlan.vid,
                "parent": parent_iface.id,
            },
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_create_vlan_requires_vlan_and_parent(self):
        self.become_admin()
        node = factory.make_Node(status=random.choice(EDITABLE_STATUSES))
        uri = get_interfaces_uri(node)
        response = self.client.post(uri, {"op": "create_vlan"})

        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(
            {
                "vlan": [
                    "A VLAN interface must be connected to a tagged VLAN."
                ],
                "parent": ["A VLAN interface must have exactly one parent."],
            },
            json_load_bytes(response.content),
        )

    def test_create_bridge(self):
        self.become_admin()
        name = factory.make_name("br")
        node = factory.make_Node(status=random.choice(EDITABLE_STATUSES))
        untagged_vlan = factory.make_VLAN()
        parent_iface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=untagged_vlan, node=node
        )
        tags = [factory.make_name("tag") for _ in range(3)]
        uri = get_interfaces_uri(node)
        response = self.client.post(
            uri,
            {
                "op": "create_bridge",
                "name": name,
                "vlan": untagged_vlan.id,
                "parent": parent_iface.id,
                "tags": ",".join(tags),
            },
        )

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_interface = json_load_bytes(response.content)
        self.assertThat(
            parsed_interface,
            ContainsDict(
                {
                    "name": Equals(name),
                    "mac_address": Equals("%s" % parent_iface.mac_address),
                    "vlan": ContainsDict({"id": Equals(untagged_vlan.id)}),
                    "type": Equals("bridge"),
                    "parents": Equals([parent_iface.name]),
                    "tags": MatchesSetwise(*map(Equals, tags)),
                }
            ),
        )

    def test_create_bridge_404_on_device(self):
        parent = factory.make_Node()
        device = factory.make_Node(
            owner=self.user, parent=parent, node_type=NODE_TYPE.DEVICE
        )
        uri = get_interfaces_uri(device)
        response = self.client.post(uri, {"op": "create_bridge"})
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_create_bridge_requires_admin(self):
        node = factory.make_Node(status=random.choice(EDITABLE_STATUSES))
        untagged_vlan = factory.make_VLAN()
        parent_iface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=untagged_vlan, node=node
        )
        uri = get_interfaces_uri(node)
        response = self.client.post(
            uri,
            {
                "op": "create_bridge",
                "vlan": untagged_vlan.vid,
                "parent": parent_iface.id,
            },
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_create_bridge_requires_name_and_parent(self):
        self.become_admin()
        node = factory.make_Node(status=random.choice(EDITABLE_STATUSES))
        uri = get_interfaces_uri(node)
        response = self.client.post(uri, {"op": "create_bridge"})

        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(
            {
                "name": ["This field is required."],
                "parent": ["A bridge interface must have exactly one parent."],
                "mac_address": ["This field cannot be blank."],
            },
            json_load_bytes(response.content),
        )

    def test_create_acquired_bridge(self):
        self.become_admin()
        name = factory.make_name("br")
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=self.user)
        parent_fabric = factory.make_Fabric()
        parent_vlan = parent_fabric.get_default_vlan()
        parent_iface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=parent_vlan
        )
        parent_subnet = factory.make_Subnet(vlan=parent_vlan)
        parent_sip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip=factory.pick_ip_in_Subnet(parent_subnet),
            subnet=parent_subnet,
            interface=parent_iface,
        )
        tags = [factory.make_name("tag") for _ in range(3)]
        uri = get_interfaces_uri(node)
        response = self.client.post(
            uri,
            {
                "op": "create_bridge",
                "name": name,
                "parent": parent_iface.id,
                "tags": ",".join(tags),
            },
        )

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_interface = json_load_bytes(response.content)
        self.assertThat(
            parsed_interface,
            ContainsDict(
                {
                    "name": Equals(name),
                    "mac_address": Equals("%s" % parent_iface.mac_address),
                    "vlan": ContainsDict({"id": Equals(parent_vlan.id)}),
                    "type": Equals("bridge"),
                    "parents": Equals([parent_iface.name]),
                    "tags": MatchesSetwise(*map(Equals, tags)),
                    "links": MatchesListwise(
                        [
                            ContainsDict(
                                {
                                    "id": Equals(parent_sip.id),
                                    "ip_address": Equals(parent_sip.ip),
                                    "subnet": ContainsDict(
                                        {"cidr": Equals(parent_subnet.cidr)}
                                    ),
                                }
                            )
                        ]
                    ),
                }
            ),
        )

    def test_create_acquired_bridge_not_allowed_in_ready(self):
        name = factory.make_name("br")
        node = factory.make_Node(status=random.choice(EDITABLE_STATUSES))
        parent_fabric = factory.make_Fabric()
        parent_vlan = parent_fabric.get_default_vlan()
        parent_iface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=parent_vlan
        )
        uri = get_interfaces_uri(node)
        response = self.client.post(
            uri,
            {"op": "create_bridge", "name": name, "parent": parent_iface.id},
        )

        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )


class TestInterfacesAPIForControllers(APITestCase.ForUser):
    scenarios = (
        ("region", {"maker": factory.make_RegionController}),
        ("rack", {"maker": factory.make_RackController}),
        ("region-rack", {"maker": factory.make_RegionRackController}),
    )

    def test_read(self):
        node = self.maker()
        for _ in range(3):
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        factory.make_Interface(INTERFACE_TYPE.BRIDGE, node=node)
        uri = get_interfaces_uri(node)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        output_content = json_load_bytes(response.content)
        expected_ids = [
            nic.id for nic in node.current_config.interface_set.all()
        ]
        result_ids = [nic["id"] for nic in output_content]
        self.assertCountEqual(expected_ids, result_ids)
        for nic in output_content:
            self.assertIn("links", nic)

    def test_create_physical_is_forbidden(self):
        self.become_admin()
        node = self.maker()
        mac = factory.make_mac_address()
        name = factory.make_name("eth")
        vlan = factory.make_VLAN()
        tags = [factory.make_name("tag") for _ in range(3)]
        uri = get_interfaces_uri(node)
        response = self.client.post(
            uri,
            {
                "op": "create_physical",
                "mac_address": mac,
                "name": name,
                "vlan": vlan.id,
                "tags": ",".join(tags),
            },
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_create_bond_is_forbidden(self):
        self.become_admin()
        node = self.maker()
        vlan = factory.make_VLAN()
        parent_1_iface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=node
        )
        parent_2_iface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=node
        )
        name = factory.make_name("bond")
        tags = [factory.make_name("tag") for _ in range(3)]
        uri = get_interfaces_uri(node)
        response = self.client.post(
            uri,
            {
                "op": "create_bond",
                "mac_address": "%s" % parent_1_iface.mac_address,
                "name": name,
                "vlan": vlan.id,
                "parents": [parent_1_iface.id, parent_2_iface.id],
                "tags": ",".join(tags),
            },
        )

        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_create_vlan_is_forbidden(self):
        self.become_admin()
        node = self.maker()
        untagged_vlan = factory.make_VLAN()
        parent_iface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=untagged_vlan, node=node
        )
        tagged_vlan = factory.make_VLAN()
        tags = [factory.make_name("tag") for _ in range(3)]
        uri = get_interfaces_uri(node)
        response = self.client.post(
            uri,
            {
                "op": "create_vlan",
                "vlan": tagged_vlan.id,
                "parent": parent_iface.id,
                "tags": ",".join(tags),
            },
        )

        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )


class TestNodeInterfaceAPI(APITransactionTestCase.ForUser):
    def test_handler_path(self):
        node = factory.make_Node(interface=True)
        interface = node.get_boot_interface()
        self.assertEqual(
            "/MAAS/api/2.0/nodes/%s/interfaces/%s/"
            % (node.system_id, interface.id),
            get_interface_uri(interface, node=node),
        )

    def test_read_basic(self):
        node = factory.make_Node()
        interface = factory.make_Interface(
            node=node,
            name="eno1",
            iftype=INTERFACE_TYPE.PHYSICAL,
            mac_address="11:11:11:11:11:11",
            enabled=False,
            vendor="my-vendor",
            product="my-product",
            firmware_version="1.2.3",
            link_connected=False,
            vlan=None,
            interface_speed=100,
            sriov_max_vf=0,
            tags=[],
        )

        uri = get_interface_uri(interface)
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_interface = json_load_bytes(response.content)
        self.maxDiff = None
        self.assertEqual(
            {
                "system_id": node.system_id,
                "id": interface.id,
                "name": "eno1",
                "type": INTERFACE_TYPE.PHYSICAL,
                "vlan": None,
                "mac_address": "11:11:11:11:11:11",
                "parents": [],
                "children": [],
                "tags": [],
                "enabled": False,
                "links": [],
                "params": "",
                "discovered": None,
                "effective_mtu": DEFAULT_MTU,
                "vendor": "my-vendor",
                "product": "my-product",
                "firmware_version": "1.2.3",
                "link_connected": False,
                "interface_speed": 100,
                "link_speed": 0,
                "numa_node": 0,
                "sriov_max_vf": 0,
                "resource_uri": (
                    f"/MAAS/api/2.0/nodes/{node.system_id}/interfaces/{interface.id}/"
                ),
            },
            parsed_interface,
        )

    def test_read_connected(self):
        vlan = factory.make_VLAN(name="my-vlan", mtu=1234)
        interface = factory.make_Interface(
            enabled=True,
            link_connected=True,
            vlan=vlan,
            interface_speed=100,
            link_speed=10,
            tags=["foo", "bar"],
        )

        uri = get_interface_uri(interface)
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_interface = json_load_bytes(response.content)
        expected_parts = {
            "id": interface.id,
            "tags": ["foo", "bar"],
            "enabled": True,
            "discovered": None,
            "effective_mtu": 1234,
            "link_connected": True,
            "interface_speed": 100,
            "link_speed": 10,
            "vlan": {
                "id": vlan.id,
                "dhcp_on": vlan.dhcp_on,
                "external_dhcp": vlan.external_dhcp,
                "fabric": vlan.fabric.get_name(),
                "fabric_id": vlan.fabric_id,
                "mtu": vlan.mtu,
                "primary_rack": None,
                "secondary_rack": None,
                "space": "undefined",
                "vid": vlan.vid,
                "name": vlan.get_name(),
                "relay_vlan": None,
                "resource_uri": f"/MAAS/api/2.0/vlans/{vlan.id}/",
            },
        }
        for key, value in expected_parts.items():
            self.assertEqual(parsed_interface[key], value)

    def test_read(self):
        node = factory.make_Node()
        bond, parents, children = make_complex_interface(node)

        # Add some known links to the bond interface.
        dhcp_subnet = factory.make_Subnet(vlan=bond.vlan)
        dhcp_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DHCP,
            ip="",
            subnet=dhcp_subnet,
            interface=bond,
        )
        discovered_ip = factory.pick_ip_in_network(dhcp_subnet.get_ipnetwork())
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
            ip=discovered_ip,
            subnet=dhcp_subnet,
            interface=bond,
        )

        # Second link is a STATIC ip link.
        static_subnet = factory.make_Subnet(vlan=bond.vlan)
        static_ip = factory.pick_ip_in_network(static_subnet.get_ipnetwork())
        sip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=static_ip,
            subnet=static_subnet,
            interface=bond,
        )

        # Third link is just a LINK_UP. In reality this cannot exist while the
        # other two links exist but for testing we allow it. If validation of
        # the StaticIPAddress model ever included this check, which it
        # probably should then this will fail and cause this test to break.
        link_subnet = factory.make_Subnet(vlan=bond.vlan)
        link_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip="",
            subnet=link_subnet,
            interface=bond,
        )

        # Add MTU parameter.
        bond.params = {"mtu": 1234}
        bond.save()

        uri = get_interface_uri(bond)
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_interface = json_load_bytes(response.content)

        expected_parts = {
            "id": bond.id,
            "name": bond.name,
            "type": bond.type,
            "mac_address": str(bond.mac_address),
            "vlan": serialize_vlan(bond.vlan),
            "tags": bond.tags,
            "resource_uri": get_interface_uri(bond),
            "params": {"mtu": 1234},
            "effective_mtu": 1500,
            "system_id": node.system_id,
        }
        for key, value in expected_parts.items():
            self.assertEqual(parsed_interface[key], value)
        self.assertCountEqual(
            [nic.name for nic in parents], parsed_interface["parents"]
        )
        self.assertCountEqual(
            [nic.name for nic in children], parsed_interface["children"]
        )

        self.assertEqual(
            [
                {
                    "id": dhcp_ip.id,
                    "mode": "dhcp",
                    "ip_address": discovered_ip,
                    "subnet": serialize_subnet(dhcp_subnet),
                },
                {
                    "id": sip.id,
                    "mode": "static",
                    "ip_address": static_ip,
                    "subnet": serialize_subnet(static_subnet),
                },
                {
                    "id": link_ip.id,
                    "mode": "link_up",
                    "subnet": serialize_subnet(link_subnet),
                },
            ],
            parsed_interface["links"],
        )
        self.assertEqual(
            [
                {
                    "ip_address": discovered_ip,
                    "subnet": serialize_subnet(dhcp_subnet),
                },
            ],
            parsed_interface["discovered"],
        )

    def test_read_effective_mtu(self):
        node = factory.make_Node()
        bond, parents, children = make_complex_interface(node)
        bond.params = {"mtu": 1000}
        bond.save()
        children[0].params = {"mtu": 2000}
        children[0].save()

        uri = get_interface_uri(bond)
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_interface = json_load_bytes(response.content)

        self.assertEqual(bond.id, parsed_interface["id"])
        self.assertEqual(2000, parsed_interface["effective_mtu"])

    def test_read_by_specifier(self):
        node = factory.make_Node(hostname="tasty-biscuits")
        bond0, _, _ = make_complex_interface(node, name="bond0")
        uri = get_interface_uri(
            "hostname:tasty-biscuits,name:bond0", node=node
        )
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_interface = json_load_bytes(response.content)
        self.assertEqual(bond0.id, parsed_interface["id"])

    def test_read_device_interface(self):
        parent = factory.make_Node()
        device = factory.make_Device(parent=parent)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=device
        )
        uri = get_interface_uri(interface)
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_interface = json_load_bytes(response.content)
        self.assertEqual(interface.id, parsed_interface["id"])

    def test_read_404_when_invalid_id(self):
        node = factory.make_Node()
        uri = reverse(
            "interface_handler",
            args=[node.system_id, random.randint(100, 1000)],
        )
        response = self.client.get(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_update_deployed_machine_interface(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        new_name = factory.make_name("name")
        new_mac = factory.make_mac_address()
        uri = get_interface_uri(interface)
        response = self.client.put(
            uri, {"name": new_name, "mac_address": new_mac}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_interface = json_load_bytes(response.content)
        self.assertEqual(new_name, parsed_interface["name"])
        self.assertEqual(new_mac, parsed_interface["mac_address"])

    def test_update_physical_interface(self):
        self.become_admin()
        for status in EDITABLE_STATUSES:
            node = factory.make_Node(status=status)
            interface = factory.make_Interface(
                INTERFACE_TYPE.PHYSICAL, node=node
            )
            new_name = factory.make_name("name")
            new_vlan = factory.make_VLAN()
            new_link_connected = True
            new_link_speed = random.randint(10, 1000)
            new_interface_speed = random.randint(new_link_speed, 1000)
            uri = get_interface_uri(interface)
            response = self.client.put(
                uri,
                {
                    "name": new_name,
                    "vlan": new_vlan.id,
                    "link_connected": new_link_connected,
                    "link_speed": new_link_speed,
                    "interface_speed": new_interface_speed,
                },
            )
            self.assertEqual(
                http.client.OK, response.status_code, response.content
            )
            parsed_interface = json_load_bytes(response.content)
            self.assertEqual(new_name, parsed_interface["name"])
            self.assertEqual(new_vlan.vid, parsed_interface["vlan"]["vid"])
            self.assertEqual(
                new_link_connected, parsed_interface["link_connected"]
            )
            self.assertEqual(new_link_speed, parsed_interface["link_speed"])
            self.assertEqual(
                new_interface_speed, parsed_interface["interface_speed"]
            )

    def test_update_device_physical_interface(self):
        node = factory.make_Node()
        device = factory.make_Device(owner=self.user, parent=node)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=device
        )
        new_name = factory.make_name("name")
        new_vlan = factory.make_VLAN()
        uri = get_interface_uri(interface)
        response = self.client.put(
            uri, {"name": new_name, "vlan": new_vlan.id}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_interface = json_load_bytes(response.content)
        self.assertEqual(new_name, parsed_interface["name"])
        self.assertEqual(new_vlan.vid, parsed_interface["vlan"]["vid"])

    def test_update_bond_interface(self):
        self.become_admin()
        for status in EDITABLE_STATUSES:
            node = factory.make_Node(status=status)
            bond, [nic_0, nic_1], [vlan_10, vlan_11] = make_complex_interface(
                node
            )
            uri = get_interface_uri(bond)
            response = self.client.put(uri, {"parents": [nic_0.id]})
            self.assertEqual(
                http.client.OK, response.status_code, response.content
            )
            parsed_interface = json_load_bytes(response.content)
            self.assertEqual([nic_0.name], parsed_interface["parents"])

    def test_update_vlan_interface(self):
        self.become_admin()
        for status in EDITABLE_STATUSES:
            node = factory.make_Node(status=status)
            bond, [nic_0, nic_1], [vlan_10, vlan_11] = make_complex_interface(
                node
            )
            physical_interface = factory.make_Interface(
                INTERFACE_TYPE.PHYSICAL, node=node, vlan=nic_0.vlan
            )
            uri = get_interface_uri(vlan_10)
            response = self.client.put(uri, {"parent": physical_interface.id})
            self.assertEqual(
                http.client.OK, response.status_code, response.content
            )
            parsed_interface = json_load_bytes(response.content)
            self.assertEqual(
                [physical_interface.name], parsed_interface["parents"]
            )

    def test_update_requires_admin(self):
        node = factory.make_Node()
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        new_name = factory.make_name("name")
        uri = get_interface_uri(interface)
        response = self.client.put(uri, {"name": new_name})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_update_409_when_not_ready_broken_or_deployed(self):
        self.become_admin()
        for status in BLOCKED_STATUSES:
            # Update is the only call that a deployed node can have called on
            # its interface.
            if status == NODE_STATUS.DEPLOYED:
                continue
            node = factory.make_Node(interface=True, status=status)
            interface = factory.make_Interface(
                INTERFACE_TYPE.PHYSICAL, node=node
            )
            new_name = factory.make_name("name")
            uri = get_interface_uri(interface)
            response = self.client.put(uri, {"name": new_name})
            self.assertEqual(
                http.client.CONFLICT, response.status_code, response.content
            )

    def test_delete_deletes_interface(self):
        self.become_admin()
        for status in EDITABLE_STATUSES:
            node = factory.make_Node(interface=True, status=status)
            interface = node.get_boot_interface()
            uri = get_interface_uri(interface)
            response = self.client.delete(uri)
            self.assertEqual(
                http.client.NO_CONTENT, response.status_code, response.content
            )
            self.assertIsNone(reload_object(interface))

    def test_delete_deletes_device_interface(self):
        parent = factory.make_Node()
        device = factory.make_Device(owner=self.user, parent=parent)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=device
        )
        uri = get_interface_uri(interface)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )
        self.assertIsNone(reload_object(interface))

    def test_delete_403_when_not_admin(self):
        node = factory.make_Node(interface=True)
        interface = node.get_boot_interface()
        uri = get_interface_uri(interface)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )
        self.assertIsNotNone(reload_object(interface))

    def test_delete_404_when_invalid_id(self):
        self.become_admin()
        node = factory.make_Node()
        uri = reverse(
            "interface_handler",
            args=[node.system_id, random.randint(100, 1000)],
        )
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_delete_409_when_invalid_status(self):
        self.become_admin()
        for status in BLOCKED_STATUSES:
            node = factory.make_Node(interface=True, status=status)
            interface = node.get_boot_interface()
            uri = get_interface_uri(interface)
            response = self.client.delete(uri)
            self.assertEqual(
                http.client.CONFLICT, response.status_code, response.content
            )

    def test_link_subnet_creates_link(self):
        # The form that is used is fully tested in test_forms_interface_link.
        # This just tests that the form is saved and the updated interface
        # is returned.
        self.become_admin()
        for status in EDITABLE_STATUSES:
            node = factory.make_Node(interface=True, status=status)
            interface = node.get_boot_interface()
            uri = get_interface_uri(interface)
            response = self.client.post(
                uri, {"op": "link_subnet", "mode": INTERFACE_LINK_TYPE.DHCP}
            )
            self.assertEqual(
                http.client.OK, response.status_code, response.content
            )
            parsed_response = json_load_bytes(response.content)
            self.assertThat(
                parsed_response["links"][0],
                ContainsDict({"mode": Equals(INTERFACE_LINK_TYPE.DHCP)}),
            )

    def test_link_subnet_creates_link_on_device(self):
        parent = factory.make_Node()
        device = factory.make_Device(owner=self.user, parent=parent)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=device
        )
        subnet = factory.make_Subnet(vlan=interface.vlan)
        uri = get_interface_uri(interface)
        response = self.client.post(
            uri,
            {
                "op": "link_subnet",
                "mode": INTERFACE_LINK_TYPE.STATIC,
                "subnet": subnet.id,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_response = json_load_bytes(response.content)
        self.assertThat(
            parsed_response["links"][0],
            ContainsDict({"mode": Equals(INTERFACE_LINK_TYPE.STATIC)}),
        )

    def test_link_subnet_allows_subnet_with_link_up(self):
        self.become_admin()
        node = factory.make_Node(
            owner=self.user, status=random.choice(EDITABLE_STATUSES)
        )
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        uri = get_interface_uri(interface)
        response = self.client.post(
            uri,
            {
                "op": "link_subnet",
                "mode": INTERFACE_LINK_TYPE.LINK_UP,
                "subnet": subnet.id,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_response = json_load_bytes(response.content)
        self.assertThat(
            parsed_response["links"][0],
            ContainsDict({"mode": Equals(INTERFACE_LINK_TYPE.LINK_UP)}),
        )
        self.assertEqual(
            subnet.id, parsed_response["links"][0]["subnet"]["id"]
        )

    def test_link_subnet_allows_link_up_subnet_to_be_cleared(self):
        self.become_admin()
        node = factory.make_Node(
            owner=self.user, status=random.choice(EDITABLE_STATUSES)
        )
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        uri = get_interface_uri(interface)
        self.client.post(
            uri,
            {
                "op": "link_subnet",
                "mode": INTERFACE_LINK_TYPE.LINK_UP,
                "subnet": subnet.id,
            },
        )
        response = self.client.post(
            uri, {"op": "link_subnet", "mode": INTERFACE_LINK_TYPE.LINK_UP}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_response = json_load_bytes(response.content)
        self.assertThat(
            parsed_response["links"][0],
            ContainsDict({"mode": Equals(INTERFACE_LINK_TYPE.LINK_UP)}),
        )
        self.assertNotIn("subnet", parsed_response["links"][0])

    def test_link_subnet_allows_link_up_subnet_to_be_changed(self):
        self.become_admin()
        node = factory.make_Node(
            owner=self.user, status=random.choice(EDITABLE_STATUSES)
        )
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        subnet2 = factory.make_Subnet(vlan=interface.vlan)
        uri = get_interface_uri(interface)
        self.client.post(
            uri,
            {
                "op": "link_subnet",
                "mode": INTERFACE_LINK_TYPE.LINK_UP,
                "subnet": subnet.id,
            },
        )
        response = self.client.post(
            uri,
            {
                "op": "link_subnet",
                "mode": INTERFACE_LINK_TYPE.LINK_UP,
                "subnet": subnet2.id,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_response = json_load_bytes(response.content)
        self.assertThat(
            parsed_response["links"][0],
            ContainsDict({"mode": Equals(INTERFACE_LINK_TYPE.LINK_UP)}),
        )
        self.assertEqual(
            subnet2.id, parsed_response["links"][0]["subnet"]["id"]
        )

    def test_link_subnet_disallows_subnets_on_another_vlan(self):
        self.become_admin()
        node = factory.make_Node(
            owner=self.user, status=random.choice(EDITABLE_STATUSES)
        )
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        vlan2 = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=interface.vlan)
        subnet2 = factory.make_Subnet(vlan=vlan2)
        uri = get_interface_uri(interface)
        self.client.post(
            uri,
            {
                "op": "link_subnet",
                "mode": INTERFACE_LINK_TYPE.LINK_UP,
                "subnet": subnet.id,
            },
        )
        response = self.client.post(
            uri,
            {
                "op": "link_subnet",
                "mode": INTERFACE_LINK_TYPE.LINK_UP,
                "subnet": subnet2.id,
            },
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_link_subnet_allows_link_up_subnet_to_be_forcibly_changed(self):
        self.become_admin()
        node = factory.make_Node(
            owner=self.user, status=random.choice(EDITABLE_STATUSES)
        )
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        vlan2 = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=interface.vlan)
        subnet2 = factory.make_Subnet(vlan=vlan2)
        uri = get_interface_uri(interface)
        self.client.post(
            uri,
            {
                "op": "link_subnet",
                "mode": INTERFACE_LINK_TYPE.LINK_UP,
                "subnet": subnet.id,
            },
        )
        response = self.client.post(
            uri,
            {
                "op": "link_subnet",
                "mode": INTERFACE_LINK_TYPE.LINK_UP,
                "force": "True",
                "subnet": subnet2.id,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_response = json_load_bytes(response.content)
        self.assertThat(
            parsed_response["links"][0],
            ContainsDict({"mode": Equals(INTERFACE_LINK_TYPE.LINK_UP)}),
        )
        self.assertEqual(
            subnet2.id, parsed_response["links"][0]["subnet"]["id"]
        )

    def test_link_subnet_force_link_up_deletes_existing_links(self):
        self.become_admin()
        node = factory.make_Node(
            owner=self.user, status=random.choice(EDITABLE_STATUSES)
        )
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        vlan2 = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=interface.vlan)
        subnet2 = factory.make_Subnet(vlan=vlan2)
        uri = get_interface_uri(interface)
        self.client.post(
            uri,
            {
                "op": "link_subnet",
                "mode": INTERFACE_LINK_TYPE.DHCP,
                "subnet": subnet.id,
            },
        )
        response = self.client.post(
            uri,
            {
                "op": "link_subnet",
                "mode": INTERFACE_LINK_TYPE.LINK_UP,
                "force": "True",
                "subnet": subnet2.id,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_response = json_load_bytes(response.content)
        self.assertThat(
            parsed_response["links"][0],
            ContainsDict({"mode": Equals(INTERFACE_LINK_TYPE.LINK_UP)}),
        )
        self.assertEqual(
            subnet2.id, parsed_response["links"][0]["subnet"]["id"]
        )

    def test_link_subnet_without_force_link_up_returns_bad_request(self):
        self.become_admin()
        node = factory.make_Node(
            owner=self.user, status=random.choice(EDITABLE_STATUSES)
        )
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        vlan2 = factory.make_VLAN()
        subnet = factory.make_Subnet(vlan=interface.vlan)
        subnet2 = factory.make_Subnet(vlan=vlan2)
        uri = get_interface_uri(interface)
        self.client.post(
            uri,
            {
                "op": "link_subnet",
                "mode": INTERFACE_LINK_TYPE.DHCP,
                "subnet": subnet.id,
            },
        )
        response = self.client.post(
            uri,
            {
                "op": "link_subnet",
                "mode": INTERFACE_LINK_TYPE.LINK_UP,
                "force": "False",
                "subnet": subnet2.id,
            },
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_link_subnet_on_device_only_allows_static(self):
        parent = factory.make_Node()
        device = factory.make_Device(owner=self.user, parent=parent)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=device
        )
        for link_type in [
            INTERFACE_LINK_TYPE.AUTO,
            INTERFACE_LINK_TYPE.DHCP,
            INTERFACE_LINK_TYPE.LINK_UP,
        ]:
            uri = get_interface_uri(interface)
            response = self.client.post(
                uri, {"op": "link_subnet", "mode": link_type}
            )
            self.assertEqual(
                http.client.BAD_REQUEST, response.status_code, response.content
            )

    def test_link_subnet_raises_error(self):
        self.become_admin()
        for status in EDITABLE_STATUSES:
            node = factory.make_Node(interface=True, status=status)
            interface = node.get_boot_interface()
            uri = get_interface_uri(interface)
            response = self.client.post(uri, {"op": "link_subnet"})
            self.assertEqual(
                http.client.BAD_REQUEST, response.status_code, response.content
            )
            self.assertEqual(
                {"mode": ["This field is required."]},
                json_load_bytes(response.content),
            )

    def test_link_subnet_requries_admin(self):
        node = factory.make_Node(interface=True)
        interface = node.get_boot_interface()
        uri = get_interface_uri(interface)
        response = self.client.post(uri, {"op": "link_subnet"})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_link_subnet_409_when_invalid_status(self):
        self.become_admin()
        for status in BLOCKED_STATUSES:
            node = factory.make_Node(interface=True, status=status)
            interface = node.get_boot_interface()
            uri = get_interface_uri(interface)
            response = self.client.post(
                uri, {"op": "link_subnet", "mode": INTERFACE_LINK_TYPE.DHCP}
            )
            self.assertEqual(
                http.client.CONFLICT, response.status_code, response.content
            )

    def test_unlink_subnet_deletes_link(self):
        # The form that is used is fully tested in test_forms_interface_link.
        # This just tests that the form is saved and the updated interface
        # is returned.
        self.become_admin()
        for status in EDITABLE_STATUSES:
            node = factory.make_Node(interface=True, status=status)
            interface = node.get_boot_interface()
            subnet = factory.make_Subnet()
            dhcp_ip = factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.DHCP,
                ip="",
                subnet=subnet,
                interface=interface,
            )
            uri = get_interface_uri(interface)
            response = self.client.post(
                uri, {"op": "unlink_subnet", "id": dhcp_ip.id}
            )
            self.assertEqual(
                http.client.OK, response.status_code, response.content
            )
            self.assertIsNone(reload_object(dhcp_ip))

    def test_unlink_subnet_deletes_link_on_device(self):
        parent = factory.make_Node()
        device = factory.make_Device(owner=self.user, parent=parent)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=device
        )
        subnet = factory.make_Subnet()
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=subnet,
            interface=interface,
        )
        uri = get_interface_uri(interface)
        response = self.client.post(
            uri, {"op": "unlink_subnet", "id": static_ip.id}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertIsNone(reload_object(static_ip))

    def test_unlink_subnet_raises_error(self):
        self.become_admin()
        for status in EDITABLE_STATUSES:
            node = factory.make_Node(interface=True, status=status)
            interface = node.get_boot_interface()
            uri = get_interface_uri(interface)
            response = self.client.post(uri, {"op": "unlink_subnet"})
            self.assertEqual(
                http.client.BAD_REQUEST, response.status_code, response.content
            )
            self.assertEqual(
                {"id": ["This field is required."]},
                json_load_bytes(response.content),
            )

    def test_unlink_subnet_requries_admin(self):
        node = factory.make_Node(interface=True)
        interface = node.get_boot_interface()
        uri = get_interface_uri(interface)
        response = self.client.post(uri, {"op": "unlink_subnet"})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_unlink_subnet_409_when_invalid_status(self):
        self.become_admin()
        for status in BLOCKED_STATUSES:
            node = factory.make_Node(interface=True, status=status)
            interface = node.get_boot_interface()
            uri = get_interface_uri(interface)
            response = self.client.post(uri, {"op": "unlink_subnet"})
            self.assertEqual(
                http.client.CONFLICT, response.status_code, response.content
            )

    def test_disconnect_deletes_links_and_clears_vlan(self):
        # The form that is used is fully tested in test_forms_interface_link.
        # This just tests that the form is saved and the updated interface
        # is returned.
        self.become_admin()
        for status in EDITABLE_STATUSES:
            node = factory.make_Node(interface=True, status=status)
            interface = node.get_boot_interface()
            subnet = factory.make_Subnet()
            dhcp_ip = factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.DHCP,
                ip="",
                subnet=subnet,
                interface=interface,
            )
            uri = get_interface_uri(interface)
            response = self.client.post(uri, {"op": "disconnect"})
            self.assertEqual(
                http.client.OK, response.status_code, response.content
            )
            self.assertIsNone(reload_object(dhcp_ip))
            self.assertIsNone(reload_object(interface).vlan)

    def test_disconnect_requries_admin(self):
        node = factory.make_Node(interface=True)
        interface = node.get_boot_interface()
        uri = get_interface_uri(interface)
        response = self.client.post(uri, {"op": "disconnect"})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_disconnect_409_when_invalid_status(self):
        self.become_admin()
        for status in BLOCKED_STATUSES:
            node = factory.make_Node(interface=True, status=status)
            interface = node.get_boot_interface()
            uri = get_interface_uri(interface)
            response = self.client.post(uri, {"op": "disconnect"})
            self.assertEqual(
                http.client.CONFLICT, response.status_code, response.content
            )

    def test_set_default_gateway_sets_gateway_link_ipv4_on_node(self):
        # The form that is used is fully tested in test_forms_interface_link.
        # This just tests that the form is saved and the node link is created.
        self.become_admin()
        for status in EDITABLE_STATUSES:
            node = factory.make_Node(interface=True, status=status)
            interface = node.get_boot_interface()
            network = factory.make_ipv4_network()
            subnet = factory.make_Subnet(
                cidr=str(network.cidr), vlan=interface.vlan
            )
            link_ip = factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.AUTO,
                ip="",
                subnet=subnet,
                interface=interface,
            )
            uri = get_interface_uri(interface)
            response = self.client.post(
                uri, {"op": "set_default_gateway", "link_id": link_ip.id}
            )
            self.assertEqual(
                http.client.OK, response.status_code, response.content
            )
            self.assertEqual(link_ip, reload_object(node).gateway_link_ipv4)

    def test_set_default_gateway_sets_gateway_link_ipv6_on_node(self):
        # The form that is used is fully tested in test_forms_interface_link.
        # This just tests that the form is saved and the node link is created.
        self.become_admin()
        for status in EDITABLE_STATUSES:
            node = factory.make_Node(interface=True, status=status)
            interface = node.get_boot_interface()
            network = factory.make_ipv6_network()
            subnet = factory.make_Subnet(
                cidr=str(network.cidr), vlan=interface.vlan
            )
            link_ip = factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.AUTO,
                ip="",
                subnet=subnet,
                interface=interface,
            )
            uri = get_interface_uri(interface)
            response = self.client.post(
                uri, {"op": "set_default_gateway", "link_id": link_ip.id}
            )
            self.assertEqual(
                http.client.OK, response.status_code, response.content
            )
            self.assertEqual(link_ip, reload_object(node).gateway_link_ipv6)

    def test_set_default_gateway_raises_error(self):
        self.become_admin()
        for status in EDITABLE_STATUSES:
            node = factory.make_Node(interface=True, status=status)
            interface = node.get_boot_interface()
            uri = get_interface_uri(interface)
            response = self.client.post(uri, {"op": "set_default_gateway"})
            self.assertEqual(
                http.client.BAD_REQUEST, response.status_code, response.content
            )
            self.assertEqual(
                {"__all__": ["This interface has no usable gateways."]},
                json_load_bytes(response.content),
            )

    def test_set_default_gateway_requries_admin(self):
        node = factory.make_Node(interface=True)
        interface = node.get_boot_interface()
        uri = get_interface_uri(interface)
        response = self.client.post(uri, {"op": "set_default_gateway"})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_set_default_gateway_409_when_invalid_status(self):
        self.become_admin()
        for status in BLOCKED_STATUSES:
            node = factory.make_Node(interface=True, status=status)
            interface = node.get_boot_interface()
            uri = get_interface_uri(interface)
            response = self.client.post(uri, {"op": "set_default_gateway"})
            self.assertEqual(
                http.client.CONFLICT, response.status_code, response.content
            )

    def test_add_tag_returns_403_when_not_admin(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        uri = get_interface_uri(interface)
        response = self.client.post(
            uri, {"op": "add_tag", "tag": factory.make_name("tag")}
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_add_tag_returns_404_when_system_id_doesnt_match(self):
        self.become_admin()
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        other_node = factory.make_Node()
        uri = get_interface_uri(interface, node=other_node)
        response = self.client.post(
            uri, {"op": "add_tag", "tag": factory.make_name("tag")}
        )
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_add_tag_to_interface(self):
        self.become_admin()
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        tag_to_be_added = factory.make_name("tag")
        uri = get_interface_uri(interface)
        response = self.client.post(
            uri, {"op": "add_tag", "tag": tag_to_be_added}
        )

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json_load_bytes(response.content)
        self.assertIn(tag_to_be_added, parsed_device["tags"])
        interface = reload_object(interface)
        self.assertIn(tag_to_be_added, interface.tags)

    def test_remove_tag_returns_403_when_not_admin(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        uri = get_interface_uri(interface)
        response = self.client.post(
            uri, {"op": "remove_tag", "tag": factory.make_name("tag")}
        )

        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_remove_tag_returns_404_when_system_id_doesnt_match(self):
        self.become_admin()
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        other_node = factory.make_Node()
        uri = get_interface_uri(interface, node=other_node)
        response = self.client.post(
            uri, {"op": "remove_tag", "tag": factory.make_name("tag")}
        )

        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_remove_tag_from_block_device(self):
        self.become_admin()
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        tag_to_be_removed = interface.tags[0]
        uri = get_interface_uri(interface)
        response = self.client.post(
            uri, {"op": "remove_tag", "tag": tag_to_be_removed}
        )

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_device = json_load_bytes(response.content)
        self.assertNotIn(tag_to_be_removed, parsed_device["tags"])
        interface = reload_object(interface)
        self.assertNotIn(tag_to_be_removed, interface.tags)


class TestInterfaceAPIForControllers(APITestCase.ForUser):
    scenarios = (
        ("region", {"maker": factory.make_RegionController}),
        ("rack", {"maker": factory.make_RackController}),
        ("region-rack", {"maker": factory.make_RegionRackController}),
    )

    def test_read(self):
        node = self.maker()
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)

        # First link is a DHCP link.
        links = []
        dhcp_subnet = factory.make_Subnet()
        dhcp_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DHCP,
            ip="",
            subnet=dhcp_subnet,
            interface=interface,
        )
        discovered_ip = factory.pick_ip_in_network(dhcp_subnet.get_ipnetwork())
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
            ip=discovered_ip,
            subnet=dhcp_subnet,
            interface=interface,
        )
        links.append(
            MatchesDict(
                {
                    "id": Equals(dhcp_ip.id),
                    "mode": Equals(INTERFACE_LINK_TYPE.DHCP),
                    "subnet": ContainsDict({"id": Equals(dhcp_subnet.id)}),
                    "ip_address": Equals(discovered_ip),
                }
            )
        )

        # Second link is a STATIC ip link.
        static_subnet = factory.make_Subnet()
        static_ip = factory.pick_ip_in_network(static_subnet.get_ipnetwork())
        sip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=static_ip,
            subnet=static_subnet,
            interface=interface,
        )
        links.append(
            MatchesDict(
                {
                    "id": Equals(sip.id),
                    "mode": Equals(INTERFACE_LINK_TYPE.STATIC),
                    "ip_address": Equals(static_ip),
                    "subnet": ContainsDict({"id": Equals(static_subnet.id)}),
                }
            )
        )

        # Third link is just a LINK_UP. In reality this cannot exist while the
        # other two links exist but for testing we allow it. If validation of
        # the StaticIPAddress model ever included this check, which it
        # probably should then this will fail and cause this test to break.
        link_subnet = factory.make_Subnet()
        link_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip="",
            subnet=link_subnet,
            interface=interface,
        )
        links.append(
            MatchesDict(
                {
                    "id": Equals(link_ip.id),
                    "mode": Equals(INTERFACE_LINK_TYPE.LINK_UP),
                    "subnet": ContainsDict({"id": Equals(link_subnet.id)}),
                }
            )
        )

        # Add MTU parameter.
        interface.params = {"mtu": random.randint(800, 2000)}
        interface.save()

        uri = get_interface_uri(interface)
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_interface = json_load_bytes(response.content)
        self.assertThat(
            parsed_interface,
            ContainsDict(
                {
                    "id": Equals(interface.id),
                    "name": Equals(interface.name),
                    "type": Equals(interface.type),
                    "vlan": ContainsDict({"id": Equals(interface.vlan.id)}),
                    "mac_address": Equals(str(interface.mac_address)),
                    "tags": Equals(interface.tags),
                    "resource_uri": Equals(get_interface_uri(interface)),
                    "params": Equals(interface.params),
                    "effective_mtu": Equals(interface.get_effective_mtu()),
                    "numa_node": Equals(0),
                }
            ),
        )
        self.assertThat(parsed_interface["links"], MatchesSetwise(*links))
        json_discovered = parsed_interface["discovered"][0]
        self.assertEqual(dhcp_subnet.id, json_discovered["subnet"]["id"])
        self.assertEqual(discovered_ip, json_discovered["ip_address"])

    def test_update(self):
        self.become_admin()
        node = self.maker()
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)

        new_fabric = factory.make_Fabric()
        new_vlan = new_fabric.get_default_vlan()
        uri = get_interface_uri(interface)
        response = self.client.put(uri, {"vlan": new_vlan.id})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_interface = json_load_bytes(response.content)
        self.assertEqual(new_vlan.id, parsed_interface["vlan"]["id"])

    def test_update_only_works_for_vlan_field(self):
        self.become_admin()
        node = self.maker()
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)

        new_name = factory.make_name("name")
        new_fabric = factory.make_Fabric()
        new_vlan = new_fabric.get_default_vlan()
        uri = get_interface_uri(interface)
        response = self.client.put(
            uri, {"name": new_name, "vlan": new_vlan.id}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_interface = json_load_bytes(response.content)
        self.assertEqual(new_vlan.id, parsed_interface["vlan"]["id"])
        self.assertEqual(interface.name, parsed_interface["name"])

    def test_update_forbidden_for_vlan_interface(self):
        self.become_admin()
        node = self.maker()
        parent = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        vlan_interface = factory.make_Interface(
            INTERFACE_TYPE.VLAN, parents=[parent]
        )

        new_vlan = factory.make_VLAN()
        uri = get_interface_uri(vlan_interface)
        response = self.client.put(uri, {"vlan": new_vlan.id})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_delete_is_forbidden(self):
        self.become_admin()
        node = self.maker()
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        uri = get_interface_uri(interface)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_link_subnet_is_forbidden(self):
        self.become_admin()
        node = self.maker()
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        uri = get_interface_uri(interface)
        response = self.client.post(
            uri, {"op": "link_subnet", "mode": INTERFACE_LINK_TYPE.DHCP}
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_unlink_subnet_is_forbidden(self):
        self.become_admin()
        node = self.maker()
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        subnet = factory.make_Subnet()
        dhcp_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DHCP,
            ip="",
            subnet=subnet,
            interface=interface,
        )
        uri = get_interface_uri(interface)
        response = self.client.post(
            uri, {"op": "unlink_subnet", "id": dhcp_ip.id}
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )
        self.assertIsNotNone(reload_object(dhcp_ip))
