# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests the ReservedIP WebSocket handler"""

import pytest
from twisted.internet import defer

from maasserver.dhcp import configure_dhcp_on_agents
from maasserver.models.reservedip import ReservedIP
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.base import (
    HandlerDoesNotExistError,
    HandlerValidationError,
)
import maasserver.websockets.handlers.reservedip as reservedip_module
from maasserver.websockets.handlers.reservedip import ReservedIPHandler
from maastesting.djangotestcase import count_queries


class TestReservedIPHandler(MAASServerTestCase):

    def setUp(self):
        super().setUp()
        d = defer.succeed(None)
        self.patch(reservedip_module, "post_commit_do").return_value = d

    def test_create(self):
        user = factory.make_User()
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        vlan = subnet.vlan
        handler = ReservedIPHandler(user, {}, None)
        reserved_ip = handler.create(
            {
                "ip": "10.0.0.55",
                "subnet": subnet.id,
                "vlan": vlan.id,
                "mac_address": "00:11:22:33:44:55",
                "comment": "this is a comment",
            }
        )

        assert reserved_ip["ip"] == "10.0.0.55"
        assert reserved_ip["subnet"] == subnet.id
        assert reserved_ip["vlan"] == vlan.id
        assert reserved_ip["mac_address"] == "00:11:22:33:44:55"
        assert reserved_ip["comment"] == "this is a comment"

        reservedip_module.post_commit_do.assert_called_once_with(
            configure_dhcp_on_agents, reserved_ip_ids=[reserved_ip["id"]]
        )

    def test_create_with_invalid_params(self):
        """Creating a reserved IP fails if:"""
        user = factory.make_User()
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        handler = ReservedIPHandler(user, {}, None)

        # - IP must be provided, and subnet and VLAN must exist for the given IP
        with pytest.raises(HandlerValidationError) as exc_info:
            handler.create({})
        self.assertEqual(
            exc_info.value.message_dict,
            {
                "ip": [
                    "This field is required.",
                    "This field cannot be null.",
                ],
                "subnet": [
                    "This field is required.",
                    "This field cannot be null.",
                ],
                "vlan": [
                    "This field is required.",
                    "This field cannot be null.",
                ],
            },
        )
        reservedip_module.post_commit_do.assert_not_called()

        # - MAC address must be valid
        with pytest.raises(Exception) as exc_info:
            handler.create({"ip": "10.0.0.155", "mac_address": "abcde"})
        self.assertEqual(
            exc_info.value.message_dict,
            {"mac_address": ["'abcde' is not a valid MAC address."]},
        )
        reservedip_module.post_commit_do.assert_not_called()

        # - IP cannot be already a reserved IP
        handler.create({"ip": "10.0.0.55", "mac_address": "00:11:22:33:44:55"})
        reservedip_module.post_commit_do.assert_called_once()
        reservedip_module.post_commit_do.reset_mock()

        with pytest.raises(Exception) as exc_info:
            handler.create({"ip": "10.0.0.55"})
        self.assertEqual(
            exc_info.value.message_dict,
            {"ip": ["Reserved IP with this IP address already exists."]},
        )
        reservedip_module.post_commit_do.assert_not_called()

        # - MAC address cannot appear more than once in the same VLAN
        with pytest.raises(Exception) as exc_info:
            handler.create(
                {"ip": "10.0.0.56", "mac_address": "00:11:22:33:44:55"}
            )
        self.assertEqual(
            exc_info.value.message_dict,
            {
                "__all__": [
                    "Reserved IP with this MAC address and VLAN already exists."
                ]
            },
        )
        reservedip_module.post_commit_do.assert_not_called()

        # - MAC address can appear more than once if it is reserved in different VLANs
        factory.make_Subnet(cidr="192.168.0.0/24")
        handler.create(
            {"ip": "192.168.0.15", "mac_address": "00:11:22:33:44:55"}
        )
        reservedip_module.post_commit_do.assert_called_once()
        reservedip_module.post_commit_do.reset_mock()

        # - IP must be part of a registered subnet
        with pytest.raises(Exception) as exc_info:
            handler.create({"ip": "10.0.10.56", "subnet": subnet.id})
        self.assertEqual(
            exc_info.value.message_dict,
            {"ip": ["The provided IP is not part of the subnet."]},
        )
        reservedip_module.post_commit_do.assert_not_called()

        # - IP cannot be the broadcast address
        with pytest.raises(Exception) as exc_info:
            handler.create({"ip": "10.0.0.255", "subnet": subnet.id})
        self.assertEqual(
            exc_info.value.message_dict,
            {"ip": ["The broadcast address cannot be a reserved IP."]},
        )
        reservedip_module.post_commit_do.assert_not_called()

        # - IP cannot be the network address
        with pytest.raises(Exception) as exc_info:
            handler.create({"ip": "10.0.0.0", "subnet": subnet.id})
        self.assertEqual(
            exc_info.value.message_dict,
            {"ip": ["The network address cannot be a reserved IP."]},
        )
        reservedip_module.post_commit_do.assert_not_called()

        # - IP cannot be an anycast address (IPv6)
        factory.make_Subnet(cidr="2001::/64")
        with pytest.raises(Exception) as exc_info:
            handler.create({"ip": "2001::"})
        self.assertEqual(
            exc_info.value.message_dict,
            {"ip": ["The network address cannot be a reserved IP."]},
        )
        reservedip_module.post_commit_do.assert_not_called()

    def test_get(self):
        user = factory.make_User()
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        handler = ReservedIPHandler(user, {}, None)
        reserved_ip_id = handler.create({"ip": "10.0.0.16"})["id"]

        reserved_ip = handler.get({"id": reserved_ip_id})

        self.assertEqual(reserved_ip["subnet"], subnet.id)
        self.assertEqual(reserved_ip["ip"], "10.0.0.16")
        self.assertEqual(reserved_ip["mac_address"], None)
        self.assertEqual(reserved_ip["comment"], "")
        self.assertTrue("node_summary" not in reserved_ip)

    def test_get_with_invalid_params(self):
        """Getting a reserved IP fails if:"""
        user = factory.make_User()
        handler = ReservedIPHandler(user, {}, None)

        # - given ID must exist
        with pytest.raises(HandlerDoesNotExistError) as exc_info:
            handler.get({"id": 1})

        self.assertEqual(
            str(exc_info.value),
            "Object with id (1) does not exist",
        )

    def test_update(self):
        user = factory.make_User()
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        handler = ReservedIPHandler(user, {}, None)
        reserved_ip_id = handler.create({"ip": "10.0.0.16"})["id"]
        reservedip_module.post_commit_do.reset_mock()

        handler.update(
            {
                "id": reserved_ip_id,
                "mac_address": "00:11:22:33:44:55",
                "comment": "test update",
            }
        )

        reserved_ip = handler.get({"id": reserved_ip_id})
        self.assertEqual(reserved_ip["ip"], "10.0.0.16")
        self.assertEqual(reserved_ip["subnet"], subnet.id)
        self.assertEqual(reserved_ip["mac_address"], "00:11:22:33:44:55")
        self.assertEqual(reserved_ip["comment"], "test update")

        reservedip_module.post_commit_do.assert_called_once_with(
            configure_dhcp_on_agents, subnet_ids=[reserved_ip["subnet"]]
        )

    def test_update_with_invalid_params(self):
        """Updating a reserved IP fails if:"""
        user = factory.make_User()
        factory.make_Subnet(cidr="10.0.0.0/24")
        subnet = factory.make_Subnet(cidr="10.1.0.0/24")

        handler = ReservedIPHandler(user, {}, None)
        handler.create({"ip": "10.0.0.10", "mac_address": "00:11:22:33:44:55"})
        reserved_ip_id = handler.create({"ip": "10.0.0.16"})["id"]
        reservedip_module.post_commit_do.reset_mock()

        # - the IP of a reserved IP cannot be changed
        with pytest.raises(HandlerValidationError) as exc_info:
            handler.update({"id": reserved_ip_id, "ip": "10.0.0.20"})
        self.assertEqual(
            exc_info.value.message_dict,
            {"ip": ["Field cannot be changed."]},
        )
        reservedip_module.post_commit_do.assert_not_called()

        # - the subnet of a reserved IP cannot be changed
        with pytest.raises(HandlerValidationError) as exc_info:
            handler.update({"id": reserved_ip_id, "subnet": subnet.id})
        self.assertEqual(
            exc_info.value.message_dict,
            {"subnet": ["Field cannot be changed."]},
        )
        reservedip_module.post_commit_do.assert_not_called()

        # - the vlan of a reserved IP cannot be changed
        with pytest.raises(HandlerValidationError) as exc_info:
            handler.update({"id": reserved_ip_id, "vlan": subnet.vlan.id})
        self.assertEqual(
            exc_info.value.message_dict,
            {"vlan": ["Field cannot be changed."]},
        )
        reservedip_module.post_commit_do.assert_not_called()

        # - there is already an entry with the same MAC address in the same VLAN
        with pytest.raises(HandlerValidationError) as exc_info:
            handler.update(
                {"id": reserved_ip_id, "mac_address": "00:11:22:33:44:55"}
            )
        self.assertEqual(
            exc_info.value.message_dict,
            {
                "__all__": [
                    "Reserved IP with this MAC address and VLAN already exists."
                ]
            },
        )
        reservedip_module.post_commit_do.assert_not_called()

        # - MAC address can appear more than once if it is reserved in different VLANs
        reserved_ip_id_vlan_10_1_0_0 = handler.create(
            {"ip": "10.1.0.10", "subnet": subnet.id}
        )
        reservedip_module.post_commit_do.reset_mock()
        handler.update(
            {
                "id": reserved_ip_id_vlan_10_1_0_0["id"],
                "mac_address": "00:11:22:33:44:55",
            }
        )
        reservedip_module.post_commit_do.assert_called_once()

    def test_delete(self):
        user = factory.make_User()
        factory.make_Subnet(cidr="10.0.0.0/24")
        handler = ReservedIPHandler(user, {}, None)
        reserved_ip = handler.create({"ip": "10.0.0.16"})
        self.assertEqual(len(ReservedIP.objects.all()), 1)
        reservedip_module.post_commit_do.assert_called_once()
        reservedip_module.post_commit_do.reset_mock()

        handler.delete({"id": reserved_ip["id"]})

        self.assertEqual(len(ReservedIP.objects.all()), 0)

        reservedip_module.post_commit_do.assert_called_once_with(
            configure_dhcp_on_agents, subnet_ids=[reserved_ip["subnet"]]
        )

    def test_delete_with_invalid_params(self):
        user = factory.make_User()
        factory.make_Subnet(cidr="10.0.0.0/24")
        handler = ReservedIPHandler(user, {}, None)
        reserved_ip_id = handler.create({"ip": "10.0.0.16"})["id"]
        reservedip_module.post_commit_do.reset_mock()
        invalid_reserved_ip_id = reserved_ip_id + 1

        with pytest.raises(HandlerDoesNotExistError) as exc_info:
            handler.delete({"id": invalid_reserved_ip_id})

        self.assertEqual(
            str(exc_info.value),
            f"Object with id ({invalid_reserved_ip_id}) does not exist",
        )
        reservedip_module.post_commit_do.assert_not_called()

    def test_list(self):
        user = factory.make_User()
        factory.make_Subnet(cidr="10.0.0.0/24")
        handler = ReservedIPHandler(user, {}, None)

        reserved_ips = handler.list({})
        self.assertEqual(len(reserved_ips), 0)

        handler.create({"ip": "10.0.0.16"})
        handler.create({"ip": "10.0.0.25"})
        reserved_ips = handler.list({})
        self.assertEqual(len(reserved_ips), 2)
        self.assertEqual(
            sorted(r["ip"] for r in reserved_ips), ["10.0.0.16", "10.0.0.25"]
        )
        for rip in reserved_ips:
            self.assertEqual(None, rip["node_summary"])

    def test_list_with_node_summary(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        node = factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
        reservedip = factory.make_ReservedIP(
            ip="10.0.0.1",
            mac_address=node.boot_interface.mac_address,
            subnet=subnet,
        )
        user = factory.make_User()
        handler = ReservedIPHandler(user, {}, None)
        num_queries, reserved_ips = count_queries(handler.list, {})
        self.assertEqual(len(reserved_ips), 1)
        # 1 - get the list of reserved ips
        # 2 - get list of interfaces for all the mac addresses
        # 3 - get list of node configs
        # 4 - get list of nodes
        # 5 - get list of domains
        # 6 - get the vlan - to be removed soon
        self.assertEqual(num_queries, 6)
        self.assertEqual(
            [
                {
                    "id": reservedip.id,
                    "created": reservedip.created.strftime(
                        "%a, %d %b. %Y %H:%M:%S"
                    ),
                    "updated": reservedip.updated.strftime(
                        "%a, %d %b. %Y %H:%M:%S"
                    ),
                    "subnet": subnet.id,
                    "vlan": subnet.vlan.id,
                    "ip": reservedip.ip,
                    "mac_address": node.boot_interface.mac_address,
                    "comment": None,
                    "node_summary": {
                        "fqdn": node.fqdn,
                        "hostname": node.hostname,
                        "node_type": node.node_type,
                        "system_id": node.system_id,
                        "via": node.boot_interface.name,
                    },
                }
            ],
            reserved_ips,
        )
