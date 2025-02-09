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
    HandlerPermissionError,
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
        user = factory.make_admin()
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        handler = ReservedIPHandler(user, {}, None)
        reserved_ip = handler.create(
            {
                "ip": "10.0.0.55",
                "subnet": subnet.id,
                "mac_address": "00:11:22:33:44:55",
                "comment": "this is a comment",
            }
        )

        assert reserved_ip["ip"] == "10.0.0.55"
        assert reserved_ip["subnet"] == subnet.id
        assert reserved_ip["mac_address"] == "00:11:22:33:44:55"
        assert reserved_ip["comment"] == "this is a comment"

        reservedip_module.post_commit_do.assert_called_once_with(
            configure_dhcp_on_agents, reserved_ip_ids=[reserved_ip["id"]]
        )

    def test_create_mandatory_fields(self):
        user = factory.make_admin()
        handler = ReservedIPHandler(user, {}, None)

        # - IP must be provided, and subnet and VLAN must exist for the given IP
        with pytest.raises(HandlerValidationError) as exc_info:
            handler.create({})
        self.assertEqual(
            exc_info.value.message_dict,
            {
                "ip": ["This field is required."],
                "mac_address": ["This field cannot be blank."],
            },
        )
        reservedip_module.post_commit_do.assert_not_called()

    def test_create_invalid_mac(self):
        user = factory.make_admin()
        factory.make_Subnet(cidr="10.0.0.0/24")
        handler = ReservedIPHandler(user, {}, None)

        # - IP must be provided, and subnet and VLAN must exist for the given IP
        with pytest.raises(HandlerValidationError) as exc_info:
            handler.create({"ip": "10.0.0.155", "mac_address": "abcde"})
        self.assertEqual(
            exc_info.value.message_dict,
            {"mac_address": ["'abcde' is not a valid MAC address."]},
        )
        reservedip_module.post_commit_do.assert_not_called()

    def test_create_duplicate(self):
        user = factory.make_admin()
        factory.make_Subnet(cidr="10.0.0.0/24")
        handler = ReservedIPHandler(user, {}, None)

        # - IP cannot be already a reserved IP
        handler.create({"ip": "10.0.0.55", "mac_address": "00:11:22:33:44:55"})
        reservedip_module.post_commit_do.assert_called_once()
        reservedip_module.post_commit_do.reset_mock()

        with pytest.raises(Exception) as exc_info:
            handler.create(
                {"ip": "10.0.0.55", "mac_address": "00:11:22:33:44:56"}
            )
        self.assertEqual(
            exc_info.value.message_dict,
            {"ip": ["Reserved IP with this IP address already exists."]},
        )
        reservedip_module.post_commit_do.assert_not_called()

        with pytest.raises(Exception) as exc_info:
            handler.create(
                {"ip": "10.0.0.56", "mac_address": "00:11:22:33:44:55"}
            )
        self.assertEqual(
            exc_info.value.message_dict,
            {
                "__all__": [
                    "Reserved IP with this MAC address and Subnet already exists."
                ]
            },
        )
        reservedip_module.post_commit_do.assert_not_called()

    def test_create_requires_admin(self):
        user = factory.make_User()
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        handler = ReservedIPHandler(user, {}, None)

        create_data = {
            "ip": "10.0.0.55",
            "subnet": subnet.id,
            "mac_address": "00:11:22:33:44:55",
            "comment": "this is a comment",
        }

        self.assertRaises(HandlerPermissionError, handler.create, create_data)

    def test_get(self):
        admin = factory.make_admin()
        admin_handler = ReservedIPHandler(admin, {}, None)

        user = factory.make_User()
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        handler = ReservedIPHandler(user, {}, None)
        reserved_ip_id = admin_handler.create(
            {"ip": "10.0.0.16", "mac_address": "00:11:22:33:44:55"}
        )["id"]

        reserved_ip = handler.get({"id": reserved_ip_id})

        self.assertEqual(reserved_ip["subnet"], subnet.id)
        self.assertEqual(reserved_ip["ip"], "10.0.0.16")
        self.assertEqual(reserved_ip["mac_address"], "00:11:22:33:44:55")
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
        user = factory.make_admin()
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        handler = ReservedIPHandler(user, {}, None)
        reserved_ip_id = handler.create(
            {"ip": "10.0.0.16", "mac_address": "00:11:22:33:44:55"}
        )["id"]
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

        reservedip_module.post_commit_do.assert_not_called()

    def test_update_requires_admin(self):
        user = factory.make_User()
        handler = ReservedIPHandler(user, {}, None)

        update_data = {
            "id": "10.0.0.16",
            "mac_address": "00:11:22:33:44:55",
            "comment": "test update",
        }

        self.assertRaises(HandlerPermissionError, handler.update, update_data)

    def test_delete(self):
        user = factory.make_admin()
        factory.make_Subnet(cidr="10.0.0.0/24")
        handler = ReservedIPHandler(user, {}, None)
        reserved_ip = handler.create(
            {"ip": "10.0.0.16", "mac_address": "00:11:22:33:44:55"}
        )
        self.assertEqual(len(ReservedIP.objects.all()), 1)
        reservedip_module.post_commit_do.assert_called_once()
        reservedip_module.post_commit_do.reset_mock()

        handler.delete({"id": reserved_ip["id"]})

        self.assertEqual(len(ReservedIP.objects.all()), 0)

        reservedip_module.post_commit_do.assert_called_once_with(
            configure_dhcp_on_agents, subnet_ids=[reserved_ip["subnet"]]
        )

    def test_delete_with_invalid_params(self):
        user = factory.make_admin()
        factory.make_Subnet(cidr="10.0.0.0/24")
        handler = ReservedIPHandler(user, {}, None)
        reserved_ip_id = handler.create(
            {"ip": "10.0.0.16", "mac_address": "00:11:22:33:44:55"}
        )["id"]
        reservedip_module.post_commit_do.reset_mock()
        invalid_reserved_ip_id = reserved_ip_id + 1

        with pytest.raises(HandlerDoesNotExistError) as exc_info:
            handler.delete({"id": invalid_reserved_ip_id})

        self.assertEqual(
            str(exc_info.value),
            f"Object with id ({invalid_reserved_ip_id}) does not exist",
        )
        reservedip_module.post_commit_do.assert_not_called()

    def test_delete_requires_admin(self):
        user = factory.make_User()
        handler = ReservedIPHandler(user, {}, None)

        delete_data = {
            "id": 1,
        }

        self.assertRaises(HandlerPermissionError, handler.delete, delete_data)

    def test_list(self):
        admin = factory.make_admin()
        admin_handler = ReservedIPHandler(admin, {}, None)

        user = factory.make_User()
        factory.make_Subnet(cidr="10.0.0.0/24")
        handler = ReservedIPHandler(user, {}, None)

        reserved_ips = handler.list({})
        self.assertEqual(len(reserved_ips), 0)

        admin_handler.create(
            {"ip": "10.0.0.16", "mac_address": "00:11:22:33:44:55"}
        )
        admin_handler.create(
            {"ip": "10.0.0.25", "mac_address": "00:11:22:33:44:56"}
        )
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
        self.assertEqual(num_queries, 5)
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
