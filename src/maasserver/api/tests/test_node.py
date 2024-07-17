# Copyright 2013-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from functools import partial
import http.client
import random
from unittest.mock import ANY, Mock

import bson
from django.conf import settings
from django.urls import reverse
from twisted.internet.defer import succeed

from maasserver.api import auth
from maasserver.enum import NODE_STATUS, NODE_STATUS_CHOICES
from maasserver.models import Config, Node
from maasserver.models import node as node_module
from maasserver.models import NodeKey
from maasserver.models.scriptset import get_status_from_qs
from maasserver.testing.api import APITestCase
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.factory import factory
from maasserver.testing.fixtures import RBACEnabled
from maasserver.testing.osystems import make_usable_osystem
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.testing.testclient import MAASSensibleOAuthClient
from maasserver.utils import osystems
from maasserver.utils.converters import json_load_bytes
from maasserver.utils.orm import reload_object
from metadataserver.enum import (
    HARDWARE_TYPE,
    RESULT_TYPE,
    SCRIPT_STATUS,
    SCRIPT_STATUS_CHOICES,
    SCRIPT_TYPE,
)
from metadataserver.nodeinituser import get_node_init_user
from provisioningserver.enum import POWER_STATE
from provisioningserver.refresh.node_info_scripts import (
    LLDP_OUTPUT_NAME,
    LSHW_OUTPUT_NAME,
)
from provisioningserver.rpc.exceptions import PowerActionAlreadyInProgress


class TestNodeAnonAPI(MAASServerTestCase):
    def test_anonymous_user_cannot_access(self):
        client = MAASSensibleOAuthClient()
        response = client.get(reverse("nodes_handler"))
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertEqual(
            "Unrecognised signature: method=GET op=None",
            response.content.decode(),
        )

    def test_node_init_user_cannot_access(self):
        token = NodeKey.objects.get_token_for_node(factory.make_Node())
        client = MAASSensibleOAuthClient(get_node_init_user(), token)
        response = client.get(reverse("nodes_handler"))
        self.assertEqual(http.client.FORBIDDEN, response.status_code)


class TestNodesAPILoggedIn(APITestCase.ForUserAndAdmin):
    def setUp(self):
        super().setUp()
        self.patch(node_module, "wait_for_power_command")

    def test_nodes_GET_logged_in(self):
        node = factory.make_Node()
        response = self.client.get(reverse("nodes_handler"))
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            [node.system_id],
            [parsed_node.get("system_id") for parsed_node in parsed_result],
        )


class TestNodeAPI(APITestCase.ForUser):
    """Tests for /api/2.0/nodes/<node>/."""

    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/nodes/node-name/",
            reverse("node_handler", args=["node-name"]),
        )

    @staticmethod
    def get_node_uri(node):
        """Get the API URI for `node`."""
        return reverse("node_handler", args=[node.system_id])

    def test_GET_refuses_to_access_nonexistent_node(self):
        # When fetching a Node, the api returns a 'Not Found' (404) error
        # if no node is found.
        url = reverse("node_handler", args=["invalid-uuid"])

        response = self.client.get(url)

        self.assertEqual(http.client.NOT_FOUND, response.status_code)
        self.assertEqual(
            "No Node matches the given query.",
            response.content.decode(settings.DEFAULT_CHARSET),
        )

    def test_GET_returns_404_if_node_name_contains_invalid_characters(self):
        # When the requested name contains characters that are invalid for
        # a hostname, the result of the request is a 404 response.
        url = reverse("node_handler", args=["invalid-uuid-#..."])

        response = self.client.get(url)

        self.assertEqual(http.client.NOT_FOUND, response.status_code)
        self.assertEqual(
            "No Node matches the given query.",
            response.content.decode(settings.DEFAULT_CHARSET),
        )

    def test_resource_uri_points_back_at_machine(self):
        self.become_admin()
        # When a Machine is returned by the API, the field 'resource_uri'
        # provides the URI for this Machine.
        machine = factory.make_Node(
            hostname="diane",
            owner=self.user,
            architecture=make_usable_architecture(self),
        )
        response = self.client.get(self.get_node_uri(machine))
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            reverse("machine_handler", args=[parsed_result["system_id"]]),
            parsed_result["resource_uri"],
        )

    def test_resource_uri_points_back_at_device(self):
        self.become_admin()
        # When a Device is returned by the API, the field 'resource_uri'
        # provides the URI for this Device.
        device = factory.make_Device(hostname="diane", owner=self.user)
        response = self.client.get(self.get_node_uri(device))
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            reverse("device_handler", args=[parsed_result["system_id"]]),
            parsed_result["resource_uri"],
        )

    def test_resource_uri_points_back_at_rack_controller(self):
        self.become_admin()
        # When a RackController is returned by the API, the field
        # 'resource_uri' provides the URI for this RackController.
        rack = factory.make_RackController(hostname="diane", owner=self.user)
        response = self.client.get(self.get_node_uri(rack))
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            reverse(
                "rackcontroller_handler", args=[parsed_result["system_id"]]
            ),
            parsed_result["resource_uri"],
        )

    def test_resource_uri_points_back_at_region_controller(self):
        self.become_admin()
        # When a RegionController is returned by the API, the field
        # 'resource_uri' provides the URI for this RegionController.
        rack = factory.make_RegionController(hostname="diane", owner=self.user)
        response = self.client.get(self.get_node_uri(rack))
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            reverse(
                "regioncontroller_handler", args=[parsed_result["system_id"]]
            ),
            parsed_result["resource_uri"],
        )

    def test_health_status(self):
        self.become_admin()
        machine = factory.make_Machine(owner=self.user)
        commissioning_script_set = factory.make_ScriptSet(
            result_type=RESULT_TYPE.COMMISSIONING, node=machine
        )
        testing_script_set = factory.make_ScriptSet(
            result_type=RESULT_TYPE.TESTING, node=machine
        )
        make_script_result = partial(
            factory.make_ScriptResult,
            script_set=testing_script_set,
            status=factory.pick_choice(
                SCRIPT_STATUS_CHOICES, but_not=[SCRIPT_STATUS.ABORTED]
            ),
        )
        commissioning_script_result = make_script_result(
            script_set=commissioning_script_set,
            script=factory.make_Script(script_type=SCRIPT_TYPE.COMMISSIONING),
        )
        cpu_script_result = make_script_result(
            script=factory.make_Script(
                script_type=SCRIPT_TYPE.TESTING,
                hardware_type=HARDWARE_TYPE.CPU,
            )
        )
        memory_script_result = make_script_result(
            script=factory.make_Script(
                script_type=SCRIPT_TYPE.TESTING,
                hardware_type=HARDWARE_TYPE.MEMORY,
            )
        )
        network_script_result = make_script_result(
            script=factory.make_Script(
                script_type=SCRIPT_TYPE.TESTING,
                hardware_type=HARDWARE_TYPE.NETWORK,
            )
        )
        storage_script_result = make_script_result(
            script=factory.make_Script(
                script_type=SCRIPT_TYPE.TESTING,
                hardware_type=HARDWARE_TYPE.STORAGE,
            )
        )
        node_script_result = make_script_result(
            script=factory.make_Script(
                script_type=SCRIPT_TYPE.TESTING,
                hardware_type=HARDWARE_TYPE.NODE,
            )
        )
        interface_script_result = make_script_result(
            script=factory.make_Script(
                script_type=SCRIPT_TYPE.TESTING,
                hardware_type=HARDWARE_TYPE.NETWORK,
            )
        )
        testing_script_results = (
            machine.get_latest_testing_script_results.exclude(
                status=SCRIPT_STATUS.ABORTED
            )
        )
        testing_status = get_status_from_qs(testing_script_results)

        response = self.client.get(self.get_node_uri(machine))
        parsed_result = json_load_bytes(response.content)

        def status(s):
            return get_status_from_qs([s])

        def status_name(s):
            return SCRIPT_STATUS_CHOICES[status(s)][1]

        self.assertEqual(response.status_code, http.client.OK)
        self.assertEqual(
            status(commissioning_script_result),
            parsed_result["commissioning_status"],
        )
        self.assertEqual(
            status_name(commissioning_script_result),
            parsed_result["commissioning_status_name"],
        )
        self.assertEqual(testing_status, parsed_result["testing_status"])
        self.assertEqual(
            SCRIPT_STATUS_CHOICES[testing_status][1],
            parsed_result["testing_status_name"],
        )
        self.assertEqual(
            status(cpu_script_result), parsed_result["cpu_test_status"]
        )
        self.assertEqual(
            status_name(cpu_script_result),
            parsed_result["cpu_test_status_name"],
        )
        self.assertEqual(
            status(memory_script_result), parsed_result["memory_test_status"]
        )
        self.assertEqual(
            status_name(memory_script_result),
            parsed_result["memory_test_status_name"],
        )
        self.assertEqual(
            status(network_script_result), parsed_result["network_test_status"]
        )
        self.assertEqual(
            status_name(network_script_result),
            parsed_result["network_test_status_name"],
        )
        self.assertEqual(
            status(storage_script_result), parsed_result["storage_test_status"]
        )
        self.assertEqual(
            status_name(storage_script_result),
            parsed_result["storage_test_status_name"],
        )
        self.assertEqual(
            status(node_script_result), parsed_result["other_test_status"]
        )
        self.assertEqual(
            status_name(node_script_result),
            parsed_result["other_test_status_name"],
        )
        self.assertEqual(
            status(interface_script_result),
            parsed_result["interface_test_status"],
        )
        self.assertEqual(
            status_name(interface_script_result),
            parsed_result["interface_test_status_name"],
        )

    def test_hardware_info(self):
        self.become_admin()
        machine = factory.make_Machine(owner=self.user)
        system_vendor = factory.make_NodeMetadata(machine, "system_vendor")
        system_product = factory.make_NodeMetadata(machine, "system_product")
        system_family = factory.make_NodeMetadata(machine, "system_family")
        system_version = factory.make_NodeMetadata(machine, "system_version")
        system_serial = factory.make_NodeMetadata(machine, "system_serial")
        system_sku = factory.make_NodeMetadata(machine, "system_sku")
        cpu_model = factory.make_NodeMetadata(machine, "cpu_model")
        mainboard_vendor = factory.make_NodeMetadata(
            machine, "mainboard_vendor"
        )
        mainboard_product = factory.make_NodeMetadata(
            machine, "mainboard_product"
        )
        mainboard_serial = factory.make_NodeMetadata(
            machine, "mainboard_serial"
        )
        mainboard_version = factory.make_NodeMetadata(
            machine, "mainboard_version"
        )
        mainboard_firmware_vendor = factory.make_NodeMetadata(
            machine, "mainboard_firmware_vendor"
        )
        mainboard_firmware_version = factory.make_NodeMetadata(
            machine, "mainboard_firmware_version"
        )
        mainboard_firmware_date = factory.make_NodeMetadata(
            machine, "mainboard_firmware_date"
        )
        chassis_vendor = factory.make_NodeMetadata(machine, "chassis_vendor")
        chassis_type = factory.make_NodeMetadata(machine, "chassis_type")
        chassis_serial = factory.make_NodeMetadata(machine, "chassis_serial")
        chassis_version = factory.make_NodeMetadata(machine, "chassis_version")
        factory.make_NodeMetadata(machine)

        response = self.client.get(self.get_node_uri(machine))
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(response.status_code, http.client.OK)
        self.assertEqual(
            {
                "system_vendor": system_vendor.value,
                "system_product": system_product.value,
                "system_family": system_family.value,
                "system_version": system_version.value,
                "system_sku": system_sku.value,
                "system_serial": system_serial.value,
                "cpu_model": cpu_model.value,
                "mainboard_vendor": mainboard_vendor.value,
                "mainboard_product": mainboard_product.value,
                "mainboard_serial": mainboard_serial.value,
                "mainboard_version": mainboard_version.value,
                "mainboard_firmware_vendor": mainboard_firmware_vendor.value,
                "mainboard_firmware_version": mainboard_firmware_version.value,
                "mainboard_firmware_date": mainboard_firmware_date.value,
                "chassis_vendor": chassis_vendor.value,
                "chassis_type": chassis_type.value,
                "chassis_serial": chassis_serial.value,
                "chassis_version": chassis_version.value,
            },
            parsed_result["hardware_info"],
        )

    def test_DELETE_deletes_node(self):
        # The api allows to delete a Node.
        self.become_admin()
        node = factory.make_Node(owner=self.user)
        system_id = node.system_id
        response = self.client.delete(self.get_node_uri(node))

        self.assertEqual(204, response.status_code)
        self.assertCountEqual([], Node.objects.filter(system_id=system_id))

    def test_DELETE_deletes_node_fails_if_not_admin(self):
        # Only superusers can delete nodes.
        node = factory.make_Node(owner=self.user)
        response = self.client.delete(self.get_node_uri(node))

        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_DELETE_forbidden_without_edit_permission(self):
        # A user without the edit permission cannot delete a Node.
        node = factory.make_Node()
        response = self.client.delete(self.get_node_uri(node))

        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_DELETE_refuses_to_delete_invisible_node(self):
        # The request to delete a single node is denied if the node isn't
        # visible by the user.
        other_node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User()
        )

        response = self.client.delete(self.get_node_uri(other_node))

        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_DELETE_refuses_to_delete_nonexistent_node(self):
        # When deleting a Node, the api returns a 'Not Found' (404) error
        # if no node is found.
        url = reverse("node_handler", args=["invalid-uuid"])
        response = self.client.delete(url)

        self.assertEqual(http.client.NOT_FOUND, response.status_code)

    def test_CREATE_disabled(self):
        response = self.client.post(
            reverse("node_handler", args=["invalid-uuid"]), {}
        )
        self.assertEqual(http.client.METHOD_NOT_ALLOWED, response.status_code)

    def test_UPDATE_disabled(self):
        machine = factory.make_Node(
            owner=self.user, architecture=make_usable_architecture(self)
        )
        response = self.client.put(
            self.get_node_uri(machine), {"hostname": "francis"}
        )
        self.assertEqual(http.client.METHOD_NOT_ALLOWED, response.status_code)


class TestGetDetails(APITestCase.ForUser):
    """Tests for /api/2.0/nodes/<node>/?op=details."""

    def make_script_result(self, node, script_result=0, script_name=None):
        script_set = node.current_commissioning_script_set
        if script_set is None:
            script_set = factory.make_ScriptSet(
                node=node, result_type=RESULT_TYPE.COMMISSIONING
            )
            node.current_commissioning_script_set = script_set
            node.save()
        if script_result == 0:
            status = SCRIPT_STATUS.PASSED
        else:
            status = SCRIPT_STATUS.FAILED
        return factory.make_ScriptResult(
            script_set=script_set,
            status=status,
            exit_status=script_result,
            script_name=script_name,
        )

    def make_lshw_result(self, node, script_result=0):
        return self.make_script_result(node, script_result, LSHW_OUTPUT_NAME)

    def make_lldp_result(self, node, script_result=0):
        return self.make_script_result(node, script_result, LLDP_OUTPUT_NAME)

    def get_details(self, node):
        url = reverse("node_handler", args=[node.system_id])
        response = self.client.get(url, {"op": "details"})
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual("application/bson", response["content-type"])
        return bson.BSON(response.content).decode()

    def test_GET_returns_empty_details_when_there_are_none(self):
        node = factory.make_Node()
        self.assertDictEqual(
            {"lshw": None, "lldp": None}, self.get_details(node)
        )

    def test_GET_returns_all_details(self):
        node = factory.make_Node()
        lshw_result = self.make_lshw_result(node)
        lldp_result = self.make_lldp_result(node)
        self.assertDictEqual(
            {"lshw": lshw_result.stdout, "lldp": lldp_result.stdout},
            self.get_details(node),
        )

    def test_GET_returns_only_those_details_that_exist(self):
        node = factory.make_Node()
        lshw_result = self.make_lshw_result(node)
        self.assertDictEqual(
            {"lshw": lshw_result.stdout, "lldp": None}, self.get_details(node)
        )

    def test_GET_returns_not_found_when_node_does_not_exist(self):
        url = reverse("node_handler", args=["does-not-exist"])
        response = self.client.get(url, {"op": "details"})
        self.assertEqual(http.client.NOT_FOUND, response.status_code)

    def test_GET_returns_all_details_for_administrator(self):
        self.become_admin()
        node = factory.make_Node(owner=factory.make_User())
        lshw_result = self.make_lshw_result(node)
        lldp_result = self.make_lldp_result(node)
        self.assertDictEqual(
            {"lshw": lshw_result.stdout, "lldp": lldp_result.stdout},
            self.get_details(node),
        )

    def test_GET_returns_forbidden_for_non_owned_nodes(self):
        node = factory.make_Node(owner=factory.make_User())
        url = reverse("node_handler", args=[node.system_id])
        response = self.client.get(url, {"op": "details"})
        self.assertEqual(http.client.FORBIDDEN, response.status_code)


class TestPowerParameters(APITestCase.ForUser):
    def get_node_uri(self, node):
        """Get the API URI for `node`."""
        return reverse("node_handler", args=[node.system_id])

    def test_get_power_parameters_superuser(self):
        self.become_admin()
        power_parameters = {factory.make_string(): factory.make_string()}
        node = factory.make_Node(power_parameters=power_parameters)
        response = self.client.get(
            self.get_node_uri(node), {"op": "power_parameters"}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_params = json_load_bytes(response.content)
        self.assertEqual(node.get_power_parameters(), parsed_params)

    def test_get_power_parameters_user(self):
        power_parameters = {factory.make_string(): factory.make_string()}
        node = factory.make_Node(power_parameters=power_parameters)
        response = self.client.get(
            self.get_node_uri(node), {"op": "power_parameters"}
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_get_power_parameters_rbac_pool_admin(self):
        self.patch(auth, "validate_user_external_auth").return_value = True
        rbac = self.useFixture(RBACEnabled())
        self.become_non_local()
        power_parameters = {factory.make_string(): factory.make_string()}
        node = factory.make_Machine(power_parameters=power_parameters)
        rbac.store.add_pool(node.pool)
        rbac.store.allow(self.user.username, node.pool, "admin-machines")
        response = self.client.get(
            self.get_node_uri(node), {"op": "power_parameters"}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_params = json_load_bytes(response.content)
        self.assertEqual(node.get_power_parameters(), parsed_params)

    def test_get_power_parameters_rbac_pool_user(self):
        self.patch(auth, "validate_user_external_auth").return_value = True
        rbac = self.useFixture(RBACEnabled())
        self.become_non_local()
        power_parameters = {factory.make_string(): factory.make_string()}
        node = factory.make_Machine(power_parameters=power_parameters)
        rbac.store.add_pool(node.pool)
        rbac.store.allow(self.user.username, node.pool, "view")
        rbac.store.allow(self.user.username, node.pool, "deploy-machines")
        response = self.client.get(
            self.get_node_uri(node), {"op": "power_parameters"}
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_get_power_parameters_empty(self):
        self.become_admin()
        node = factory.make_Node()
        response = self.client.get(
            self.get_node_uri(node), {"op": "power_parameters"}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_params = json_load_bytes(response.content)
        self.assertEqual(node.get_power_parameters(), parsed_params)

    def test_get_power_parameters_view_lock(self):
        self.become_admin()
        power_parameters = {factory.make_string(): factory.make_string()}
        node = factory.make_Node(
            owner=self.user, power_parameters=power_parameters, locked=True
        )
        response = self.client.get(
            self.get_node_uri(node), {"op": "power_parameters"}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_params = json_load_bytes(response.content)
        self.assertEqual(node.get_power_parameters(), parsed_params)


class TestSetWorkloadAnnotations(APITestCase.ForUser):
    scenarios = (
        (
            "machine",
            {"handler": "machine_handler", "maker": factory.make_Node},
        ),
        (
            "device",
            {"handler": "device_handler", "maker": factory.make_Device},
        ),
    )

    def get_node_uri(self, node):
        """Get the API URI for `node`."""
        return reverse(self.handler, args=[node.system_id])

    def test_must_be_owned(self):
        node = self.maker(status=NODE_STATUS.READY)
        params = {
            factory.make_name("key"): factory.make_name("value")
            for _ in range(3)
        }
        params["op"] = "set_workload_annotations"
        response = self.client.post(self.get_node_uri(node), params)
        self.assertEqual(http.client.CONFLICT, response.status_code)

    def test_adds_data(self):
        node = self.maker(status=NODE_STATUS.ALLOCATED, owner=self.user)
        annotations = {
            factory.make_name("key"): factory.make_name("value")
            for _ in range(3)
        }
        params = annotations.copy()
        params["op"] = "set_workload_annotations"
        response = self.client.post(self.get_node_uri(node), params)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            json_load_bytes(response.content)["workload_annotations"],
            annotations,
        )

    def test_updates_data(self):
        annotations = {
            factory.make_name("key"): factory.make_name("value")
            for _ in range(3)
        }
        node = self.maker(
            status=NODE_STATUS.ALLOCATED,
            owner=self.user,
            owner_data=annotations,
        )
        for key in annotations:
            annotations[key] = factory.make_name("value")
        params = annotations.copy()
        params["op"] = "set_workload_annotations"
        response = self.client.post(self.get_node_uri(node), params)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            json_load_bytes(response.content)["workload_annotations"],
            annotations,
        )

    def test_removes_data(self):
        annotations = {
            factory.make_name("key"): factory.make_name("value")
            for _ in range(3)
        }
        node = self.maker(
            status=NODE_STATUS.ALLOCATED,
            owner=self.user,
            owner_data=annotations,
        )
        for key in annotations:
            annotations[key] = ""
        params = annotations.copy()
        params["op"] = "set_workload_annotations"
        response = self.client.post(self.get_node_uri(node), params)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            json_load_bytes(response.content)["workload_annotations"],
            {},
        )


class TestSetOwnerData(APITestCase.ForUser):
    def get_node_uri(self, node):
        """Get the API URI for `node`."""
        return reverse("machine_handler", args=[node.system_id])

    def test_adds_data(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=self.user)
        owner_data = {
            factory.make_name("key"): factory.make_name("value")
            for _ in range(3)
        }
        params = owner_data.copy()
        params["op"] = "set_owner_data"
        response = self.client.post(self.get_node_uri(node), params)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            json_load_bytes(response.content)["owner_data"],
            owner_data,
        )


class TestPowerMixin(APITestCase.ForUser):
    """Test the power mixin."""

    def setUp(self):
        super().setUp()
        commissioning_osystem = Config.objects.get_config(
            name="commissioning_osystem"
        )
        commissioning_series = Config.objects.get_config(
            name="commissioning_distro_series"
        )
        self.patch(osystems, "list_all_usable_osystems").return_value = [
            {
                "name": commissioning_osystem,
                "releases": [{"name": commissioning_series}],
            }
        ]

    def get_node_uri(self, node):
        """Get the API URI for `node`."""
        # Use the machine handler to test as that will always support all
        # power commands
        return reverse("machine_handler", args=[node.system_id])

    def test_POST_power_off_checks_permission(self):
        machine = factory.make_Node(owner=factory.make_User())
        machine_stop = self.patch(machine, "stop")
        response = self.client.post(
            self.get_node_uri(machine), {"op": "power_off"}
        )
        self.assertEqual(http.client.FORBIDDEN, response.status_code)
        machine_stop.assert_not_called()

    def test_POST_power_off_returns_nothing_if_machine_was_not_stopped(self):
        # The machine may not be stopped because, for example, its power type
        # does not support it. In this case the machine is not returned to the
        # caller.
        machine = factory.make_Node(owner=self.user)
        machine_stop = self.patch(node_module.Machine, "stop")
        machine_stop.return_value = False
        response = self.client.post(
            self.get_node_uri(machine), {"op": "power_off"}
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertIsNone(json_load_bytes(response.content))
        machine_stop.mock_called_once_with(ANY, stop_mode=ANY, comment=None)

    def test_POST_power_off_returns_machine(self):
        machine = factory.make_Node(owner=self.user)
        self.patch(node_module.Machine, "stop").return_value = True
        response = self.client.post(
            self.get_node_uri(machine), {"op": "power_off"}
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            machine.system_id, json_load_bytes(response.content)["system_id"]
        )

    def test_POST_power_off_may_be_repeated(self):
        machine = factory.make_Node(
            owner=self.user, interface=True, power_type="manual"
        )
        self.patch(machine, "stop")
        self.client.post(self.get_node_uri(machine), {"op": "power_off"})
        response = self.client.post(
            self.get_node_uri(machine), {"op": "power_off"}
        )
        self.assertEqual(http.client.OK, response.status_code)

    def test_POST_power_off_power_offs_machines(self):
        machine = factory.make_Node(owner=self.user)
        machine_stop = self.patch(node_module.Machine, "stop")
        stop_mode = factory.make_name("stop_mode")
        comment = factory.make_name("comment")
        self.client.post(
            self.get_node_uri(machine),
            {"op": "power_off", "stop_mode": stop_mode, "comment": comment},
        )
        machine_stop.mock_called_once_with(
            self.user, stop_mode=stop_mode, comment=comment
        )

    def test_POST_power_off_handles_missing_comment(self):
        machine = factory.make_Node(owner=self.user)
        machine_stop = self.patch(node_module.Machine, "stop")
        stop_mode = factory.make_name("stop_mode")
        self.client.post(
            self.get_node_uri(machine),
            {"op": "power_off", "stop_mode": stop_mode},
        )
        machine_stop.mock_called_once_with(
            self.user, stop_mode=stop_mode, comment=None
        )

    def test_POST_power_off_returns_503_when_power_already_in_progress(self):
        machine = factory.make_Node(owner=self.user)
        exc_text = factory.make_name("exc_text")
        self.patch(node_module.Machine, "stop").side_effect = (
            PowerActionAlreadyInProgress(exc_text)
        )
        response = self.client.post(
            self.get_node_uri(machine), {"op": "power_off"}
        )
        self.assertEqual(response.status_code, http.client.SERVICE_UNAVAILABLE)
        self.assertIn(
            exc_text, response.content.decode(settings.DEFAULT_CHARSET)
        )

    def test_POST_power_on_checks_permission(self):
        machine = factory.make_Node_with_Interface_on_Subnet(
            owner=factory.make_User()
        )
        response = self.client.post(
            self.get_node_uri(machine), {"op": "power_on"}
        )
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_POST_power_on_checks_ownership(self):
        self.become_admin()
        machine = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY
        )
        response = self.client.post(
            self.get_node_uri(machine), {"op": "power_on"}
        )
        self.assertEqual(http.client.CONFLICT, response.status_code)
        self.assertEqual(
            "Can't start node: it hasn't been allocated.",
            response.content.decode(settings.DEFAULT_CHARSET),
        )

    def test_POST_power_on_returns_machine(self):
        self.patch(node_module.Machine, "_start")
        machine = factory.make_Node(
            owner=self.user,
            interface=True,
            power_type="manual",
            architecture=make_usable_architecture(self),
        )
        osystem, releases = make_usable_osystem(self)
        distro_series = releases[0]
        response = self.client.post(
            self.get_node_uri(machine),
            {"op": "power_on", "distro_series": distro_series},
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            machine.system_id, json_load_bytes(response.content)["system_id"]
        )

    def test_query_power_state(self):
        node = factory.make_Node()
        mock__power_control_node = self.patch(
            node_module.Node, "power_query"
        ).return_value
        mock__power_control_node.wait = Mock(return_value=POWER_STATE.ON)
        response = self.client.get(
            self.get_node_uri(node), {"op": "query_power_state"}
        )
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(POWER_STATE.ON, parsed_result["state"])

    def test_POST_test_tests_machine(self):
        self.patch(node_module.Machine, "_start").return_value = succeed(None)
        factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING, tags=["commissioning"]
        )
        self.patch(node_module.Node, "_power_control_node").return_value = (
            succeed(None)
        )
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYED,
            owner=factory.make_User(),
            interface=True,
        )
        self.become_admin()
        response = self.client.post(self.get_node_uri(node), {"op": "test"})
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(NODE_STATUS.TESTING, reload_object(node).status)

    def test_POST_test_tests_machine_with_options(self):
        self.patch(node_module.Machine, "_start").return_value = succeed(None)
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYED,
            owner=factory.make_User(),
            interface=True,
        )
        self.become_admin()

        testing_scripts = [
            factory.make_Script(script_type=SCRIPT_TYPE.TESTING)
            for _ in range(10)
        ]
        testing_script_selected_by_tag = random.choice(testing_scripts)
        testing_script_selected_by_name = random.choice(testing_scripts)
        expected_testing_scripts = [
            testing_script_selected_by_tag.name,
            testing_script_selected_by_name.name,
        ]

        response = self.client.post(
            self.get_node_uri(node),
            {
                "op": "test",
                "enable_ssh": "true",
                "testing_scripts": ",".join(
                    [
                        random.choice(
                            [
                                tag
                                for tag in testing_script_selected_by_tag.tags
                                if "tag" in tag
                            ]
                        ),
                        testing_script_selected_by_name.name,
                    ]
                ),
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        node = reload_object(node)
        testing_script_set = node.current_testing_script_set
        self.assertTrue(node.enable_ssh)
        self.assertEqual(
            set(expected_testing_scripts),
            {script_result.name for script_result in testing_script_set},
        )

    def test_POST_test_tests_machine_errors_on_no_scripts_found(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYED,
            owner=factory.make_User(),
            interface=True,
        )
        self.become_admin()
        response = self.client.post(self.get_node_uri(node), {"op": "test"})
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertEqual(b"No testing scripts found!", response.content)

    def test_POST_test_tests_machine_errors_on_bad_form_data(self):
        node = factory.make_Node(
            status=NODE_STATUS.NEW, owner=factory.make_User()
        )
        self.become_admin()
        response = self.client.post(self.get_node_uri(node), {"op": "test"})
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)

    def test_POST_test_deletes_scriptset_on_failure(self):
        node = factory.make_Node(
            status=NODE_STATUS.READY,
            owner=factory.make_User(),
            interface=True,
        )
        script = factory.make_Script(
            script_type=SCRIPT_TYPE.TESTING,
            parameters={"interface": {"type": "interface"}},
        )
        self.become_admin()
        response = self.client.post(
            self.get_node_uri(node),
            {"op": "test", "testing_scripts": script.name},
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertEqual(
            b"An interface must be configured to run network testing!",
            response.content,
        )
        self.assertFalse(node.scriptset_set.exists())

    def test_POST_override_failed_testing(self):
        node = factory.make_Node(
            status=NODE_STATUS.FAILED_TESTING,
            owner=factory.make_User(),
            osystem="",
        )
        self.become_admin()
        response = self.client.post(
            self.get_node_uri(node), {"op": "override_failed_testing"}
        )
        self.assertEqual(response.status_code, http.client.OK)
        node = reload_object(node)
        self.assertEqual(NODE_STATUS.READY, node.status)

    def test_abort_fails_for_unsupported_operation(self):
        status = factory.pick_choice(
            NODE_STATUS_CHOICES,
            but_not=[
                NODE_STATUS.DISK_ERASING,
                NODE_STATUS.COMMISSIONING,
                NODE_STATUS.DEPLOYING,
                NODE_STATUS.TESTING,
            ],
        )
        node = factory.make_Node(status=status)
        response = self.client.post(self.get_node_uri(node), {"op": "abort"})
        self.assertEqual(http.client.CONFLICT, response.status_code)

    def test_abort_passes_comment(self):
        self.become_admin()
        node = factory.make_Node(
            status=NODE_STATUS.DISK_ERASING, owner=self.user
        )
        node_method = self.patch(node_module.Node, "abort_operation")
        comment = factory.make_name("comment")
        self.client.post(
            self.get_node_uri(node), {"op": "abort", "comment": comment}
        )
        node_method.mock_called_once_with(self.user, comment)

    def test_abort_handles_missing_comment(self):
        self.become_admin()
        node = factory.make_Node(
            status=NODE_STATUS.DISK_ERASING, owner=self.user
        )
        node_method = self.patch(node_module.Node, "abort_operation")
        self.client.post(self.get_node_uri(node), {"op": "abort"})
        node_method.mock_called_once_with(self.user, None)
