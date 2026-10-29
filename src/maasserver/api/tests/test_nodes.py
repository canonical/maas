# Copyright 2013-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the nodes API."""

from datetime import timedelta
import http.client
import json
import logging
import random

from django.conf import settings
from django.http import QueryDict
from django.urls import reverse
from django.utils import timezone

from maasserver.api import nodes as nodes_module
from maasserver.api.utils import get_overridden_query_dict
from maasserver.enum import (
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_TYPE,
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_STATUS,
    NODE_STATUS_CHOICES,
    NODE_TYPE,
    NODE_TYPE_CHOICES,
)
from maasserver.exceptions import MAASAPIValidationError
from maasserver.models import (
    ControllerInfo,
    Device,
    Machine,
    RackController,
    RegionController,
)
from maasserver.models import node as node_module
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.testclient import MAASSensibleOAuthClient
from maasserver.utils.orm import post_commit_hooks, reload_object
from metadataserver.enum import (
    HARDWARE_TYPE,
    RESULT_TYPE,
    SCRIPT_STATUS,
    SCRIPT_TYPE,
)


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
        with self.assertRaises(MAASAPIValidationError) as cm:
            nodes_module.filtered_nodes_list_from_request(query)
        self.assertEqual(expected_msg, cm.exception.messages)

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


class RenderedNodesMixin:
    """Creates nodes populating every field rendered by the node listings."""

    clientfactories = {"oauth": MAASSensibleOAuthClient}

    def setUp(self):
        super().setUp()
        self.patch(node_module, "stop_workflow")
        fabric = factory.make_Fabric()
        self.untagged_vlan = fabric.get_default_vlan()
        self.tagged_vlan = factory.make_VLAN(
            fabric=fabric,
            name="tagged",
            dhcp_on=True,
            space=factory.make_Space(),
            primary_rack=factory.make_RackController(),
            secondary_rack=factory.make_RackController(),
        )
        self.relayed_vlan = factory.make_VLAN(
            fabric=factory.make_Fabric(), relay_vlan=self.tagged_vlan
        )
        self.ipv4_subnet = factory.make_Subnet(
            vlan=self.untagged_vlan, version=4, space=None
        )
        self.ipv6_subnet = factory.make_Subnet(
            vlan=self.untagged_vlan, version=6, space=None
        )
        self.tagged_subnet = factory.make_Subnet(
            vlan=self.tagged_vlan, version=4, space=None
        )
        self.relayed_subnet = factory.make_Subnet(
            vlan=self.relayed_vlan, version=4, space=None
        )
        self.info_event_type = factory.make_EventType(level=logging.INFO)
        self.debug_event_type = factory.make_EventType(level=logging.DEBUG)

    def make_ip(self, interface, subnet, alloc_type=IPADDRESS_TYPE.STICKY):
        return factory.make_StaticIPAddress(
            alloc_type=alloc_type,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=interface,
        )

    def make_interfaces(self, node):
        eth0, eth1, eth2 = (
            factory.make_Interface(node=node, vlan=self.untagged_vlan)
            for _ in range(3)
        )
        bond0 = factory.make_Interface(
            INTERFACE_TYPE.BOND,
            node=node,
            vlan=self.untagged_vlan,
            parents=[eth1, eth2],
        )
        br0 = factory.make_Interface(
            INTERFACE_TYPE.BRIDGE,
            node=node,
            vlan=self.untagged_vlan,
            parents=[bond0],
        )
        br0_vlan = factory.make_Interface(
            INTERFACE_TYPE.VLAN,
            node=node,
            vlan=self.tagged_vlan,
            parents=[br0],
        )
        br1 = factory.make_Interface(
            INTERFACE_TYPE.BRIDGE,
            node=node,
            vlan=self.tagged_vlan,
            parents=[br0_vlan],
            params={"mtu": 9000},
        )
        eth3 = factory.make_Interface(node=node, vlan=self.relayed_vlan)
        factory.make_Interface(node=node, link_connected=False)

        self.make_ip(eth0, self.ipv4_subnet)
        self.make_ip(br0, self.ipv6_subnet)
        gateway_link = self.make_ip(br1, self.tagged_subnet)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip="",
            subnet=self.ipv4_subnet,
            interface=br1,
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip="",
            subnet=self.tagged_subnet,
            interface=br1,
        )
        self.make_ip(eth3, self.relayed_subnet, IPADDRESS_TYPE.DISCOVERED)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DHCP,
            ip="",
            subnet=self.relayed_subnet,
            interface=eth3,
        )
        node.boot_interface = eth0
        node.gateway_link_ipv4 = gateway_link
        with post_commit_hooks:
            node.save()

    def make_storage(self, machine):
        volume_group = factory.make_VolumeGroup(node=machine)
        factory.make_Filesystem(
            block_device=factory.make_VirtualBlockDevice(
                filesystem_group=volume_group, node=machine
            ),
            fstype=FILESYSTEM_TYPE.EXT4,
            mount_point="/srv",
            acquired=True,
        )
        raid = factory.make_FilesystemGroup(
            node=machine, group_type=FILESYSTEM_GROUP_TYPE.RAID_1
        )
        factory.make_Filesystem(
            partition=factory.make_Partition(
                partition_table=factory.make_PartitionTable(
                    block_device=raid.virtual_device
                )
            ),
            fstype=FILESYSTEM_TYPE.XFS,
            mount_point="/data",
            acquired=True,
        )
        for cache_set in (
            factory.make_CacheSet(
                block_device=factory.make_PhysicalBlockDevice(node=machine),
                node=machine,
            ),
            factory.make_CacheSet(
                partition=factory.make_Partition(node=machine), node=machine
            ),
        ):
            factory.make_FilesystemGroup(
                node=machine,
                group_type=FILESYSTEM_GROUP_TYPE.BCACHE,
                cache_set=cache_set,
            )
        factory.make_VMFS(node=machine)
        factory.make_Filesystem(
            node_config=machine.current_config,
            fstype=FILESYSTEM_TYPE.RAMFS,
            mount_point="/ram",
        )
        numa_node = factory.make_NUMANode(node=machine)
        factory.make_NUMANodeHugepages(numa_node=numa_node)
        factory.make_PhysicalBlockDevice(node=machine, numa_node=numa_node)

    def make_events(self, node):
        now = timezone.now()
        for minutes, event_type, description in (
            (1, self.info_event_type, "older"),
            (2, self.info_event_type, "latest"),
            (3, self.debug_event_type, "debug"),
        ):
            factory.make_Event(
                node=node,
                type=event_type,
                description=description,
                created=now + timedelta(minutes=minutes),
            )

    def make_script_result(self, script_set, hardware_type, status, **kwargs):
        script = factory.make_Script(
            script_type=(
                SCRIPT_TYPE.COMMISSIONING
                if script_set.result_type == RESULT_TYPE.COMMISSIONING
                else SCRIPT_TYPE.TESTING
            ),
            hardware_type=hardware_type,
        )
        return factory.make_ScriptResult(
            script_set=script_set, script=script, status=status, **kwargs
        )

    def make_script_results(self, node):
        commissioning, testing, installation = (
            factory.make_ScriptSet(node=node, result_type=result_type)
            for result_type in (
                RESULT_TYPE.COMMISSIONING,
                RESULT_TYPE.TESTING,
                RESULT_TYPE.INSTALLATION,
            )
        )
        self.make_script_result(
            commissioning, HARDWARE_TYPE.NODE, SCRIPT_STATUS.PASSED
        )
        self.make_script_result(
            commissioning, HARDWARE_TYPE.CPU, SCRIPT_STATUS.FAILED
        )
        superseded = self.make_script_result(
            testing, HARDWARE_TYPE.CPU, SCRIPT_STATUS.FAILED
        )
        factory.make_ScriptResult(
            script_set=testing,
            script=superseded.script,
            status=SCRIPT_STATUS.PASSED,
        )
        self.make_script_result(
            testing,
            HARDWARE_TYPE.MEMORY,
            SCRIPT_STATUS.FAILED,
            suppressed=True,
        )
        self.make_script_result(
            testing,
            HARDWARE_TYPE.STORAGE,
            SCRIPT_STATUS.RUNNING,
            physical_blockdevice=node.physicalblockdevice_set.first(),
        )
        self.make_script_result(
            testing,
            HARDWARE_TYPE.NETWORK,
            SCRIPT_STATUS.FAILED,
            interface=node.current_config.interface_set.first(),
        )
        self.make_script_result(
            testing, HARDWARE_TYPE.NODE, SCRIPT_STATUS.PASSED
        )
        self.make_script_result(
            testing, HARDWARE_TYPE.NODE, SCRIPT_STATUS.ABORTED
        )
        self.make_script_result(
            installation, HARDWARE_TYPE.NODE, SCRIPT_STATUS.FAILED
        )

    def populate_node(self, node):
        self.make_interfaces(node)
        self.make_events(node)
        self.make_script_results(node)
        node.tags.add(factory.make_Tag(), factory.make_Tag())
        factory.make_NodeMetadata(node=node, key="cpu_model", value="cpu")

    def make_rich_machine(self):
        machine = factory.make_Node(
            status=NODE_STATUS.DEPLOYED,
            owner=self.user,
            owner_data={"key": "value"},
        )
        self.make_storage(machine)
        self.populate_node(machine)
        return machine

    def make_machine_with_fallbacks(self, parent):
        domain = factory.make_Domain()
        factory.make_DNSResource(domain=domain)
        machine = factory.make_Node(
            status=NODE_STATUS.READY,
            with_boot_disk=False,
            parent=parent,
            domain=domain,
        )
        factory.make_PhysicalBlockDevice(
            node=machine, size=MIN_BLOCK_DEVICE_SIZE
        )
        partition = factory.make_Partition(
            partition_table=factory.make_PartitionTable(
                block_device=factory.make_PhysicalBlockDevice(node=machine)
            )
        )
        for fstype, acquired in (
            (FILESYSTEM_TYPE.EXT4, False),
            (FILESYSTEM_TYPE.XFS, True),
        ):
            factory.make_Filesystem(
                partition=partition,
                fstype=fstype,
                mount_point="/",
                acquired=acquired,
            )
        eth0 = factory.make_Interface(node=machine, vlan=self.tagged_vlan)
        factory.make_Interface(
            INTERFACE_TYPE.VLAN,
            node=machine,
            vlan=factory.make_VLAN(fabric=self.tagged_vlan.fabric),
            parents=[eth0],
        )
        return machine

    def make_machines(self):
        machine = self.make_rich_machine()
        return [
            machine,
            self.make_machine_with_fallbacks(parent=machine),
            factory.make_Node(
                status=NODE_STATUS.ALLOCATED,
                owner=self.user,
                with_boot_disk=False,
            ),
            self.make_rich_machine(),
        ]

    def make_rich_device(self, parent):
        device = factory.make_Device(
            owner=self.user,
            parent=parent,
            domain=factory.make_Domain(),
            owner_data={"key": "value"},
        )
        eth0 = factory.make_Interface(node=device, vlan=self.tagged_vlan)
        self.make_ip(eth0, self.tagged_subnet)
        self.make_ip(eth0, self.relayed_subnet, IPADDRESS_TYPE.DISCOVERED)
        device.tags.add(factory.make_Tag())
        return device

    def make_rich_controller(self, make_controller):
        controller = make_controller()
        self.populate_node(controller)
        ControllerInfo.objects.set_version(controller, "3.7.0")
        return controller

    def make_nodes(self):
        machines = self.make_machines()
        return [
            *machines,
            self.make_rich_device(parent=machines[0]),
            factory.make_Device(owner=self.user),
            self.make_rich_controller(factory.make_RackController),
            self.make_rich_controller(factory.make_RegionController),
            self.make_rich_controller(factory.make_RegionRackController),
        ]

    def get_json(self, path, params=None):
        response = self.client.get(path, params)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        return response.json()

    def assertListedLikeDetails(self, listing, detail_handler, partial=False):
        self.assertNotEqual([], listing)
        for listed in listing:
            details = self.get_json(
                reverse(detail_handler, args=[listed["system_id"]])
            )
            if partial:
                details = {key: details[key] for key in listed}
            # Tags are rendered in database order, which isn't stable.
            for rendered in (details, listed):
                rendered["tag_names"].sort()
            self.assertEqual(details, listed)


class TestNodesListingsMatchDetails(RenderedNodesMixin, APITestCase.ForAdmin):
    def setUp(self):
        super().setUp()
        self.make_nodes()

    def test_GET_nodes(self):
        listing = self.get_json(reverse("nodes_handler"))

        regions_only = RegionController.objects.filter(
            node_type=NODE_TYPE.REGION_CONTROLLER
        )
        self.assertEqual(
            [
                node.system_id
                for nodes in (
                    Device.objects.all(),
                    Machine.objects.all(),
                    RackController.objects.all(),
                    regions_only,
                )
                for node in nodes.order_by("id")
            ],
            extract_system_ids(listing),
        )
        self.assertListedLikeDetails(listing, "node_handler")

    def test_GET_machines(self):
        self.assertListedLikeDetails(
            self.get_json(reverse("machines_handler")), "machine_handler"
        )

    def test_GET_devices(self):
        self.assertListedLikeDetails(
            self.get_json(reverse("devices_handler")), "device_handler"
        )

    def test_GET_rackcontrollers(self):
        self.assertListedLikeDetails(
            self.get_json(reverse("rackcontrollers_handler")),
            "rackcontroller_handler",
        )

    def test_GET_regioncontrollers(self):
        listing = self.get_json(reverse("regioncontrollers_handler"))

        for listed in listing:
            self.assertEqual(
                reverse(
                    "regioncontroller_handler", args=[listed["system_id"]]
                ),
                listed["resource_uri"],
            )
        self.assertListedLikeDetails(
            [
                listed
                for listed in listing
                if listed["node_type"] == NODE_TYPE.REGION_CONTROLLER
            ],
            "regioncontroller_handler",
        )
        # Region+rack controllers details are rendered as rack controllers.
        region_racks = [
            listed
            for listed in listing
            if listed["node_type"] == NODE_TYPE.REGION_AND_RACK_CONTROLLER
        ]
        for listed in region_racks:
            del listed["resource_uri"]
        self.assertListedLikeDetails(
            region_racks, "regioncontroller_handler", partial=True
        )
