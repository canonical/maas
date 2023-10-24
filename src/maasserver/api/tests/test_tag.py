# Copyright 2013-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import http.client
import json
from unittest import skip
from unittest.mock import ANY, call

from django.conf import settings
from django.urls import reverse
from testtools.matchers import MatchesStructure

from apiclient.creds import convert_tuple_to_string
from maasserver.enum import NODE_STATUS
from maasserver.models import Event, Tag
from maasserver.models.node import generate_node_system_id
from maasserver.models.user import (
    create_auth_token,
    get_auth_tokens,
    get_creds_tuple,
)
from maasserver.testing.api import APITestCase, make_worker_client
from maasserver.testing.factory import factory
from maasserver.testing.testclient import MAASSensibleOAuthClient
from maasserver.utils.orm import reload_object
from maastesting.djangotestcase import count_queries
from maastesting.matchers import MockCalledOnceWith, MockCallsMatch
from provisioningserver.events import AUDIT, EVENT_TYPES


def extract_system_ids(parsed_result):
    """List the system_ids of the machines in `parsed_result`."""
    return [machine.get("system_id") for machine in parsed_result]


class TestTagAPI(APITestCase.ForUser):
    """Tests for /api/2.0/tags/<tagname>/."""

    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/tags/tag-name/",
            reverse("tag_handler", args=["tag-name"]),
        )

    def get_tag_uri(self, tag):
        """Get the API URI for `tag`."""
        return reverse("tag_handler", args=[tag.name])

    def test_DELETE_requires_admin(self):
        tag = factory.make_Tag()
        response = self.client.delete(self.get_tag_uri(tag))
        self.assertEqual(http.client.FORBIDDEN, response.status_code)
        self.assertCountEqual([tag], Tag.objects.filter(id=tag.id))

    def test_DELETE_removes_tag(self):
        self.become_admin()
        tag = factory.make_Tag()
        response = self.client.delete(self.get_tag_uri(tag))
        self.assertEqual(http.client.NO_CONTENT, response.status_code)
        self.assertFalse(Tag.objects.filter(id=tag.id).exists())

    def test_DELETE_creates_event_log(self):
        self.become_admin()
        tag = factory.make_Tag()
        self.client.delete(self.get_tag_uri(tag))
        event = Event.objects.get(type__level=AUDIT)
        self.assertEqual(event.type.name, EVENT_TYPES.TAG)
        self.assertEqual(event.description, f"Tag '{tag.name}' deleted.")

    def test_DELETE_404(self):
        self.become_admin()
        url = reverse("tag_handler", args=["no-tag"])
        response = self.client.delete(url)
        self.assertEqual(http.client.NOT_FOUND, response.status_code)

    def test_GET_returns_tag(self):
        # The api allows for fetching a single Node (using system_id).
        tag = factory.make_Tag("tag-name")
        url = reverse("tag_handler", args=["tag-name"])
        response = self.client.get(url)

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(response.content.decode("ascii"))
        self.assertEqual(tag.name, parsed_result["name"])
        self.assertEqual(tag.definition, parsed_result["definition"])
        self.assertEqual(tag.comment, parsed_result["comment"])

    def test_GET_refuses_to_access_nonexistent_node(self):
        # When fetching a Tag, the api returns a 'Not Found' (404) error
        # if no tag is found.
        url = reverse("tag_handler", args=["no-such-tag"])
        response = self.client.get(url)
        self.assertEqual(http.client.NOT_FOUND, response.status_code)

    def test_PUT_refuses_non_superuser(self):
        tag = factory.make_Tag()
        response = self.client.put(
            self.get_tag_uri(tag), {"comment": "A special comment"}
        )
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_PUT_updates_tag(self):
        self.become_admin()
        tag = factory.make_Tag()
        # Note that 'definition' is not being sent
        response = self.client.put(
            self.get_tag_uri(tag),
            {"name": "new-tag-name", "comment": "A random comment"},
        )

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(response.content.decode("ascii"))
        self.assertEqual("new-tag-name", parsed_result["name"])
        self.assertEqual("A random comment", parsed_result["comment"])
        self.assertEqual(tag.definition, parsed_result["definition"])
        self.assertFalse(Tag.objects.filter(name=tag.name).exists())
        self.assertTrue(Tag.objects.filter(name="new-tag-name").exists())

    def test_PUT_creates_event_log(self):
        self.become_admin()
        tag = factory.make_Tag()
        self.client.put(
            self.get_tag_uri(tag),
            {"comment": "A random comment"},
        )
        event = Event.objects.get(type__level=AUDIT)
        self.assertEqual(event.type.name, EVENT_TYPES.TAG)
        self.assertEqual(event.description, f"Tag '{tag.name}' updated.")

    def test_PUT_creates_event_log_rename(self):
        self.become_admin()
        tag = factory.make_Tag()
        old_name = tag.name
        new_name = factory.make_string()
        self.client.put(
            self.get_tag_uri(tag),
            {"name": new_name},
        )
        event = Event.objects.get(type__level=AUDIT)
        self.assertEqual(event.type.name, EVENT_TYPES.TAG)
        self.assertEqual(
            event.description, f"Tag '{old_name}' renamed to '{new_name}'."
        )

    def test_PUT_updates_node_associations(self):
        populate_nodes = self.patch_autospec(Tag, "populate_nodes")
        tag = Tag(name=factory.make_name("tag"), definition="//node/foo")
        tag.save()
        self.expectThat(populate_nodes, MockCalledOnceWith(tag))
        self.become_admin()
        response = self.client.put(
            self.get_tag_uri(tag), {"definition": "//node/bar"}
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.expectThat(populate_nodes, MockCallsMatch(call(tag), call(tag)))

    def test_GET_nodes_with_no_nodes(self):
        tag = factory.make_Tag()
        response = self.client.get(self.get_tag_uri(tag), {"op": "nodes"})

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(response.content.decode("ascii"))
        self.assertEqual([], parsed_result)

    def test_GET_nodes_returns_nodes(self):
        tag = factory.make_Tag()
        machine = factory.make_Node()
        device = factory.make_Device()
        rack = factory.make_RackController()
        region = factory.make_RegionController()
        # Create a second node that isn't tagged.
        factory.make_Node()
        machine.tags.add(tag)
        device.tags.add(tag)
        rack.tags.add(tag)
        region.tags.add(tag)
        response = self.client.get(self.get_tag_uri(tag), {"op": "nodes"})

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertCountEqual(
            [machine.system_id, device.system_id],
            [r["system_id"] for r in parsed_result],
        )

    def test_GET_nodes_query_count(self):
        tag = factory.make_Tag()

        query_counts = []
        node_counts = []

        vlan = factory.make_VLAN(space=factory.make_Space())
        machine = factory.make_Node_with_Interface_on_Subnet(vlan=vlan)
        machine.tags.add(tag)
        num_queries, response = count_queries(
            self.client.get, self.get_tag_uri(tag), {"op": "nodes"}
        )
        query_counts.append(num_queries)
        node_counts.append(len(response.json()))
        machine = factory.make_Node_with_Interface_on_Subnet()
        machine.tags.add(tag)
        num_queries, response = count_queries(
            self.client.get, self.get_tag_uri(tag), {"op": "nodes"}
        )
        query_counts.append(num_queries)
        node_counts.append(len(response.json()))
        machine = factory.make_Node_with_Interface_on_Subnet()
        machine.tags.add(tag)
        num_queries, response = count_queries(
            self.client.get, self.get_tag_uri(tag), {"op": "nodes"}
        )
        query_counts.append(num_queries)
        node_counts.append(len(response.json()))

        self.assertEqual(node_counts, [1, 2, 3])
        # Because of fields `status_action`, `status_message`,
        # `default_gateways`, `health_status` and 'resource_pool', the number
        # of queries is not the same but it is proportional to the number of
        # machines.
        base_count = 88
        for idx, node_count in enumerate(node_counts):
            self.assertEqual(query_counts[idx], base_count + (node_count * 6))

    def test_GET_machines_returns_machines(self):
        tag = factory.make_Tag()
        machine = factory.make_Node()
        device = factory.make_Device()
        rack = factory.make_RackController()
        region = factory.make_RegionController()
        # Create a second node that isn't tagged.
        factory.make_Node()
        machine.tags.add(tag)
        device.tags.add(tag)
        rack.tags.add(tag)
        region.tags.add(tag)
        response = self.client.get(self.get_tag_uri(tag), {"op": "machines"})

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(
            [machine.system_id], [r["system_id"] for r in parsed_result]
        )

    def test_GET_machines_query_count(self):
        tag = factory.make_Tag()

        query_counts = []
        machine_counts = []

        machine = factory.make_Node_with_Interface_on_Subnet()
        machine.tags.add(tag)
        num_queries, response = count_queries(
            self.client.get, self.get_tag_uri(tag), {"op": "machines"}
        )
        query_counts.append(num_queries)
        machine_counts.append(len(response.json()))
        machine = factory.make_Node_with_Interface_on_Subnet()
        machine.tags.add(tag)
        num_queries, response = count_queries(
            self.client.get, self.get_tag_uri(tag), {"op": "machines"}
        )
        query_counts.append(num_queries)
        machine_counts.append(len(response.json()))
        machine = factory.make_Node_with_Interface_on_Subnet()
        machine.tags.add(tag)
        num_queries, response = count_queries(
            self.client.get, self.get_tag_uri(tag), {"op": "machines"}
        )
        query_counts.append(num_queries)
        machine_counts.append(len(response.json()))

        self.assertEqual(machine_counts, [1, 2, 3])
        # Because of fields `status_action`, `status_message`,
        # `default_gateways`, `health_status` and 'resource_pool', the number
        # of queries is not the same but it is proportional to the number of
        # machines.
        base_count = 92
        for idx, machine_count in enumerate(machine_counts):
            self.assertLessEqual(
                query_counts[idx], base_count + (machine_count * 6)
            )

    def test_GET_devices_returns_devices(self):
        tag = factory.make_Tag()
        machine = factory.make_Node()
        device = factory.make_Device()
        rack = factory.make_RackController()
        region = factory.make_RegionController()
        # Create a second node that isn't tagged.
        factory.make_Node()
        machine.tags.add(tag)
        device.tags.add(tag)
        rack.tags.add(tag)
        region.tags.add(tag)
        response = self.client.get(self.get_tag_uri(tag), {"op": "devices"})

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(
            [device.system_id], [r["system_id"] for r in parsed_result]
        )

    def test_GET_devices_query_count(self):
        tag = factory.make_Tag()
        for _ in range(3):
            device = factory.make_Device()
            device.tags.add(tag)
        num_queries1, response1 = count_queries(
            self.client.get, self.get_tag_uri(tag), {"op": "devices"}
        )

        for _ in range(3):
            device = factory.make_Device()
            device.tags.add(tag)
        num_queries2, response2 = count_queries(
            self.client.get, self.get_tag_uri(tag), {"op": "devices"}
        )

        # Make sure the responses are ok as it's not useful to compare the
        # number of queries if they are not.
        parsed_result_1 = json.loads(
            response1.content.decode(settings.DEFAULT_CHARSET)
        )
        parsed_result_2 = json.loads(
            response2.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(
            [http.client.OK, http.client.OK, 3, 6],
            [
                response1.status_code,
                response2.status_code,
                len(extract_system_ids(parsed_result_1)),
                len(extract_system_ids(parsed_result_2)),
            ],
        )
        self.assertEqual(num_queries1, num_queries2)

    def test_GET_rack_controllers_returns_rack_controllers(self):
        self.become_admin()
        tag = factory.make_Tag()
        machine = factory.make_Node()
        device = factory.make_Device()
        rack = factory.make_RackController()
        region = factory.make_RegionController()
        # Create a second node that isn't tagged.
        factory.make_Node()
        machine.tags.add(tag)
        device.tags.add(tag)
        rack.tags.add(tag)
        region.tags.add(tag)
        response = self.client.get(
            self.get_tag_uri(tag), {"op": "rack_controllers"}
        )

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(
            [rack.system_id], [r["system_id"] for r in parsed_result]
        )

    @skip("XXX: ltrager 2919-11-29 bug=1854546")
    def test_GET_rack_controllers_query_count(self):
        self.become_admin()

        tag = factory.make_Tag()
        for _ in range(3):
            rack = factory.make_RackController()
            rack.tags.add(tag)
        num_queries1, response1 = count_queries(
            self.client.get, self.get_tag_uri(tag), {"op": "rack_controllers"}
        )

        for _ in range(3):
            rack = factory.make_RackController()
            rack.tags.add(tag)
        num_queries2, response2 = count_queries(
            self.client.get, self.get_tag_uri(tag), {"op": "rack_controllers"}
        )

        # Make sure the responses are ok as it's not useful to compare the
        # number of queries if they are not.
        parsed_result_1 = json.loads(
            response1.content.decode(settings.DEFAULT_CHARSET)
        )
        parsed_result_2 = json.loads(
            response2.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(
            [http.client.OK, http.client.OK, 3, 6],
            [
                response1.status_code,
                response2.status_code,
                len(extract_system_ids(parsed_result_1)),
                len(extract_system_ids(parsed_result_2)),
            ],
        )
        self.assertEqual(num_queries1, num_queries2 - (3 * 3))

    def test_GET_rack_controllers_returns_no_rack_controllers_nonadmin(self):
        tag = factory.make_Tag()
        machine = factory.make_Node()
        device = factory.make_Device()
        rack = factory.make_RackController()
        region = factory.make_RegionController()
        # Create a second node that isn't tagged.
        factory.make_Node()
        machine.tags.add(tag)
        device.tags.add(tag)
        rack.tags.add(tag)
        region.tags.add(tag)
        response = self.client.get(
            self.get_tag_uri(tag), {"op": "rack_controllers"}
        )

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual([], parsed_result)

    def test_GET_region_controllers_returns_region_controllers(self):
        self.become_admin()
        tag = factory.make_Tag()
        machine = factory.make_Node()
        device = factory.make_Device()
        rack = factory.make_RackController()
        region = factory.make_RegionController()
        # Create a second node that isn't tagged.
        factory.make_Node()
        machine.tags.add(tag)
        device.tags.add(tag)
        rack.tags.add(tag)
        region.tags.add(tag)
        response = self.client.get(
            self.get_tag_uri(tag), {"op": "region_controllers"}
        )

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(
            [region.system_id], [r["system_id"] for r in parsed_result]
        )

    def test_GET_region_controllers_query_count(self):
        self.become_admin()

        tag = factory.make_Tag()
        for _ in range(3):
            region = factory.make_RegionController()
            region.tags.add(tag)
        num_queries1, response1 = count_queries(
            self.client.get,
            self.get_tag_uri(tag),
            {"op": "region_controllers"},
        )

        for _ in range(3):
            region = factory.make_RegionController()
            region.tags.add(tag)
        num_queries2, response2 = count_queries(
            self.client.get,
            self.get_tag_uri(tag),
            {"op": "region_controllers"},
        )

        # Make sure the responses are ok as it's not useful to compare the
        # number of queries if they are not.
        parsed_result_1 = json.loads(
            response1.content.decode(settings.DEFAULT_CHARSET)
        )
        parsed_result_2 = json.loads(
            response2.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(
            [http.client.OK, http.client.OK, 3, 6],
            [
                response1.status_code,
                response2.status_code,
                len(extract_system_ids(parsed_result_1)),
                len(extract_system_ids(parsed_result_2)),
            ],
        )
        # XXX The number for queries should be the same, but they are
        # not. Ensure that at least it's not pure linear.
        self.assertGreater(num_queries1 * 2, num_queries2)

    def test_GET_region_controllers_returns_no_controllers_nonadmin(self):
        tag = factory.make_Tag()
        machine = factory.make_Node()
        device = factory.make_Device()
        rack = factory.make_RackController()
        region = factory.make_RegionController()
        # Create a second node that isn't tagged.
        factory.make_Node()
        machine.tags.add(tag)
        device.tags.add(tag)
        rack.tags.add(tag)
        region.tags.add(tag)
        response = self.client.get(
            self.get_tag_uri(tag), {"op": "region_controllers"}
        )

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual([], parsed_result)

    def test_GET_nodes_hides_invisible_nodes(self):
        user2 = factory.make_User()
        node1 = factory.make_Node()
        node2 = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=user2)
        tag = factory.make_Tag()
        node1.tags.add(tag)
        node2.tags.add(tag)

        response = self.client.get(self.get_tag_uri(tag), {"op": "nodes"})

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(
            [node1.system_id], [r["system_id"] for r in parsed_result]
        )
        # The other user can also see his node
        client2 = MAASSensibleOAuthClient(user2)
        response = client2.get(self.get_tag_uri(tag), {"op": "nodes"})
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertCountEqual(
            [node1.system_id, node2.system_id],
            [r["system_id"] for r in parsed_result],
        )

    def test_PUT_invalid_definition(self):
        self.become_admin()
        node = factory.make_Node()
        tag = factory.make_Tag(definition="//child")
        node.tags.add(tag)
        self.assertEqual([tag.name], node.tag_names())
        response = self.client.put(
            self.get_tag_uri(tag),
            {"name": "bad tag", "definition": "invalid::tag"},
        )

        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        # The tag should not be modified
        tag = reload_object(tag)
        self.assertEqual([tag.name], node.tag_names())
        self.assertEqual("//child", tag.definition)

    def test_POST_update_nodes_unknown_tag(self):
        self.become_admin()
        name = factory.make_name()
        response = self.client.post(
            reverse("tag_handler", args=[name]), {"op": "update_nodes"}
        )
        self.assertEqual(http.client.NOT_FOUND, response.status_code)
        # check we have a verbose output
        self.assertEqual(
            "No Tag matches the given query.",
            response.content.decode(settings.DEFAULT_CHARSET),
        )

    def test_POST_update_nodes_changes_associations(self):
        tag = factory.make_Tag()
        self.become_admin()
        node_first = factory.make_Node()
        node_second = factory.make_Node()
        node_first.tags.add(tag)
        self.assertCountEqual([node_first], tag.node_set.all())
        response = self.client.post(
            self.get_tag_uri(tag),
            {
                "op": "update_nodes",
                "add": [node_second.system_id],
                "remove": [node_first.system_id],
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertCountEqual([node_second], tag.node_set.all())
        self.assertEqual({"added": 1, "removed": 1}, parsed_result)

    def test_POST_update_nodes_ignores_unknown_nodes(self):
        tag = factory.make_Tag()
        self.become_admin()
        unknown_add_system_id = generate_node_system_id()
        unknown_remove_system_id = generate_node_system_id()
        self.assertCountEqual([], tag.node_set.all())
        response = self.client.post(
            self.get_tag_uri(tag),
            {
                "op": "update_nodes",
                "add": [unknown_add_system_id],
                "remove": [unknown_remove_system_id],
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertCountEqual([], tag.node_set.all())
        self.assertEqual({"added": 0, "removed": 0}, parsed_result)

    def test_POST_update_nodes_doesnt_require_add_or_remove(self):
        tag = factory.make_Tag()
        node = factory.make_Node()
        self.become_admin()
        self.assertCountEqual([], tag.node_set.all())
        response = self.client.post(
            self.get_tag_uri(tag),
            {"op": "update_nodes", "add": [node.system_id]},
        )
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual({"added": 1, "removed": 0}, parsed_result)
        response = self.client.post(
            self.get_tag_uri(tag),
            {"op": "update_nodes", "remove": [node.system_id]},
        )
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual({"added": 0, "removed": 1}, parsed_result)

    def test_POST_update_nodes_rejects_normal_user(self):
        tag = factory.make_Tag()
        node = factory.make_Node()
        response = self.client.post(
            self.get_tag_uri(tag),
            {"op": "update_nodes", "add": [node.system_id]},
        )
        self.assertEqual(http.client.FORBIDDEN, response.status_code)
        self.assertCountEqual([], tag.node_set.all())

    def test_POST_update_nodes_allows_rack_controller(self):
        tag = factory.make_Tag()
        rack_controller = factory.make_RackController()
        node = factory.make_Node()
        client = make_worker_client(rack_controller)
        tokens = list(get_auth_tokens(rack_controller.owner))
        if len(tokens) > 0:
            # Use the latest token.
            token = tokens[-1]
        else:
            token = create_auth_token(rack_controller.owner)
        token.save()
        creds = convert_tuple_to_string(get_creds_tuple(token))
        response = client.post(
            self.get_tag_uri(tag),
            {
                "op": "update_nodes",
                "add": [node.system_id],
                "rack_controller": rack_controller.system_id,
                "credentials": creds,
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual({"added": 1, "removed": 0}, parsed_result)
        self.assertCountEqual([node], tag.node_set.all())

    def test_POST_update_nodes_refuses_non_rack_controller(self):
        tag = factory.make_Tag()
        rack_controller = factory.make_RackController()
        node = factory.make_Node()
        token = create_auth_token(rack_controller.owner)
        token.save()
        creds = convert_tuple_to_string(get_creds_tuple(token))
        response = self.client.post(
            self.get_tag_uri(tag),
            {
                "op": "update_nodes",
                "add": [node.system_id],
                "rack_controller": rack_controller.system_id,
                "credentials": creds,
            },
        )
        self.assertEqual(http.client.FORBIDDEN, response.status_code)
        self.assertCountEqual([], tag.node_set.all())

    def test_POST_update_nodes_refuses_no_token(self):
        tag = factory.make_Tag()
        rack_controller = factory.make_RackController()
        node = factory.make_Node()
        # create a token for a different user
        token = create_auth_token(factory.make_User())
        token.save()
        creds = convert_tuple_to_string(get_creds_tuple(token))
        response = self.client.post(
            self.get_tag_uri(tag),
            {
                "op": "update_nodes",
                "add": [node.system_id],
                "rack_controller": rack_controller.system_id,
                "credentials": creds,
            },
        )
        self.assertEqual(http.client.FORBIDDEN, response.status_code)
        self.assertCountEqual([], tag.node_set.all())

    def test_POST_update_nodes_ignores_incorrect_definition(self):
        tag = factory.make_Tag()
        orig_def = tag.definition
        rack_controller = factory.make_RackController()
        node = factory.make_Node()
        client = make_worker_client(rack_controller)
        tag.definition = "//new/node/definition"
        tag.save(populate=False)
        response = client.post(
            self.get_tag_uri(tag),
            {
                "op": "update_nodes",
                "add": [node.system_id],
                "rack_controller": rack_controller.system_id,
                "definition": orig_def,
            },
        )
        self.assertEqual(http.client.CONFLICT, response.status_code)
        self.assertCountEqual([], tag.node_set.all())
        self.assertCountEqual([], node.tags.all())

    def test_POST_rebuild_rebuilds_node_mapping(self):
        populate_nodes = self.patch_autospec(Tag, "populate_nodes")
        tag = Tag(name=factory.make_name("tag"), definition="//foo/bar")
        tag.save()
        self.become_admin()
        self.assertThat(populate_nodes, MockCalledOnceWith(tag))
        response = self.client.post(self.get_tag_uri(tag), {"op": "rebuild"})
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual({"rebuilding": tag.name}, parsed_result)
        self.assertThat(populate_nodes, MockCallsMatch(call(tag), call(tag)))

    def test_POST_rebuild_leaves_manual_tags(self):
        tag = factory.make_Tag(definition="")
        node = factory.make_Node()
        node.tags.add(tag)
        self.assertCountEqual([node], tag.node_set.all())
        self.become_admin()
        response = self.client.post(self.get_tag_uri(tag), {"op": "rebuild"})
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual({"rebuilding": tag.name}, parsed_result)
        self.assertCountEqual([node], tag.node_set.all())

    def test_POST_rebuild_unknown_404(self):
        self.become_admin()
        response = self.client.post(
            reverse("tag_handler", args=["unknown-tag"]), {"op": "rebuild"}
        )
        self.assertEqual(http.client.NOT_FOUND, response.status_code)

    def test_POST_rebuild_requires_admin(self):
        tag = factory.make_Tag(definition="/foo/bar")
        response = self.client.post(self.get_tag_uri(tag), {"op": "rebuild"})
        self.assertEqual(http.client.FORBIDDEN, response.status_code)


class TestTagsAPI(APITestCase.ForUser):
    def test_handler_path(self):
        self.assertEqual("/MAAS/api/2.0/tags/", reverse("tags_handler"))

    def test_GET_list_without_tags_returns_empty_list(self):
        response = self.client.get(reverse("tags_handler"))
        self.assertEqual(
            [], json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        )

    def test_POST_new_refuses_non_admin(self):
        name = factory.make_string()
        response = self.client.post(
            reverse("tags_handler"),
            {
                "name": name,
                "comment": factory.make_string(),
                "definition": factory.make_string(),
            },
        )
        self.assertEqual(http.client.FORBIDDEN, response.status_code)
        self.assertFalse(Tag.objects.filter(name=name).exists())

    def test_POST_new_creates_tag(self):
        self.patch_autospec(Tag, "populate_nodes")
        self.become_admin()
        name = factory.make_string()
        definition = "//node"
        comment = factory.make_string()
        response = self.client.post(
            reverse("tags_handler"),
            {"name": name, "comment": comment, "definition": definition},
        )
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(name, parsed_result["name"])
        self.assertEqual(comment, parsed_result["comment"])
        self.assertEqual(definition, parsed_result["definition"])
        self.assertTrue(Tag.objects.filter(name=name).exists())
        self.assertThat(Tag.populate_nodes, MockCalledOnceWith(ANY))

    def test_POST_creates_event_log(self):
        self.patch_autospec(Tag, "populate_nodes")
        self.become_admin()
        name = factory.make_string()
        self.client.post(
            reverse("tags_handler"),
            {"name": name},
        )
        event = Event.objects.get(type__level=AUDIT)
        self.assertEqual(event.type.name, EVENT_TYPES.TAG)
        self.assertEqual(event.description, f"Tag '{name}' created.")

    def test_POST_new_without_definition_creates_tag(self):
        self.become_admin()
        name = factory.make_string()
        comment = factory.make_string()
        response = self.client.post(
            reverse("tags_handler"), {"name": name, "comment": comment}
        )
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(name, parsed_result["name"])
        self.assertEqual(comment, parsed_result["comment"])
        self.assertEqual("", parsed_result["definition"])
        self.assertTrue(Tag.objects.filter(name=name).exists())

    def test_POST_new_invalid_tag_name(self):
        self.become_admin()
        # We do not check the full possible set of invalid names here, a more
        # thorough check is done in test_tag, we just check that we get a
        # reasonable error here.
        invalid = "invalid:name"
        definition = "//node"
        comment = factory.make_string()
        response = self.client.post(
            reverse("tags_handler"),
            {"name": invalid, "comment": comment, "definition": definition},
        )
        self.assertEqual(
            http.client.BAD_REQUEST,
            response.status_code,
            "We did not get BAD_REQUEST for an invalid tag name: %r"
            % (invalid,),
        )
        self.assertFalse(Tag.objects.filter(name=invalid).exists())

    def test_POST_new_kernel_opts(self):
        self.patch_autospec(Tag, "populate_nodes")
        self.become_admin()
        name = factory.make_string()
        definition = "//node"
        comment = factory.make_string()
        extra_kernel_opts = factory.make_string()
        response = self.client.post(
            reverse("tags_handler"),
            {
                "name": name,
                "comment": comment,
                "definition": definition,
                "kernel_opts": extra_kernel_opts,
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(name, parsed_result["name"])
        self.assertEqual(comment, parsed_result["comment"])
        self.assertEqual(definition, parsed_result["definition"])
        self.assertEqual(extra_kernel_opts, parsed_result["kernel_opts"])
        self.assertEqual(
            extra_kernel_opts, Tag.objects.filter(name=name)[0].kernel_opts
        )
        self.assertThat(Tag.populate_nodes, MockCalledOnceWith(ANY))

    def test_POST_new_populates_nodes(self):
        populate_nodes = self.patch_autospec(Tag, "populate_nodes")
        self.become_admin()
        name = factory.make_string()
        definition = "//node/child"
        comment = factory.make_string()
        response = self.client.post(
            reverse("tags_handler"),
            {"name": name, "comment": comment, "definition": definition},
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertThat(populate_nodes, MockCalledOnceWith(ANY))
        # The tag passed to populate_nodes() is the one created above.
        [tag], _ = populate_nodes.call_args
        self.assertThat(
            tag,
            MatchesStructure.byEquality(
                name=name, comment=comment, definition=definition
            ),
        )
