# Copyright 2013-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the nodes API."""


import http.client
import json
import random

from django.conf import settings
from django.http import QueryDict
from django.urls import reverse

from maasserver.api import auth
from maasserver.api import nodes as nodes_module
from maasserver.api.utils import get_overridden_query_dict
from maasserver.enum import (
    INTERFACE_TYPE,
    NODE_STATUS,
    NODE_STATUS_CHOICES,
    NODE_TYPE,
    NODE_TYPE_CHOICES,
)
from maasserver.exceptions import MAASAPIValidationError
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.fixtures import RBACEnabled
from maasserver.utils.orm import reload_object


class TestIsRegisteredAnonAPI(APITestCase.ForAnonymousAndUserAndAdmin):
    def make_node(self, *args, **kwargs):
        if self.user.is_anonymous:
            but_not = [
                NODE_STATUS.NEW,
                NODE_STATUS.COMMISSIONING,
                NODE_STATUS.RETIRED,
            ]
        else:
            but_not = [NODE_STATUS.RETIRED]
        return factory.make_Node(
            status=factory.pick_choice(NODE_STATUS_CHOICES, but_not=but_not)
        )

    def test_is_registered_returns_True_if_node_registered(self):
        node = self.make_node()
        mac_address = factory.make_mac_address()
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, mac_address=mac_address, node=node
        )
        response = self.client.get(
            reverse("nodes_handler"),
            {"op": "is_registered", "mac_address": mac_address},
        )
        self.assertEqual(
            (http.client.OK.value, "true"),
            (
                response.status_code,
                response.content.decode(settings.DEFAULT_CHARSET),
            ),
        )

    def test_is_registered_normalizes_mac_address(self):
        node = self.make_node()
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            mac_address="aa:bb:cc:dd:ee:ff",
            node=node,
        )
        response = self.client.get(
            reverse("nodes_handler"),
            {"op": "is_registered", "mac_address": "aabbccddeeff"},
        )
        self.assertEqual(
            (http.client.OK.value, "true"),
            (
                response.status_code,
                response.content.decode(settings.DEFAULT_CHARSET),
            ),
        )

    def test_is_registered_returns_False_if_node_not_registered(self):
        mac_address = factory.make_mac_address()
        response = self.client.get(
            reverse("nodes_handler"),
            {"op": "is_registered", "mac_address": mac_address},
        )
        self.assertEqual(
            (http.client.OK.value, "false"),
            (
                response.status_code,
                response.content.decode(settings.DEFAULT_CHARSET),
            ),
        )

    def test_is_registered_returns_False_if_node_new_commis_retired(self):
        if self.user.is_anonymous:
            status = random.choice(
                [
                    NODE_STATUS.NEW,
                    NODE_STATUS.COMMISSIONING,
                    NODE_STATUS.RETIRED,
                ]
            )
        else:
            status = NODE_STATUS.RETIRED
        node = factory.make_Node(status=status)
        mac_address = factory.make_mac_address()
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, mac_address=mac_address, node=node
        )
        response = self.client.get(
            reverse("nodes_handler"),
            {"op": "is_registered", "mac_address": mac_address},
        )
        self.assertEqual(
            (http.client.OK.value, "false"),
            (
                response.status_code,
                response.content.decode(settings.DEFAULT_CHARSET),
            ),
        )

    def test_is_registered_returns_False_if_interface_has_no_node(self):
        interface = factory.make_Interface(INTERFACE_TYPE.UNKNOWN)
        response = self.client.get(
            reverse("nodes_handler"),
            {"op": "is_registered", "mac_address": str(interface.mac_address)},
        )
        self.assertEqual(
            (http.client.OK.value, "false"),
            (
                response.status_code,
                response.content.decode(settings.DEFAULT_CHARSET),
            ),
        )


class TestIsActionInProgressAPI(APITestCase.ForAnonymous):
    scenarios = (
        (
            "commissioning",
            {"status": NODE_STATUS.COMMISSIONING, "result": "true"},
        ),
        ("deploying", {"status": NODE_STATUS.DEPLOYING, "result": "true"}),
        ("deployed", {"status": NODE_STATUS.DEPLOYED, "result": "false"}),
        ("testing", {"status": NODE_STATUS.TESTING, "result": "false"}),
        ("ready", {"status": NODE_STATUS.READY, "result": "false"}),
    )

    def test_is_action_in_progress_returns_correct_result_per_state(self):
        mac_address = factory.make_mac_address()
        node = factory.make_Node(status=self.status)
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, mac_address=mac_address, node=node
        )
        response = self.client.get(
            reverse("nodes_handler"),
            {"op": "is_action_in_progress", "mac_address": mac_address},
        )
        self.assertEqual(
            (http.client.OK.value, self.result),
            (
                response.status_code,
                response.content.decode(settings.DEFAULT_CHARSET),
            ),
        )


def extract_system_ids(parsed_result):
    """List the system_ids of the nodes in `parsed_result`."""
    return [node.get("system_id") for node in parsed_result]


def extract_system_ids_from_nodes(nodes):
    return [node.system_id for node in nodes]


class RequestFixture:
    def __init__(self, dict, fields, user=None):
        if user is None:
            user = factory.make_User()
        self.user = user
        self.GET = get_overridden_query_dict(
            dict, QueryDict(mutable=True), fields
        )


class TestFilteredNodesListFromRequest(APITestCase.ForUser):
    def test_node_list_with_id_returns_matching_nodes(self):
        # The "list" operation takes optional "id" parameters.  Only
        # nodes with matching ids will be returned.
        ids = [factory.make_Node().system_id for _ in range(3)]
        matching_id = ids[0]
        query = RequestFixture({"id": [matching_id]}, "id")
        node_list = nodes_module.filtered_nodes_list_from_request(query)

        self.assertEqual(
            [matching_id], extract_system_ids_from_nodes(node_list)
        )

    def test_node_list_with_nonexistent_id_returns_empty_list(self):
        # Trying to list a nonexistent node id returns a list containing
        # no nodes -- even if other (non-matching) nodes exist.
        existing_id = factory.make_Node().system_id
        nonexistent_id = existing_id + factory.make_string()
        query = RequestFixture({"id": [nonexistent_id]}, "id")
        node_list = nodes_module.filtered_nodes_list_from_request(query)

        self.assertEqual([], extract_system_ids_from_nodes(node_list))

    def test_node_list_with_ids_orders_by_id(self):
        # Even when ids are passed to "list," nodes are returned in id
        # order, not necessarily in the order of the id arguments.
        all_nodes = [factory.make_Node() for _ in range(3)]
        system_ids = [node.system_id for node in all_nodes]
        random.shuffle(system_ids)

        query = RequestFixture({"id": list(system_ids)}, "id")
        node_list = nodes_module.filtered_nodes_list_from_request(query)

        sorted_system_ids = [
            node.system_id
            for node in sorted(all_nodes, key=lambda node: node.id)
        ]
        self.assertCountEqual(
            sorted_system_ids, extract_system_ids_from_nodes(node_list)
        )

    def test_node_list_with_some_matching_ids_returns_matching_nodes(self):
        # If some nodes match the requested ids and some don't, only the
        # matching ones are returned.
        existing_id = factory.make_Node().system_id
        nonexistent_id = existing_id + factory.make_string()

        query = RequestFixture({"id": [existing_id, nonexistent_id]}, "id")
        node_list = nodes_module.filtered_nodes_list_from_request(query)

        self.assertEqual(
            [existing_id], extract_system_ids_from_nodes(node_list)
        )

    def test_node_list_with_hostname_returns_matching_nodes(self):
        # The list operation takes optional "hostname" parameters. Only nodes
        # with matching hostnames will be returned.
        nodes = [factory.make_Node() for _ in range(3)]
        matching_hostname = nodes[0].hostname
        matching_system_id = nodes[0].system_id

        query = RequestFixture({"hostname": [matching_hostname]}, "hostname")
        node_list = nodes_module.filtered_nodes_list_from_request(query)

        self.assertEqual(
            [matching_system_id], extract_system_ids_from_nodes(node_list)
        )

    def test_node_list_with_macs_returns_matching_nodes(self):
        # The "list" operation takes optional "mac_address" parameters. Only
        # nodes with matching MAC addresses will be returned.
        interfaces = [
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL) for _ in range(3)
        ]
        matching_mac = str(interfaces[0].mac_address)
        matching_system_id = interfaces[0].node_config.node.system_id

        query = RequestFixture({"mac_address": [matching_mac]}, "mac_address")
        node_list = nodes_module.filtered_nodes_list_from_request(query)

        self.assertEqual(
            [matching_system_id], extract_system_ids_from_nodes(node_list)
        )

    def test_node_list_with_invalid_macs_returns_sensible_error(self):
        # If specifying an invalid MAC, make sure the error that's
        # returned is not a crazy stack trace, but something nice to
        # humans.
        bad_mac1 = "00:E0:81:DD:D1:ZZ"  # ZZ is bad.
        bad_mac2 = "00:E0:81:DD:D1:XX"  # XX is bad.
        ok_mac = str(
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL).mac_address
        )
        mac_list = [bad_mac1, bad_mac2, ok_mac]

        query = RequestFixture({"mac_address": mac_list}, "mac_address")
        expected_msg = [
            "Invalid MAC address(es): 00:E0:81:DD:D1:ZZ, 00:E0:81:DD:D1:XX"
        ]
        ex = self.assertRaises(
            MAASAPIValidationError,
            nodes_module.filtered_nodes_list_from_request,
            query,
        )
        self.assertEqual(expected_msg, ex.messages)

    def test_node_list_with_agent_name_filters_by_agent_name(self):
        factory.make_Node(agent_name=factory.make_name("other_agent_name"))
        agent_name = factory.make_name("agent-name")
        node = factory.make_Node(agent_name=agent_name)

        query = RequestFixture({"agent_name": agent_name}, "agent_name")
        node_list = nodes_module.filtered_nodes_list_from_request(query)

        self.assertSequenceEqual(
            [node.system_id], extract_system_ids_from_nodes(node_list)
        )

    def test_node_list_with_agent_name_filters_with_empty_string(self):
        factory.make_Node(agent_name=factory.make_name("agent-name"))
        node = factory.make_Node(agent_name="")

        query = RequestFixture({"agent_name": ""}, "agent_name")
        node_list = nodes_module.filtered_nodes_list_from_request(query)

        self.assertSequenceEqual(
            [node.system_id], extract_system_ids_from_nodes(node_list)
        )

    def test_node_list_without_agent_name_does_not_filter(self):
        nodes = [
            factory.make_Node(agent_name=factory.make_name("agent-name"))
            for _ in range(3)
        ]

        query = RequestFixture({}, "")
        node_list = nodes_module.filtered_nodes_list_from_request(query)

        self.assertSequenceEqual(
            [node.system_id for node in nodes],
            extract_system_ids_from_nodes(node_list),
        )

    def test_node_lists_list_devices(self):
        query = RequestFixture({}, "")

        machines = [
            factory.make_Node(agent_name=factory.make_name("agent-name"))
            for _ in range(3)
        ]
        # Create devices.
        devices = [factory.make_Device(owner=query.user) for _ in range(3)]

        node_list = nodes_module.filtered_nodes_list_from_request(query)

        system_ids = extract_system_ids_from_nodes(node_list)
        self.assertEqual(
            [node.system_id for node in machines + devices],
            system_ids,
            "Node listing doesn't contain devices.",
        )

    def test_node_list_with_zone_filters_by_zone(self):
        factory.make_Node(zone=factory.make_Zone(name="twilight"))
        zone = factory.make_Zone()
        node = factory.make_Node(zone=zone)

        query = RequestFixture({"zone": zone.name}, "zone")
        node_list = nodes_module.filtered_nodes_list_from_request(query)

        self.assertSequenceEqual(
            [node.system_id], extract_system_ids_from_nodes(node_list)
        )

    def test_node_list_without_zone_does_not_filter(self):
        nodes = [factory.make_Node(zone=factory.make_Zone()) for _ in range(3)]

        query = RequestFixture({}, "")
        node_list = nodes_module.filtered_nodes_list_from_request(query)

        self.assertSequenceEqual(
            [node.system_id for node in nodes],
            extract_system_ids_from_nodes(node_list),
        )

    def test_node_list_with_pool_filters_by_pool(self):
        pool1 = factory.make_ResourcePool()
        pool2 = factory.make_ResourcePool()
        node1 = factory.make_Node(pool=pool1)
        factory.make_Node(pool=pool2)

        query = RequestFixture({"pool": pool1.name}, "pool", self.user)
        node_list = nodes_module.filtered_nodes_list_from_request(query)

        self.assertSequenceEqual(
            [node1.system_id], extract_system_ids_from_nodes(node_list)
        )

    def test_node_list_without_pool_does_not_filter(self):
        nodes = [
            factory.make_Node(pool=factory.make_ResourcePool())
            for _ in range(3)
        ]

        query = RequestFixture({}, "", self.user)
        node_list = nodes_module.filtered_nodes_list_from_request(query)

        self.assertSequenceEqual(
            [node.system_id for node in nodes],
            extract_system_ids_from_nodes(node_list),
        )


class TestNodesAPI(APITestCase.ForUser):
    """Tests for /api/2.0/nodes/."""

    def test_handler_path(self):
        self.assertEqual("/MAAS/api/2.0/nodes/", reverse("nodes_handler"))

    def test_GET_lists_nodes(self):
        # The api allows for fetching the list of Nodes.
        node1 = factory.make_Node()
        node2 = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.user
        )
        response = self.client.get(reverse("nodes_handler"))
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertCountEqual(
            [node1.system_id, node2.system_id],
            extract_system_ids(parsed_result),
        )

    def test_GET_lists_nodes_admin(self):
        # Only admins can see controllers
        self.become_admin()
        system_ids = [
            factory.make_Node(
                node_type=node_type[0], owner=self.user
            ).system_id
            for node_type in NODE_TYPE_CHOICES
        ]
        response = self.client.get(reverse("nodes_handler"))
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertCountEqual(system_ids, extract_system_ids(parsed_result))

    def test_GET_without_nodes_returns_empty_list(self):
        # If there are no nodes to list, the "list" op still works but
        # returns an empty list.
        response = self.client.get(reverse("nodes_handler"))
        self.assertEqual(
            [], json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        )

    def test_GET_orders_by_id(self):
        # Nodes are returned in id order.
        nodes = [factory.make_Node() for counter in range(3)]
        response = self.client.get(reverse("nodes_handler"))
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertSequenceEqual(
            [node.system_id for node in nodes],
            extract_system_ids(parsed_result),
        )

    def test_GET_with_id_returns_matching_nodes(self):
        # The "list" operation takes optional "id" parameters.  Only
        # nodes with matching ids will be returned.
        ids = [factory.make_Node().system_id for counter in range(3)]
        matching_id = ids[0]
        response = self.client.get(
            reverse("nodes_handler"), {"id": [matching_id]}
        )
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual([matching_id], extract_system_ids(parsed_result))

    def test_GET_list_with_nonexistent_id_returns_empty_list(self):
        # Trying to list a nonexistent node id returns a list containing
        # no nodes -- even if other (non-matching) nodes exist.
        existing_id = factory.make_Node().system_id
        nonexistent_id = existing_id + factory.make_string()
        response = self.client.get(
            reverse("nodes_handler"), {"id": [nonexistent_id]}
        )
        self.assertEqual(
            [], json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        )

    def test_GET_with_ids_orders_by_id(self):
        # Even when ids are passed to "list," nodes are returned in id
        # order, not necessarily in the order of the id arguments.
        ids = [factory.make_Node().system_id for counter in range(3)]
        response = self.client.get(
            reverse("nodes_handler"), {"id": list(reversed(ids))}
        )
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertSequenceEqual(ids, extract_system_ids(parsed_result))

    def test_GET_with_some_matching_ids_returns_matching_nodes(self):
        # If some nodes match the requested ids and some don't, only the
        # matching ones are returned.
        existing_id = factory.make_Node().system_id
        nonexistent_id = existing_id + factory.make_string()
        response = self.client.get(
            reverse("nodes_handler"), {"id": [existing_id, nonexistent_id]}
        )
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual([existing_id], extract_system_ids(parsed_result))

    def test_GET_with_hostname_returns_matching_nodes(self):
        # The list operation takes optional "hostname" parameters. Only nodes
        # with matching hostnames will be returned.
        nodes = [factory.make_Node() for _ in range(3)]
        matching_hostname = nodes[0].hostname
        matching_system_id = nodes[0].system_id
        response = self.client.get(
            reverse("nodes_handler"), {"hostname": [matching_hostname]}
        )
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(
            [matching_system_id], extract_system_ids(parsed_result)
        )

    def test_GET_with_macs_returns_matching_nodes(self):
        # The "list" operation takes optional "mac_address" parameters. Only
        # nodes with matching MAC addresses will be returned.
        interfaces = [
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL) for _ in range(3)
        ]
        matching_mac = interfaces[0].mac_address
        matching_system_id = interfaces[0].node_config.node.system_id
        response = self.client.get(
            reverse("nodes_handler"), {"mac_address": [matching_mac]}
        )
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(
            [matching_system_id], extract_system_ids(parsed_result)
        )

    def test_GET_with_invalid_macs_returns_sensible_error(self):
        # If specifying an invalid MAC, make sure the error that's
        # returned is not a crazy stack trace, but something nice to
        # humans.
        bad_mac1 = "00:E0:81:DD:D1:ZZ"  # ZZ is bad.
        bad_mac2 = "00:E0:81:DD:D1:XX"  # XX is bad.
        ok_mac = str(
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL).mac_address
        )
        response = self.client.get(
            reverse("nodes_handler"),
            {"mac_address": [bad_mac1, bad_mac2, ok_mac]},
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(
            parsed_result,
            {
                "mac_address": [
                    "'00:E0:81:DD:D1:ZZ' is not a valid MAC address."
                ]
            },
        )

    def test_GET_with_agent_name_filters_by_agent_name(self):
        factory.make_Node(agent_name=factory.make_name("other_agent_name"))
        agent_name = factory.make_name("agent-name")
        node = factory.make_Node(agent_name=agent_name)
        response = self.client.get(
            reverse("nodes_handler"), {"agent_name": agent_name}
        )
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertSequenceEqual(
            [node.system_id], extract_system_ids(parsed_result)
        )

    def test_GET_with_agent_name_filters_with_empty_string(self):
        factory.make_Node(agent_name=factory.make_name("agent-name"))
        node = factory.make_Node(agent_name="")
        response = self.client.get(
            reverse("nodes_handler"), {"agent_name": ""}
        )
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertSequenceEqual(
            [node.system_id], extract_system_ids(parsed_result)
        )

    def test_GET_without_agent_name_does_not_filter(self):
        nodes = [
            factory.make_Node(agent_name=factory.make_name("agent-name"))
            for _ in range(3)
        ]
        response = self.client.get(reverse("nodes_handler"))
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertSequenceEqual(
            [node.system_id for node in nodes],
            extract_system_ids(parsed_result),
        )

    def test_GET_has_disable_ipv4(self):
        # The api allows for fetching the list of Nodes.
        factory.make_Node()
        factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=self.user)
        response = self.client.get(reverse("nodes_handler"))
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(http.client.OK, response.status_code)
        disable_ipv4 = [node.get("disable_ipv4") for node in parsed_result]
        self.assertEqual([False, False], disable_ipv4)

    def test_GET_shows_all_types(self):
        machines = [
            factory.make_Node(agent_name=factory.make_name("agent-name"))
            for _ in range(3)
        ]
        # Create devices.
        devices = [
            factory.make_Node(node_type=NODE_TYPE.DEVICE, owner=self.user)
            for _ in range(3)
        ]
        rack_controllers = [
            factory.make_Node(agent_name=factory.make_name("agent-name"))
            for _ in range(3)
        ]
        response = self.client.get(reverse("nodes_handler"))
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertCountEqual(
            [node.system_id for node in machines + devices + rack_controllers],
            extract_system_ids(parsed_result),
            "Node listing doesn't contain all node types.",
        )

    def test_GET_with_zone_filters_by_zone(self):
        factory.make_Node(zone=factory.make_Zone(name="twilight"))
        zone = factory.make_Zone()
        node = factory.make_Node(zone=zone)
        response = self.client.get(
            reverse("nodes_handler"), {"zone": zone.name}
        )
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertSequenceEqual(
            [node.system_id], extract_system_ids(parsed_result)
        )

    def test_GET_without_zone_does_not_filter(self):
        nodes = [factory.make_Node(zone=factory.make_Zone()) for _ in range(3)]
        response = self.client.get(reverse("nodes_handler"))
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertSequenceEqual(
            [node.system_id for node in nodes],
            extract_system_ids(parsed_result),
        )

    def test_POST_set_zone_sets_zone_on_nodes(self):
        self.become_admin()
        node = factory.make_Node()
        zone = factory.make_Zone()
        response = self.client.post(
            reverse("nodes_handler"),
            {"op": "set_zone", "nodes": [node.system_id], "zone": zone.name},
        )
        self.assertEqual(http.client.OK, response.status_code)
        node = reload_object(node)
        self.assertEqual(zone, node.zone)

    def test_POST_set_zone_does_not_affect_other_nodes(self):
        self.become_admin()
        node = factory.make_Node()
        original_zone = node.zone
        response = self.client.post(
            reverse("nodes_handler"),
            {
                "op": "set_zone",
                "nodes": [factory.make_Node().system_id],
                "zone": factory.make_Zone().name,
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        node = reload_object(node)
        self.assertEqual(original_zone, node.zone)

    def test_POST_set_zone_requires_admin(self):
        node = factory.make_Node(owner=self.user)
        original_zone = node.zone
        response = self.client.post(
            reverse("nodes_handler"),
            {
                "op": "set_zone",
                "nodes": [node.system_id],
                "zone": factory.make_Zone().name,
            },
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        node = reload_object(node)
        self.assertEqual(original_zone, node.zone)

    def test_POST_set_zone_rbac_pool_admin_allowed(self):
        self.patch(auth, "validate_user_external_auth").return_value = True
        rbac = self.useFixture(RBACEnabled())
        self.become_non_local()
        machine = factory.make_Machine()
        zone = factory.make_Zone()
        rbac.store.add_pool(machine.pool)
        rbac.store.allow(self.user.username, machine.pool, "admin-machines")
        rbac.store.allow(self.user.username, machine.pool, "view")
        response = self.client.post(
            reverse("nodes_handler"),
            {
                "op": "set_zone",
                "nodes": [machine.system_id],
                "zone": zone.name,
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        machine = reload_object(machine)
        self.assertEqual(zone, machine.zone)

    def test_CREATE_disabled(self):
        response = self.client.post(reverse("nodes_handler"), {})
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)

    def test_UPDATE_disabled(self):
        response = self.client.put(reverse("nodes_handler"), {})
        self.assertEqual(http.client.METHOD_NOT_ALLOWED, response.status_code)

    def test_DELETE_disabled(self):
        response = self.client.put(reverse("nodes_handler"), {})
        self.assertEqual(http.client.METHOD_NOT_ALLOWED, response.status_code)


class TestPowersMixin(APITestCase.ForUser):
    """Test the powers mixin."""

    def get_node_uri(self, node):
        """Get the API URI for `node`."""
        # Use the machine handler to test as that will always support all
        # power commands
        return reverse("machine_handler", args=[node.system_id])

    def test_GET_power_parameters_requires_admin(self):
        response = self.client.get(
            reverse("machines_handler"), {"op": "power_parameters"}
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_GET_power_parameters_without_ids_does_not_filter(self):
        self.become_admin()
        machines = [
            factory.make_Node(
                power_parameters={factory.make_string(): factory.make_string()}
            )
            for _ in range(0, 3)
        ]
        response = self.client.get(
            reverse("machines_handler"), {"op": "power_parameters"}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        expected = {
            machine.system_id: machine.get_power_parameters()
            for machine in machines
        }
        self.assertEqual(expected, parsed)

    def test_GET_power_parameters_with_ids_filters(self):
        self.become_admin()
        machines = [
            factory.make_Node(
                power_parameters={factory.make_string(): factory.make_string()}
            )
            for _ in range(0, 6)
        ]
        expected_machines = random.sample(machines, 3)
        response = self.client.get(
            reverse("machines_handler"),
            {
                "op": "power_parameters",
                "id": [machine.system_id for machine in expected_machines],
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        expected = {
            machine.system_id: machine.get_power_parameters()
            for machine in expected_machines
        }
        self.assertEqual(expected, parsed)
