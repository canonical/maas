# Copyright 2015-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import http.client
import json
import random

from django.conf import settings
from django.test import RequestFactory
from django.urls import reverse
from twisted.internet.defer import succeed

from maasserver import eventloop
from maasserver.api import auth
from maasserver.api import machines as machines_module
from maasserver.api.machines import AllocationOptions, get_allocation_options
from maasserver.enum import BMC_TYPE, BRIDGE_TYPE, INTERFACE_TYPE, NODE_STATUS
import maasserver.forms as forms_module
from maasserver.forms.pods import ComposeMachineForm, ComposeMachineForPodsForm
from maasserver.models import Config, Domain, Machine, Node, ScriptSet
from maasserver.models import node as node_module
from maasserver.models.node import RELEASABLE_STATUSES
from maasserver.node_constraint_filter_forms import AcquireNodeForm
from maasserver.testing.api import APITestCase, APITransactionTestCase
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.eventloop import (
    RegionEventLoopFixture,
    RunningEventLoopFixture,
)
from maasserver.testing.factory import factory
from maasserver.testing.fixtures import RBACEnabled
from maasserver.testing.osystems import make_usable_osystem
from maasserver.testing.testclient import MAASSensibleOAuthClient
from maasserver.utils.orm import post_commit_hooks, reload_object
from maastesting.djangotestcase import CountQueries
from maastesting.testcase import MAASTestCase
from metadataserver.enum import SCRIPT_TYPE
from provisioningserver.enum import POWER_STATE
from provisioningserver.utils.enum import map_enum


class TestGetStorageLayoutParams(MAASTestCase):
    def test_sets_request_data_to_mutable(self):
        data = {"op": "allocate", "storage_layout": "flat"}
        request = RequestFactory().post(reverse("machines_handler"), data)
        request.data = request.POST.copy()
        request.data._mutable = False
        machines_module.get_storage_layout_params(request)
        self.assertTrue(request.data._mutable)


class TestMachineHostname(APITestCase.ForUserAndAdmin):
    def test_GET_returns_fqdn_with_domain_name_from_node(self):
        # If DNS management is enabled, the domain part of a hostname
        # still comes from the node.
        hostname = factory.make_name("hostname")
        domainname = factory.make_name("domain")
        domain, _ = Domain.objects.get_or_create(
            name=domainname, defaults={"authoritative": True}
        )
        factory.make_Node(hostname=hostname, domain=domain)
        fqdn = f"{hostname}.{domainname}"
        response = self.client.get(reverse("machines_handler"))
        self.assertEqual(
            http.client.OK.value, response.status_code, response.content
        )
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(
            [fqdn], [machine.get("fqdn") for machine in parsed_result]
        )


class TestMachineWorkloadAnnotations(APITestCase.ForUser):
    def test_GET_returns_workload_annotations(self):
        owner_data = {factory.make_name("key"): factory.make_name("value")}
        factory.make_Node(owner_data=owner_data)
        response = self.client.get(reverse("machines_handler"))
        self.assertEqual(
            http.client.OK.value, response.status_code, response.content
        )
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(
            [machine.get("owner_data") for machine in parsed_result],
            [owner_data],
        )
        self.assertEqual(
            [machine.get("workload_annotations") for machine in parsed_result],
            [owner_data],
        )


def extract_system_ids(parsed_result):
    """List the system_ids of the machines in `parsed_result`."""
    return [machine.get("system_id") for machine in parsed_result]


def extract_system_ids_from_machines(machines):
    return [machine.system_id for machine in machines]


class TestMachinesAPI(APITestCase.ForUser):
    """Tests for /api/2.0/machines/."""

    # XXX: GavinPanella 2016-05-24 bug=1585138: op=list_allocated does not
    # work for clients authenticated via username and password.
    clientfactories = {"oauth": MAASSensibleOAuthClient}

    def setUp(self):
        super().setUp()
        self.machines_url = reverse("machines_handler")
        self.patch(node_module, "stop_workflow")

    def get_json(self, *args, **kwargs):
        """Call the handler, and get the JSON response"""
        return self.client.get(self.machines_url, *args, **kwargs).json()

    def test_handler_path(self):
        self.assertEqual("/MAAS/api/2.0/machines/", self.machines_url)

    def test_GET_includes_virtualmachine_id(self):
        vmhost = factory.make_BMC(bmc_type=BMC_TYPE.POD)
        machine1 = factory.make_Node(bmc=vmhost)
        vm1 = factory.make_VirtualMachine(machine=machine1, bmc=vmhost)
        machine2 = factory.make_Node()
        parsed_result = self.get_json()
        result = list(
            (entry["system_id"], entry["virtualmachine_id"])
            for entry in parsed_result
        )
        self.assertCountEqual(
            result,
            [(machine1.system_id, vm1.id), (machine2.system_id, None)],
        )

    def test_GET_includes_error_description(self):
        factory.make_Node(
            status=NODE_STATUS.BROKEN,
            ephemeral_deploy=True,
            error_description="my error",
        )
        parsed_result = self.get_json()
        self.assertEquals(parsed_result[0]["error_description"], "my error")

    def test_POST_creates_machine(self):
        # The API allows a non-admin logged-in user to create a Machine.
        hostname = factory.make_name("host")
        architecture = make_usable_architecture(self)
        macs = {
            factory.make_mac_address() for _ in range(random.randint(1, 2))
        }
        response = self.client.post(
            self.machines_url,
            {
                "hostname": hostname,
                "architecture": architecture,
                "mac_addresses": macs,
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        system_id = response.json()["system_id"]
        machine = Machine.objects.get(system_id=system_id)
        self.assertEqual(machine.hostname, hostname)
        self.assertEqual(machine.architecture, architecture)
        self.assertEqual(
            {
                nic.mac_address
                for nic in machine.current_config.interface_set.all()
            },
            macs,
        )

    def test_POST_creates_ipmi_machine_sets_workaround_flags(self):
        make_usable_architecture(self)
        hostname = factory.make_name("host")
        macs = {
            factory.make_mac_address() for _ in range(random.randint(1, 2))
        }
        power_address = factory.make_ip_address()
        workaround_flags = ["authcap"]
        response = self.client.post(
            self.machines_url,
            {
                "hostname": hostname,
                "mac_addresses": macs,
                "power_type": "ipmi",
                "power_parameters_power_address": power_address,
                "power_parameters_workaround_flags": workaround_flags,
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        system_id = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )["system_id"]
        machine = Machine.objects.get(system_id=system_id)
        self.assertEqual(machine.hostname, hostname)
        self.assertCountEqual(
            workaround_flags,
            machine.get_power_parameters()["workaround_flags"],
        )

    def test_POST_creates_ipmi_machine_sets_mac_addresses_empty_no_arch(self):
        make_usable_architecture(self)
        hostname = factory.make_name("host")
        macs = {
            factory.make_mac_address() for _ in range(random.randint(1, 2))
        }
        power_address = factory.make_ip_address()
        response = self.client.post(
            self.machines_url,
            {
                "hostname": hostname,
                "mac_addresses": macs,
                "power_type": "ipmi",
                "power_parameters_power_address": power_address,
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        system_id = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )["system_id"]
        machine = Machine.objects.get(system_id=system_id)
        self.assertEqual(machine.hostname, hostname)
        self.assertEqual(
            {
                nic.mac_address
                for nic in machine.current_config.interface_set.all()
            },
            set(),
        )
        self.assertEqual(
            power_address, machine.get_power_parameters()["power_address"]
        )

    def test_POST_when_logged_in_creates_machine_in_declared_state(self):
        # When a user enlists a machine, it goes into the New state.
        # This will change once we start doing proper commissioning.
        response = self.client.post(
            self.machines_url,
            {
                "hostname": factory.make_name("host"),
                "architecture": make_usable_architecture(self),
                "mac_addresses": [factory.make_mac_address()],
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        system_id = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )["system_id"]
        self.assertEqual(
            NODE_STATUS.NEW, Node.objects.get(system_id=system_id).status
        )

    def test_POST_when_logged_in_creates_deployed_machine(self):
        self.become_admin()
        response = self.client.post(
            self.machines_url,
            {
                "deployed": True,
                "hostname": factory.make_name("host"),
                "architecture": make_usable_architecture(self),
                "mac_addresses": [factory.make_mac_address()],
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        system_id = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )["system_id"]
        node = Node.objects.get(system_id=system_id)
        self.assertEqual(NODE_STATUS.DEPLOYED, node.status)
        self.assertEqual(self.user, node.owner)

    def test_POST_new_when_no_RPC_to_rack_defaults_empty_power(self):
        # Test for bug 1305061, if there is no cluster RPC connection
        # then make sure that power_type is defaulted to the empty
        # string rather than being entirely absent, which results in a
        # crash.
        self.become_admin()
        # The patching behind the scenes to avoid *real* RPC is
        # complex and the available power types is actually a
        # valid set, so use an invalid type to trigger the bug here.
        power_type = factory.make_name("power_type")
        response = self.client.post(
            self.machines_url,
            {
                "architecture": make_usable_architecture(self),
                "mac_addresses": ["aa:bb:cc:dd:ee:ff"],
                "power_type": power_type,
            },
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        validation_errors = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )["power_type"]
        self.assertEqual(
            "Select a valid choice. %s is not one of the "
            "available choices." % power_type,
            validation_errors[0],
        )

    def test_POST_new_handles_empty_str_power_parameters(self):
        # Regression test for LP:1636858
        response = self.client.post(
            self.machines_url,
            {
                "architecture": make_usable_architecture(self),
                "mac_addresses": ["aa:bb:cc:dd:ee:ff"],
                "power_type": "",
                "power_parameters": "",
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        system_id = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )["system_id"]
        machine = Machine.objects.get(system_id=system_id)
        self.assertEqual("", machine.power_type)
        self.assertEqual({}, machine.get_power_parameters())

    def test_POST_handles_error_when_unable_to_access_bmc(self):
        # Regression test for LP1600328
        self.patch(Machine, "_start").return_value = None
        make_usable_osystem(self)
        self.become_admin()
        power_address = factory.make_ip_address()
        power_id = factory.make_name("power_id")
        response = self.client.post(
            self.machines_url,
            {
                "architecture": make_usable_architecture(self),
                "mac_addresses": ["aa:bb:cc:dd:ee:ff"],
                "power_type": "virsh",
                "power_parameters_power_address": power_address,
                "power_parameters_power_id": power_id,
            },
        )
        parsed_result = response.json()
        machine = Machine.objects.get(system_id=parsed_result["system_id"])
        self.assertEqual("virsh", parsed_result["power_type"])
        self.assertEqual(
            power_address, machine.get_power_parameters()["power_address"]
        )
        self.assertEqual(power_id, machine.get_power_parameters()["power_id"])

    def test_POST_sets_description(self):
        # Regression test for LP1707562
        self.become_admin()
        self.patch(Machine, "_start").return_value = None
        make_usable_osystem(self)
        power_address = factory.make_ip_address()
        power_id = factory.make_name("power_id")
        description = factory.make_name("description")
        response = self.client.post(
            self.machines_url,
            {
                "architecture": make_usable_architecture(self),
                "mac_addresses": ["aa:bb:cc:dd:ee:ff"],
                "power_type": "virsh",
                "power_parameters_power_address": power_address,
                "power_parameters_power_id": power_id,
                "description": description,
            },
        )
        parsed_result = response.json()
        self.assertEqual(NODE_STATUS.COMMISSIONING, parsed_result["status"])
        self.assertEqual(description, parsed_result["description"])

    def test_POST_starts_commissioning_with_selected_test_scripts(self):
        # Regression test for LP1707562
        self.become_admin()
        self.patch(Machine, "_start").return_value = None
        make_usable_osystem(self)
        power_address = factory.make_ip_address()
        power_id = factory.make_name("power_id")
        test_script = factory.make_Script(script_type=SCRIPT_TYPE.TESTING)
        response = self.client.post(
            self.machines_url,
            {
                "architecture": make_usable_architecture(self),
                "mac_addresses": ["aa:bb:cc:dd:ee:ff"],
                "power_type": "virsh",
                "power_parameters_power_address": power_address,
                "power_parameters_power_id": power_id,
                "testing_scripts": test_script.name,
            },
        )
        parsed_result = response.json()
        self.assertEqual(NODE_STATUS.COMMISSIONING, parsed_result["status"])
        script_set = ScriptSet.objects.get(
            id=parsed_result["current_testing_result_id"]
        )
        self.assertEqual(
            [test_script.name],
            [script_result.name for script_result in script_set],
        )

    def test_POST_commission_true(self):
        # Regression test for LP:1904398
        self.become_admin()
        self.patch(Machine, "_start").return_value = None
        make_usable_osystem(self)
        response = self.client.post(
            self.machines_url,
            {
                "architecture": make_usable_architecture(self),
                "mac_addresses": ["aa:bb:cc:dd:ee:ff"],
                "power_type": "manual",
                "commission": True,
            },
        )
        parsed_result = response.json()
        self.assertEqual(NODE_STATUS.COMMISSIONING, parsed_result["status"])

    def test_POST_commission_false(self):
        # Regression test for LP:1904398
        self.become_admin()
        make_usable_osystem(self)
        response = self.client.post(
            self.machines_url,
            {
                "architecture": make_usable_architecture(self),
                "mac_addresses": ["aa:bb:cc:dd:ee:ff"],
                "power_type": "manual",
                "commission": False,
            },
        )
        parsed_result = response.json()
        self.assertEqual(NODE_STATUS.NEW, parsed_result["status"])

    def test_GET_lists_machines(self):
        # The api allows for fetching the list of Machines.
        machine1 = factory.make_Node()
        machine2 = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.user
        )
        parsed_result = self.get_json()

        self.assertCountEqual(
            [machine1.system_id, machine2.system_id],
            extract_system_ids(parsed_result),
        )

    def test_GET_includes_numa_nodes(self):
        machine = factory.make_Node()
        factory.make_NUMANode(node=machine, memory=2048 * 1024, cores=[0, 1])
        factory.make_NUMANode(node=machine, memory=4096 * 1024, cores=[2, 3])
        [parsed_result] = self.get_json()
        self.assertCountEqual(
            parsed_result["numanode_set"],
            [
                {"index": 0, "memory": 0, "cores": [], "hugepages_set": []},
                {
                    "index": 1,
                    "memory": 2048 * 1024,
                    "cores": [0, 1],
                    "hugepages_set": [],
                },
                {
                    "index": 2,
                    "memory": 4096 * 1024,
                    "cores": [2, 3],
                    "hugepages_set": [],
                },
            ],
        )

    def test_GET_includes_numa_nodes_hugepages(self):
        machine = factory.make_Node()
        hugepages = factory.make_NUMANodeHugepages(
            numa_node=machine.default_numanode
        )
        [parsed_result] = self.get_json()
        self.assertEqual(
            parsed_result["numanode_set"][0]["hugepages_set"],
            [
                {
                    "page_size": hugepages.page_size,
                    "total": hugepages.total,
                },
            ],
        )

    def test_GET_returns_pod_for_machine_in_pod(self):
        pod = factory.make_Pod()
        machine = factory.make_Node()
        machine.bmc = pod
        machine.save()
        parsed_result = self.get_json()
        self.assertEqual(
            {
                "id": pod.id,
                "name": pod.name,
                "resource_uri": reverse("pod_handler", kwargs={"id": pod.id}),
            },
            parsed_result[0]["pod"],
        )

    def test_GET_doesnt_return_pod_for_machine_without_bmc(self):
        factory.make_Node()
        parsed_result = self.get_json()
        self.assertIsNone(parsed_result[0]["pod"])

    def test_GET_doesnt_return_pod_for_machine_without_pod(self):
        factory.make_Node(bmc=factory.make_BMC())
        parsed_result = self.get_json()
        self.assertIsNone(parsed_result[0]["pod"])

    def test_GET_machines_issues_linear_number_of_queries(self):
        queries_count = []
        machines_count = []

        def exec_request():
            with CountQueries(reset=True) as counter:
                result = self.get_json()
            queries_count.append(counter.count)
            machines_count.append(len(result))

        vlan = factory.make_VLAN(space=factory.make_Space())
        node = factory.make_Node_with_Interface_on_Subnet(vlan=vlan)
        factory.make_VirtualBlockDevice(node=node)
        exec_request()

        node = factory.make_Node_with_Interface_on_Subnet(vlan=vlan)
        factory.make_VirtualBlockDevice(node=node)
        exec_request()

        node = factory.make_Node_with_Interface_on_Subnet(vlan=vlan)
        factory.make_VirtualBlockDevice(node=node)
        exec_request()

        expected_counts = [1, 2, 3]
        self.assertEqual(machines_count, expected_counts)
        # TODO: this should be 94. Update this when we will be able to count also the queries made by the service layer.
        base_count = 93
        for idx, machine_count in enumerate(machines_count):
            self.assertEqual(
                queries_count[idx], base_count + (machine_count * 7)
            )

    def test_GET_without_machines_returns_empty_list(self):
        # If there are no machines to list, the "read" op still works but
        # returns an empty list.
        self.assertEqual([], self.get_json())

    def test_GET_orders_by_id(self):
        # Machines are returned in id order.
        machines = [factory.make_Node() for counter in range(3)]
        parsed_result = self.get_json()
        self.assertEqual(
            [machine.system_id for machine in machines],
            extract_system_ids(parsed_result),
        )

    def test_GET_with_id_returns_matching_machines(self):
        # The "read" operation takes optional "id" parameters.  Only
        # machines with matching ids will be returned.
        ids = [factory.make_Node().system_id for counter in range(3)]
        matching_id = ids[0]
        parsed_result = self.get_json({"id": [matching_id]})
        self.assertEqual([matching_id], extract_system_ids(parsed_result))

    def test_GET_with_nonexistent_id_returns_empty_list(self):
        # Trying to list a nonexistent machine id returns a list containing
        # no machines -- even if other (non-matching) machines exist.
        existing_id = factory.make_Node().system_id
        nonexistent_id = existing_id + factory.make_string()
        response = self.get_json({"id": [nonexistent_id]})
        self.assertEqual([], response)

    def test_GET_with_ids_orders_by_id(self):
        # Even when ids are passed to "list," machines are returned in id
        # order, not necessarily in the order of the id arguments.
        ids = [factory.make_Node().system_id for counter in range(3)]
        parsed_result = self.get_json({"id": list(reversed(ids))})
        self.assertEqual(ids, extract_system_ids(parsed_result))

    def test_GET_with_some_matching_ids_returns_matching_machines(self):
        # If some machines match the requested ids and some don't, only the
        # matching ones are returned.
        existing_id = factory.make_Node().system_id
        nonexistent_id = existing_id + factory.make_string()
        parsed_result = self.get_json({"id": [existing_id, nonexistent_id]})
        self.assertEqual([existing_id], extract_system_ids(parsed_result))

    def test_GET_with_hostname_returns_matching_machines(self):
        # The read operation takes optional "hostname" parameters. Only
        # machines with matching hostnames will be returned.
        machines = [factory.make_Node() for _ in range(3)]
        matching_hostname = machines[0].hostname
        matching_system_id = machines[0].system_id
        parsed_result = self.get_json({"hostname": [matching_hostname]})
        self.assertEqual(
            [matching_system_id], extract_system_ids(parsed_result)
        )

    def test_GET_with_macs_returns_matching_machines(self):
        # The "read" operation takes optional "mac_address" parameters. Only
        # machines with matching MAC addresses will be returned.
        interfaces = [
            factory.make_Interface(INTERFACE_TYPE.PHYSICAL) for _ in range(3)
        ]
        matching_mac = interfaces[0].mac_address
        matching_system_id = interfaces[0].node_config.node.system_id
        parsed_result = self.get_json({"mac_address": [matching_mac]})
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
            self.machines_url,
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
        machine = factory.make_Node(agent_name=agent_name)
        parsed_result = self.get_json({"agent_name": agent_name})
        self.assertEqual(
            [machine.system_id], extract_system_ids(parsed_result)
        )

    def test_GET_with_agent_name_filters_with_empty_string(self):
        factory.make_Node(agent_name=factory.make_name("agent-name"))
        machine = factory.make_Node(agent_name="")
        parsed_result = self.get_json({"agent_name": ""})
        self.assertEqual(
            [machine.system_id], extract_system_ids(parsed_result)
        )

    def test_GET_without_agent_name_does_not_filter(self):
        machines = [
            factory.make_Node(agent_name=factory.make_name("agent-name"))
            for _ in range(3)
        ]
        parsed_result = self.get_json()
        self.assertSequenceEqual(
            [machine.system_id for machine in machines],
            extract_system_ids(parsed_result),
        )

    def test_GET_doesnt_list_devices(self):
        factory.make_Device()
        parsed_result = self.get_json()
        self.assertEqual([], parsed_result)

    def test_GET_with_zone_filters_by_zone(self):
        factory.make_Node(zone=factory.make_Zone(name="twilight"))
        zone = factory.make_Zone()
        machine = factory.make_Node(zone=zone)
        parsed_result = self.get_json({"zone": zone.name})
        self.assertEqual(
            [machine.system_id], extract_system_ids(parsed_result)
        )

    def test_GET_without_zone_does_not_filter(self):
        machines = [
            factory.make_Node(zone=factory.make_Zone()) for _ in range(3)
        ]
        parsed_result = self.get_json()
        self.assertEqual(
            [machine.system_id for machine in machines],
            extract_system_ids(parsed_result),
        )

    def test_GET_list_allocated_returns_only_allocated_with_user(self):
        machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.user
        )
        factory.make_Node(status=NODE_STATUS.ALLOCATED)

        parsed_result = self.get_json({"op": "list_allocated"})
        self.assertEqual(
            [machine.system_id], extract_system_ids(parsed_result)
        )

    def test_GET_list_allocated_filters_by_id(self):
        machines = []
        for _ in range(3):
            machines.append(
                factory.make_Node(
                    status=NODE_STATUS.ALLOCATED, owner=self.user
                )
            )

        required_machine_ids = [machines[0].system_id, machines[1].system_id]
        parsed_result = self.get_json(
            {"op": "list_allocated", "id": required_machine_ids}
        )
        self.assertCountEqual(
            required_machine_ids, extract_system_ids(parsed_result)
        )

    def test_GET_list_allocated_with_rbac(self):
        self.patch(auth, "validate_user_external_auth").return_value = True
        rbac = self.useFixture(RBACEnabled())
        self.become_non_local()

        user = factory.make_User()
        pool = factory.make_ResourcePool()
        rbac.store.allow(user.username, pool, "view")

        pool = factory.make_ResourcePool()
        rbac.store.add_pool(pool)
        rbac.store.allow(self.user.username, pool, "view")

        factory.make_Node(
            hostname="viewable",
            owner=self.user,
            pool=pool,
            status=NODE_STATUS.ALLOCATED,
        )
        # a machine with the same user but not accesssible to the user (not in
        # the allowed pool)
        factory.make_Node(
            hostname="not-accessible",
            owner=self.user,
            status=NODE_STATUS.ALLOCATED,
        )
        # a machine owned by another user in the accessible pool
        factory.make_Node(
            hostname="other-user",
            owner=factory.make_User(),
            status=NODE_STATUS.ALLOCATED,
            pool=pool,
        )

        parsed_result = self.get_json({"op": "list_allocated"})
        hostnames = [machine["hostname"] for machine in parsed_result]
        self.assertEqual(["viewable"], hostnames)

    def test_POST_allocate_returns_available_machine(self):
        # The "allocate" operation returns an available machine.
        available_status = NODE_STATUS.READY
        machine = factory.make_Node(
            status=available_status, owner=None, with_boot_disk=True
        )
        response = self.client.post(self.machines_url, {"op": "allocate"})
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(machine.system_id, parsed_result["system_id"])

    def test_POST_allocate_returns_a_composed_machine_limit_from_rbac(self):
        self.patch(auth, "validate_user_external_auth").return_value = True
        rbac = self.useFixture(RBACEnabled())
        self.become_non_local()

        # 2 pods one with only view permissions and another with
        # dynamic_compose permission.
        view_pool = factory.make_ResourcePool()
        rbac.store.add_pool(view_pool)
        rbac.store.allow(self.user.username, view_pool, "view")
        factory.make_Pod(pool=view_pool, architectures=["amd64/generic"])
        deploy_pool = factory.make_ResourcePool()
        rbac.store.add_pool(deploy_pool)
        rbac.store.allow(self.user.username, deploy_pool, "deploy-machines")
        deploy_pod = factory.make_Pod(
            pool=deploy_pool, architectures=["amd64/generic"]
        )

        passed_pods = []

        class FakeComposer(ComposeMachineForPodsForm):
            """Catch the passed pods parameter and fake compose."""

            def __init__(self, *args, **kwargs):
                passed_pods.extend(kwargs["pods"])
                super().__init__(*args, **kwargs)

            def compose(self):
                return factory.make_Node(
                    status=NODE_STATUS.READY, owner=None, with_boot_disk=True
                )

        self.patch(machines_module, "ComposeMachineForPodsForm", FakeComposer)

        mock_filter_nodes = self.patch(AcquireNodeForm, "filter_nodes")
        mock_filter_nodes.return_value = Node.objects.none(), {}, {}
        response = self.client.post(self.machines_url, {"op": "allocate"})
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual([deploy_pod], passed_pods)

    def test_POST_allocate_returns_a_composed_machine_no_constraints(self):
        # The "allocate" operation returns a composed machine.
        available_status = NODE_STATUS.READY
        pod = factory.make_Pod()
        pod.architectures = [
            random.choice(
                [
                    "amd64/generic",
                    "i386/generic",
                    "armhf/generic",
                    "arm64/generic",
                ]
            )
        ]
        pod.save()
        machine = factory.make_Node(
            status=available_status, owner=None, with_boot_disk=True
        )
        mock_filter_nodes = self.patch(AcquireNodeForm, "filter_nodes")
        mock_filter_nodes.return_value = Node.objects.none(), {}, {}
        mock_compose = self.patch(ComposeMachineForPodsForm, "compose")
        mock_compose.return_value = machine
        response = self.client.post(self.machines_url, {"op": "allocate"})
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(machine.system_id, parsed_result["system_id"])
        mock_compose.assert_called_once_with()

    def test_POST_allocate_returns_a_composed_machine_constraints(self):
        # The "allocate" operation returns a composed machine.
        available_status = NODE_STATUS.READY
        architectures = [
            "amd64/generic",
            "i386/generic",
            "armhf/generic",
            "arm64/generic",
        ]
        tags = [
            factory.make_Tag(name=factory.make_name("tag")) for _ in range(3)
        ]
        tag_names = [tag.name for tag in tags]
        pod = factory.make_Pod(architectures=architectures)
        pod.tags = tag_names
        pod.hints.cores = random.randint(8, 16)
        pod.hints.memory = random.randint(4096, 8192)
        pod.hints.save()
        pod.save()
        machine = factory.make_Node(
            status=available_status, owner=None, with_boot_disk=True
        )
        mock_list_all_usable_architectures = self.patch(
            forms_module, "list_all_usable_architectures"
        )
        mock_list_all_usable_architectures.return_value = sorted(
            pod.architectures
        )
        mock_filter_nodes = self.patch(AcquireNodeForm, "filter_nodes")
        mock_filter_nodes.return_value = Node.objects.none(), {}, {}
        mock_compose = self.patch(ComposeMachineForPodsForm, "compose")
        mock_compose.return_value = machine
        response = self.client.post(
            self.machines_url,
            {
                "op": "allocate",
                "cpu_count": pod.hints.cores,
                "mem": pod.hints.memory,
                "arch": pod.architectures[0],
                "tags": tag_names,
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(machine.system_id, parsed_result["system_id"])
        mock_compose.assert_called_once_with()

    def test_POST_allocate_returns_a_composed_machine(self):
        # The "allocate" operation returns a composed machine.
        def compose_machine(*args, **kwargs):
            return factory.make_Node(
                status=NODE_STATUS.READY,
                owner=None,
                with_boot_disk=True,
                bmc=pod,
                hostname=pod_machine_hostname,
            )

        pod_machine_hostname = factory.make_name("pod-machine")
        architectures = [
            "amd64/generic",
            "i386/generic",
            "armhf/generic",
            "arm64/generic",
        ]
        pool = factory.make_ResourcePool()
        pod = factory.make_Pod(architectures=architectures, pool=pool)
        pod.hints.cores = random.randint(8, 16)
        pod.hints.memory = random.randint(4096, 8192)
        pod.hints.save()
        mock_list_all_usable_architectures = self.patch(
            forms_module, "list_all_usable_architectures"
        )
        mock_list_all_usable_architectures.return_value = sorted(
            pod.architectures
        )
        mock_compose = self.patch(ComposeMachineForm, "compose")
        mock_compose.side_effect = compose_machine
        response = self.client.post(
            self.machines_url,
            {
                "op": "allocate",
                "cpu_count": pod.hints.cores,
                "mem": pod.hints.memory,
                "arch": "amd64",
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(pod_machine_hostname, parsed_result["hostname"])

    def test_POST_allocate_returns_a_composed_machine_with_zone(self):
        # The "allocate" operation returns a composed machine with zone of Pod.
        available_status = NODE_STATUS.READY
        architectures = [
            "amd64/generic",
            "i386/generic",
            "armhf/generic",
            "arm64/generic",
        ]
        zone = factory.make_Zone()
        pod = factory.make_Pod(architectures=architectures, zone=zone)
        pod.hints.cores = random.randint(8, 16)
        pod.hints.memory = random.randint(4096, 8192)
        pod.hints.save()
        machine = factory.make_Node(
            status=available_status,
            owner=None,
            with_boot_disk=True,
            zone=pod.zone,
        )
        mock_list_all_usable_architectures = self.patch(
            forms_module, "list_all_usable_architectures"
        )
        mock_list_all_usable_architectures.return_value = sorted(
            pod.architectures
        )
        mock_filter_nodes = self.patch(AcquireNodeForm, "filter_nodes")
        mock_filter_nodes.return_value = Node.objects.none(), {}, {}
        mock_compose = self.patch(ComposeMachineForPodsForm, "compose")
        mock_compose.return_value = machine
        response = self.client.post(
            self.machines_url,
            {
                "op": "allocate",
                "cpu_count": pod.hints.cores,
                "mem": pod.hints.memory,
                "arch": pod.architectures[0],
                "zone": pod.zone.name,
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(machine.system_id, parsed_result["system_id"])
        self.assertEqual(machine.zone.name, parsed_result["zone"]["name"])
        mock_compose.assert_called_once_with()

    def test_POST_allocate_returns_a_composed_machine_with_pod(self):
        # The "allocate" operation returns a composed machine for pod
        # when constraint 'pod' is used.
        available_status = NODE_STATUS.READY
        architectures = [
            "amd64/generic",
            "i386/generic",
            "armhf/generic",
            "arm64/generic",
        ]
        pod_name = factory.make_name("pod")
        pod = factory.make_Pod(name=pod_name, architectures=architectures)
        pod.hints.cores = random.randint(8, 16)
        pod.hints.memory = random.randint(4096, 8192)
        pod.hints.save()
        machine = factory.make_Node(
            status=available_status, owner=None, with_boot_disk=True
        )
        mock_list_all_usable_architectures = self.patch(
            forms_module, "list_all_usable_architectures"
        )
        mock_list_all_usable_architectures.return_value = sorted(
            pod.architectures
        )
        mock_filter_nodes = self.patch(AcquireNodeForm, "filter_nodes")
        mock_filter_nodes.return_value = Node.objects.none(), {}, {}
        mock_compose = self.patch(ComposeMachineForPodsForm, "compose")
        mock_compose.return_value = machine
        response = self.client.post(
            self.machines_url,
            {
                "op": "allocate",
                "cpu_count": pod.hints.cores,
                "mem": pod.hints.memory,
                "arch": pod.architectures[0],
                "pod": pod_name,
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(machine.system_id, parsed_result["system_id"])
        mock_compose.assert_called_once_with()

    def test_POST_allocate_returns_a_composed_machine_with_not_pod(self):
        # The "allocate" operation returns a composed machine for pod
        # when constraint 'not_pod' is used.
        available_status = NODE_STATUS.READY
        architectures = [
            "amd64/generic",
            "i386/generic",
            "armhf/generic",
            "arm64/generic",
        ]
        pod_name = factory.make_name("pod")
        pod = factory.make_Pod(name=pod_name, architectures=architectures)
        pod.hints.cores = random.randint(8, 16)
        pod.hints.memory = random.randint(4096, 8192)
        pod.hints.save()
        machine = factory.make_Node(
            status=available_status, owner=None, with_boot_disk=True
        )
        mock_list_all_usable_architectures = self.patch(
            forms_module, "list_all_usable_architectures"
        )
        mock_list_all_usable_architectures.return_value = sorted(
            pod.architectures
        )
        mock_filter_nodes = self.patch(AcquireNodeForm, "filter_nodes")
        mock_filter_nodes.return_value = Node.objects.none(), {}, {}
        mock_compose = self.patch(ComposeMachineForPodsForm, "compose")
        mock_compose.return_value = machine
        response = self.client.post(
            self.machines_url,
            {
                "op": "allocate",
                "cpu_count": pod.hints.cores,
                "mem": pod.hints.memory,
                "arch": pod.architectures[0],
                "pod": pod_name,
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(machine.system_id, parsed_result["system_id"])
        mock_compose.assert_called_once_with()

    def test_POST_allocate_returns_a_composed_machine_with_pod_type(self):
        # The "allocate" operation returns a composed machine for pod
        # when constraint 'pod_type' is used.
        available_status = NODE_STATUS.READY
        architectures = [
            "amd64/generic",
            "i386/generic",
            "armhf/generic",
            "arm64/generic",
        ]
        pod = factory.make_Pod(pod_type="virsh", architectures=architectures)
        pod.hints.cores = random.randint(8, 16)
        pod.hints.memory = random.randint(4096, 8192)
        pod.hints.save()
        machine = factory.make_Node(
            status=available_status, owner=None, with_boot_disk=True
        )
        mock_list_all_usable_architectures = self.patch(
            forms_module, "list_all_usable_architectures"
        )
        mock_list_all_usable_architectures.return_value = sorted(
            pod.architectures
        )
        mock_filter_nodes = self.patch(AcquireNodeForm, "filter_nodes")
        mock_filter_nodes.return_value = Node.objects.none(), {}, {}
        mock_compose = self.patch(ComposeMachineForPodsForm, "compose")
        mock_compose.return_value = machine
        response = self.client.post(
            self.machines_url,
            {
                "op": "allocate",
                "cpu_count": pod.hints.cores,
                "mem": pod.hints.memory,
                "arch": pod.architectures[0],
                "pod_type": "virsh",
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(machine.system_id, parsed_result["system_id"])
        mock_compose.assert_called_once_with()

    def test_POST_allocate_returns_a_composed_machine_with_not_pod_type(self):
        # The "allocate" operation returns a composed machine for pod
        # when constraint 'not_pod_type' is used.
        available_status = NODE_STATUS.READY
        architectures = [
            "amd64/generic",
            "i386/generic",
            "armhf/generic",
            "arm64/generic",
        ]
        pod = factory.make_Pod(pod_type="virsh", architectures=architectures)
        pod.hints.cores = random.randint(8, 16)
        pod.hints.memory = random.randint(4096, 8192)
        pod.hints.save()
        machine = factory.make_Node(
            status=available_status, owner=None, with_boot_disk=True
        )
        mock_list_all_usable_architectures = self.patch(
            forms_module, "list_all_usable_architectures"
        )
        mock_list_all_usable_architectures.return_value = sorted(
            pod.architectures
        )
        mock_filter_nodes = self.patch(AcquireNodeForm, "filter_nodes")
        mock_filter_nodes.return_value = Node.objects.none(), {}, {}
        mock_compose = self.patch(ComposeMachineForPodsForm, "compose")
        mock_compose.return_value = machine
        response = self.client.post(
            self.machines_url,
            {
                "op": "allocate",
                "cpu_count": pod.hints.cores,
                "mem": pod.hints.memory,
                "arch": pod.architectures[0],
                "not_pod_type": "lxd",
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(machine.system_id, parsed_result["system_id"])
        mock_compose.assert_called_once_with()

    def test_POST_allocate_returns_a_composed_machine_wildcard_arch(self):
        # The "allocate" operation returns a composed machine.
        available_status = NODE_STATUS.READY
        architectures = [
            "amd64/generic",
            "i386/generic",
            "armhf/generic",
            "arm64/generic",
        ]
        pod = factory.make_Pod(architectures=architectures)
        pod.hints.cores = random.randint(8, 16)
        pod.hints.memory = random.randint(4096, 8192)
        pod.hints.save()
        machine = factory.make_Node(
            status=available_status, owner=None, with_boot_disk=True
        )
        mock_list_all_usable_architectures = self.patch(
            forms_module, "list_all_usable_architectures"
        )
        mock_list_all_usable_architectures.return_value = sorted(
            pod.architectures
        )
        mock_filter_nodes = self.patch(AcquireNodeForm, "filter_nodes")
        mock_filter_nodes.return_value = Node.objects.none(), {}, {}
        mock_compose = self.patch(ComposeMachineForPodsForm, "compose")
        mock_compose.return_value = machine
        response = self.client.post(
            self.machines_url,
            {
                "op": "allocate",
                "cpu_count": pod.hints.cores,
                "mem": pod.hints.memory,
                "arch": "amd64",
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(machine.system_id, parsed_result["system_id"])
        mock_compose.assert_called_once_with()

    def test_POST_allocate_returns_a_composed_machine_with_storage(self):
        # The "allocate" operation returns a composed machine.
        available_status = NODE_STATUS.READY
        architectures = [
            "amd64/generic",
            "i386/generic",
            "armhf/generic",
            "arm64/generic",
        ]
        pod = factory.make_Pod(architectures=architectures)
        pod.hints.cores = random.randint(8, 16)
        pod.hints.memory = random.randint(4096, 8192)
        pod.hints.save()
        machine = factory.make_Node(
            status=available_status, owner=None, with_boot_disk=False
        )
        disk_1 = factory.make_PhysicalBlockDevice(
            node=machine,
            size=(random.randint(8, 16) * (1000**3)),
            tags=["local"],
            formatted_root=True,
        )
        disk_2 = factory.make_PhysicalBlockDevice(
            node=machine,
            size=(random.randint(8, 16) * (1000**3)),
            tags=["other"],
        )
        storage = "root:%d(local),remote:%d(other)" % (
            disk_1.size // (1000**3),
            disk_2.size // (1000**3),
        )
        mock_list_all_usable_architectures = self.patch(
            forms_module, "list_all_usable_architectures"
        )
        mock_list_all_usable_architectures.return_value = sorted(
            pod.architectures
        )
        mock_filter_nodes = self.patch(AcquireNodeForm, "filter_nodes")
        mock_filter_nodes.return_value = Node.objects.none(), {}, {}
        mock_compose = self.patch(ComposeMachineForPodsForm, "compose")
        mock_compose.return_value = machine
        response = self.client.post(
            self.machines_url,
            {
                "op": "allocate",
                "cpu_count": pod.hints.cores,
                "mem": pod.hints.memory,
                "arch": pod.architectures[0],
                "storage": storage,
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(machine.system_id, parsed_result["system_id"])
        self.assertEqual(
            {"root": [disk_1.id], "remote": [disk_2.id]},
            parsed_result["constraints_by_type"]["storage"],
        )
        mock_compose.assert_called_once_with()

    def test_POST_allocate_returns_a_composed_machine_with_interfaces(self):
        # The "allocate" operation returns a composed machine.
        available_status = NODE_STATUS.READY
        architectures = [
            "amd64/generic",
            "i386/generic",
            "armhf/generic",
            "arm64/generic",
        ]
        pod = factory.make_Pod(architectures=architectures)
        pod.hints.cores = random.randint(8, 16)
        pod.hints.memory = random.randint(4096, 8192)
        pod.hints.save()
        machine = factory.make_Node_with_Interface_on_Subnet(
            status=available_status, owner=None
        )
        mock_list_all_usable_architectures = self.patch(
            forms_module, "list_all_usable_architectures"
        )
        mock_list_all_usable_architectures.return_value = sorted(
            pod.architectures
        )
        mock_filter_nodes = self.patch(AcquireNodeForm, "filter_nodes")
        mock_filter_nodes.return_value = Node.objects.none(), {}, {}
        mock_compose = self.patch(ComposeMachineForPodsForm, "compose")
        mock_compose.return_value = machine
        space = factory.make_Space()
        machine.boot_interface.vlan.space = space

        with post_commit_hooks:
            machine.boot_interface.vlan.save()

        response = self.client.post(
            self.machines_url,
            {
                "op": "allocate",
                "cpu_count": pod.hints.cores,
                "mem": pod.hints.memory,
                "arch": pod.architectures[0],
                "interfaces": "eth0:space=%s" % space.name,
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(machine.system_id, parsed_result["system_id"])
        self.assertEqual(
            {"eth0": [machine.boot_interface.id]},
            parsed_result["constraints_by_type"]["interfaces"],
        )
        mock_compose.assert_called_once_with()

    def test_POST_allocate_returns_machine_with_interface_link_speed(self):
        # The "allocate" operation returns a composed machine.
        available_status = NODE_STATUS.READY
        architectures = [
            "amd64/generic",
            "i386/generic",
            "armhf/generic",
            "arm64/generic",
        ]
        pod = factory.make_Pod(architectures=architectures)
        pod.hints.cores = random.randint(8, 16)
        pod.hints.memory = random.randint(4096, 8192)
        pod.hints.save()
        link_speed = 1000
        machine = factory.make_Node_with_Interface_on_Subnet(
            status=available_status,
            owner=None,
            link_connected=True,
            interface_speed=10000,
            link_speed=link_speed,
        )
        mock_list_all_usable_architectures = self.patch(
            forms_module, "list_all_usable_architectures"
        )
        mock_list_all_usable_architectures.return_value = sorted(
            pod.architectures
        )
        mock_filter_nodes = self.patch(AcquireNodeForm, "filter_nodes")
        mock_filter_nodes.return_value = Node.objects.none(), {}, {}
        mock_compose = self.patch(ComposeMachineForPodsForm, "compose")
        mock_compose.return_value = machine
        space = factory.make_Space()
        machine.boot_interface.vlan.space = space

        with post_commit_hooks:
            machine.boot_interface.vlan.save()

        response = self.client.post(
            self.machines_url,
            {
                "op": "allocate",
                "cpu_count": pod.hints.cores,
                "mem": pod.hints.memory,
                "arch": pod.architectures[0],
                "interfaces": "eth0:space=%s,link_speed=100" % space.name,
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(machine.system_id, parsed_result["system_id"])
        self.assertEqual(
            {"eth0": [machine.boot_interface.id]},
            parsed_result["constraints_by_type"]["interfaces"],
        )
        self.assertEqual(
            link_speed, parsed_result["boot_interface"]["link_speed"]
        )
        mock_compose.assert_called_once_with()

    def test_POST_allocate_returns_conflict_when_compose_fails(self):
        # The "allocate" operation returns a composed machine.
        architectures = [
            "amd64/generic",
            "i386/generic",
            "armhf/generic",
            "arm64/generic",
        ]
        pod = factory.make_Pod(architectures=architectures)
        pod.hints.cores = random.randint(8, 16)
        pod.hints.memory = random.randint(4096, 8192)
        pod.hints.save()
        storage = "root:%d(local),remote:%d(other)" % (
            random.randint(8, 16),
            random.randint(8, 16),
        )
        mock_list_all_usable_architectures = self.patch(
            forms_module, "list_all_usable_architectures"
        )
        mock_list_all_usable_architectures.return_value = sorted(
            pod.architectures
        )
        mock_filter_nodes = self.patch(AcquireNodeForm, "filter_nodes")
        mock_filter_nodes.return_value = Node.objects.none(), {}, {}
        mock_compose = self.patch(ComposeMachineForPodsForm, "compose")
        mock_compose.return_value = None
        response = self.client.post(
            self.machines_url,
            {
                "op": "allocate",
                "cpu_count": pod.hints.cores,
                "mem": pod.hints.memory,
                "arch": pod.architectures[0],
                "storage": storage,
            },
        )
        self.assertEqual(http.client.CONFLICT, response.status_code)

    def test_POST_allocate_allocates_machine(self):
        # The "allocate" operation allocates the machine it returns.
        available_status = NODE_STATUS.READY
        machine = factory.make_Node(
            status=available_status, owner=None, with_boot_disk=True
        )
        self.client.post(self.machines_url, {"op": "allocate"})
        machine = Machine.objects.get(system_id=machine.system_id)
        self.assertEqual(self.user, machine.owner)

    def test_POST_allocate_uses_machine_acquire_lock(self):
        # The "allocate" operation allocates the machine it returns.
        available_status = NODE_STATUS.READY
        factory.make_Node(
            status=available_status, owner=None, with_boot_disk=True
        )
        machine_acquire = self.patch(machines_module.locks, "node_acquire")
        self.client.post(self.machines_url, {"op": "allocate"})
        machine_acquire.__enter__.assert_called_once_with()
        machine_acquire.__exit__.assert_called_once_with(None, None, None)

    def test_POST_allocate_sets_agent_name(self):
        available_status = NODE_STATUS.READY
        machine = factory.make_Node(
            status=available_status,
            owner=None,
            agent_name=factory.make_name("agent-name"),
            with_boot_disk=True,
        )
        agent_name = factory.make_name("agent-name")
        self.client.post(
            self.machines_url,
            {"op": "allocate", "agent_name": agent_name},
        )
        machine = Machine.objects.get(system_id=machine.system_id)
        self.assertEqual(agent_name, machine.agent_name)

    def test_POST_allocate_agent_name_defaults_to_empty_string(self):
        available_status = NODE_STATUS.READY
        agent_name = factory.make_name("agent-name")
        machine = factory.make_Node(
            status=available_status,
            owner=None,
            agent_name=agent_name,
            with_boot_disk=True,
        )
        self.client.post(self.machines_url, {"op": "allocate"})
        machine = Machine.objects.get(system_id=machine.system_id)
        self.assertEqual("", machine.agent_name)

    def test_POST_allocate_fails_if_no_machine_present(self):
        # The "allocate" operation returns a Conflict error if no machines
        # are available.
        response = self.client.post(self.machines_url, {"op": "allocate"})
        # Fails with Conflict error: resource can't satisfy request.
        self.assertEqual(http.client.CONFLICT, response.status_code)

    def test_POST_allocate_failure_shows_no_constraints_if_none_given(self):
        response = self.client.post(self.machines_url, {"op": "allocate"})
        self.assertEqual(http.client.CONFLICT, response.status_code)
        self.assertEqual(
            "No machine available.",
            response.content.decode(settings.DEFAULT_CHARSET),
        )

    def test_POST_allocate_failure_shows_constraints_if_given(self):
        hostname = factory.make_name("host")
        response = self.client.post(
            self.machines_url, {"op": "allocate", "name": hostname}
        )
        expected_response = (
            "No available machine matches constraints: [('name', "
            "['%s'])] (resolved to \"name=%s\")" % (hostname, hostname)
        ).encode(settings.DEFAULT_CHARSET)
        self.assertEqual(http.client.CONFLICT, response.status_code)
        self.assertEqual(expected_response, response.content)

    def test_POST_allocate_ignores_already_allocated_machine(self):
        factory.make_Node(
            status=NODE_STATUS.ALLOCATED,
            owner=factory.make_User(),
            with_boot_disk=True,
        )
        response = self.client.post(self.machines_url, {"op": "allocate"})
        self.assertEqual(http.client.CONFLICT, response.status_code)

    def test_POST_allocate_chooses_candidate_matching_constraint(self):
        # If "allocate" is passed a constraint, it will go for a machine
        # matching that constraint even if there's tons of other machines
        # available.
        # (Creating lots of machines here to minimize the chances of this
        # passing by accident).
        available_machines = [
            factory.make_Node(
                status=NODE_STATUS.READY, owner=None, with_boot_disk=True
            )
            for counter in range(20)
        ]
        desired_machine = random.choice(available_machines)
        response = self.client.post(
            self.machines_url,
            {"op": "allocate", "name": desired_machine.hostname},
        )
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        domain_name = desired_machine.domain.name
        self.assertEqual(
            f"{desired_machine.hostname}.{domain_name}",
            parsed_result["fqdn"],
        )

    def test_POST_allocate_would_rather_fail_than_disobey_constraint(self):
        # If "allocate" is passed a constraint, it won't return a machine
        # that does not meet that constraint.  Even if it means that it
        # can't meet the request.
        factory.make_Node(
            status=NODE_STATUS.READY, owner=None, with_boot_disk=True
        )
        desired_machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User()
        )
        response = self.client.post(
            self.machines_url,
            {"op": "allocate", "name": desired_machine.system_id},
        )
        self.assertEqual(http.client.CONFLICT, response.status_code)

    def test_POST_allocate_fails_if_given_system_id_invalid(self):
        # If an unavailable or incorrect "system_id" is passed, make sure
        # that no machine is returned.
        some_available_machine = factory.make_Node(
            status=NODE_STATUS.READY, owner=None, with_boot_disk=True
        )
        incorrect_system_id = (
            some_available_machine.system_id[-1]
            + some_available_machine.system_id[:-1]
        )
        response = self.client.post(
            self.machines_url,
            {"op": "allocate", "system_id": incorrect_system_id},
        )
        expected_response = f"No machine with system ID {incorrect_system_id} available.".encode(
            "utf-8"
        )
        self.assertEqual(http.client.CONFLICT, response.status_code)
        self.assertEqual(expected_response, response.content)

    def test_POST_allocate_does_not_ignore_unknown_constraint(self):
        factory.make_Node(
            status=NODE_STATUS.READY, owner=None, with_boot_disk=True
        )
        unknown_constraint = factory.make_string()
        response = self.client.post(
            self.machines_url,
            {"op": "allocate", unknown_constraint: factory.make_string()},
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(
            {unknown_constraint: ["No such constraint."]}, parsed_result
        )

    def test_POST_allocate_allocates_machine_by_name(self):
        # Positive test for name constraint.
        # If a name constraint is given, "allocate" attempts to allocate
        # a machine of that name.
        machine = factory.make_Node(
            domain=factory.make_Domain(),
            status=NODE_STATUS.READY,
            owner=None,
            with_boot_disk=True,
        )
        response = self.client.post(
            self.machines_url,
            {"op": "allocate", "name": machine.hostname},
        )
        self.assertEqual(http.client.OK, response.status_code)
        domain_name = machine.domain.name
        self.assertEqual(
            f"{machine.hostname}.{domain_name}",
            json.loads(response.content.decode(settings.DEFAULT_CHARSET))[
                "fqdn"
            ],
        )

    def test_POST_allocate_allocates_machine_by_system_id(self):
        # Positive test for system_id constraint.
        # If a name constraint is given, "allocate" attempts to allocate
        # a machine with that system_id.
        machine = factory.make_Node(
            domain=factory.make_Domain(),
            status=NODE_STATUS.READY,
            owner=None,
            with_boot_disk=True,
        )
        response = self.client.post(
            self.machines_url,
            {"op": "allocate", "system_id": machine.system_id},
        )
        self.assertEqual(http.client.OK, response.status_code)
        resultant_system_id = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )["system_id"]
        self.assertEqual(machine.system_id, resultant_system_id)

    def test_POST_allocate_treats_unknown_name_as_resource_conflict(self):
        # A name constraint naming an unknown machine produces a resource
        # conflict: most likely the machine existed but has changed or
        # disappeared.
        # Certainly it's not a 404, since the resource named in the URL
        # is "machines/," which does exist.
        factory.make_Node(
            status=NODE_STATUS.READY, owner=None, with_boot_disk=True
        )
        response = self.client.post(
            self.machines_url,
            {"op": "allocate", "name": factory.make_string()},
        )
        self.assertEqual(http.client.CONFLICT, response.status_code)

    def test_POST_allocate_allocates_machine_by_arch(self):
        # Asking for a particular arch allocates a machine with that arch.
        arch = make_usable_architecture(self)
        machine = factory.make_Node(
            status=NODE_STATUS.READY, architecture=arch, with_boot_disk=True
        )
        response = self.client.post(
            self.machines_url, {"op": "allocate", "arch": arch}
        )
        self.assertEqual(http.client.OK, response.status_code)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(machine.architecture, response_json["architecture"])

    def test_POST_allocate_treats_unknown_arch_as_bad_request(self):
        # Asking for an unknown arch returns an HTTP "400 Bad Request"
        factory.make_Node(status=NODE_STATUS.READY, with_boot_disk=True)
        response = self.client.post(
            self.machines_url, {"op": "allocate", "arch": "sparc"}
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)

    def test_POST_allocate_allocates_machine_by_cpu(self):
        # Asking for enough cpu allocates a machine with at least that.
        machine = factory.make_Node(
            status=NODE_STATUS.READY, cpu_count=3, with_boot_disk=True
        )
        response = self.client.post(
            self.machines_url, {"op": "allocate", "cpu_count": 2}
        )
        self.assertEqual(response.status_code, http.client.OK)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(machine.system_id, response_json["system_id"])

    def test_POST_allocate_allocates_machine_by_float_cpu(self):
        # Asking for a needlessly precise number of cpus works.
        machine = factory.make_Node(
            status=NODE_STATUS.READY, cpu_count=1, with_boot_disk=True
        )
        response = self.client.post(
            self.machines_url, {"op": "allocate", "cpu_count": "1.0"}
        )
        self.assertEqual(response.status_code, http.client.OK)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(machine.system_id, response_json["system_id"])

    def test_POST_allocate_fails_with_invalid_cpu(self):
        # Asking for an invalid amount of cpu returns a bad request.
        factory.make_Node(status=NODE_STATUS.READY, with_boot_disk=True)
        response = self.client.post(
            self.machines_url,
            {"op": "allocate", "cpu_count": "plenty"},
        )
        self.assertEqual(response.status_code, http.client.BAD_REQUEST)

    def test_POST_allocate_allocates_machine_by_mem(self):
        # Asking for enough memory acquires a machine with at least that.
        machine = factory.make_Node(
            status=NODE_STATUS.READY, memory=1024, with_boot_disk=True
        )
        response = self.client.post(
            self.machines_url, {"op": "allocate", "mem": 1024}
        )
        self.assertEqual(response.status_code, http.client.OK)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(machine.system_id, response_json["system_id"])

    def test_POST_allocate_fails_with_invalid_mem(self):
        # Asking for an invalid amount of memory returns a bad request.
        factory.make_Node(status=NODE_STATUS.READY, with_boot_disk=True)
        response = self.client.post(
            self.machines_url, {"op": "allocate", "mem": "bags"}
        )
        self.assertEqual(response.status_code, http.client.BAD_REQUEST)

    def test_POST_allocate_allocates_machine_by_tags(self):
        machine = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True
        )
        machine_tag_names = ["fast", "stable", "cute"]
        machine.tags.set(factory.make_Tag(t) for t in machine_tag_names)
        # Legacy call using comma-separated tags.
        response = self.client.post(
            self.machines_url,
            {"op": "allocate", "tags": ["fast", "stable"]},
        )
        self.assertEqual(response.status_code, http.client.OK)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertCountEqual(machine_tag_names, response_json["tag_names"])

    def test_POST_allocate_does_not_compose_machine_by_tags(self):
        pod = factory.make_Pod()
        pod.architectures = [
            random.choice(
                [
                    "amd64/generic",
                    "i386/generic",
                    "armhf/generic",
                    "arm64/generic",
                ]
            )
        ]
        pod.save()
        mock_filter_nodes = self.patch(AcquireNodeForm, "filter_nodes")
        mock_filter_nodes.return_value = Node.objects.none(), {}, {}
        mock_compose = self.patch(ComposeMachineForPodsForm, "compose")
        factory.make_Tag("fast")
        factory.make_Tag("stable")
        # Legacy call using comma-separated tags.
        response = self.client.post(
            self.machines_url,
            {"op": "allocate", "tags": ["fast", "stable"]},
        )
        self.assertEqual(response.status_code, http.client.CONFLICT)
        mock_compose.assert_not_called()

    def test_POST_allocate_allocates_machine_by_negated_tags(self):
        tagged_machine = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True
        )
        partially_tagged_machine = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True
        )
        machine_tag_names = ["fast", "stable", "cute"]
        tags = [factory.make_Tag(t) for t in machine_tag_names]
        tagged_machine.tags.set(tags)
        partially_tagged_machine.tags.set(tags[:-1])
        # Legacy call using comma-separated tags.
        response = self.client.post(
            self.machines_url,
            {"op": "allocate", "not_tags": ["cute"]},
        )
        self.assertEqual(response.status_code, http.client.OK)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(
            partially_tagged_machine.system_id, response_json["system_id"]
        )
        self.assertCountEqual(
            machine_tag_names[:-1], response_json["tag_names"]
        )

    def test_POST_allocate_allocates_machine_by_zone(self):
        factory.make_Node(status=NODE_STATUS.READY, with_boot_disk=True)
        zone = factory.make_Zone()
        machine = factory.make_Node(
            status=NODE_STATUS.READY, zone=zone, with_boot_disk=True
        )
        response = self.client.post(
            self.machines_url, {"op": "allocate", "zone": zone.name}
        )
        self.assertEqual(response.status_code, http.client.OK)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(machine.system_id, response_json["system_id"])

    def test_POST_allocate_allocates_machine_by_zone_fails_if_no_machine(self):
        factory.make_Node(status=NODE_STATUS.READY, with_boot_disk=True)
        zone = factory.make_Zone()
        response = self.client.post(
            self.machines_url, {"op": "allocate", "zone": zone.name}
        )
        self.assertEqual(response.status_code, http.client.CONFLICT)

    def test_POST_allocate_rejects_unknown_zone(self):
        response = self.client.post(
            self.machines_url,
            {"op": "allocate", "zone": factory.make_name("zone")},
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)

    def test_POST_allocate_allocates_machine_by_pool(self):
        node1 = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True
        )
        factory.make_Node(status=NODE_STATUS.READY, with_boot_disk=True)
        pool = factory.make_ResourcePool(nodes=[node1])
        response = self.client.post(
            self.machines_url, {"op": "allocate", "pool": pool.name}
        )
        self.assertEqual(response.status_code, http.client.OK)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(node1.system_id, response_json["system_id"])

    def test_POST_allocate_allocates_machine_by_pool_fails_if_no_machine(self):
        factory.make_Node(status=NODE_STATUS.READY, with_boot_disk=True)
        pool = factory.make_ResourcePool()
        response = self.client.post(
            self.machines_url, {"op": "allocate", "pool": pool.name}
        )
        self.assertEqual(response.status_code, http.client.CONFLICT)

    def test_POST_allocate_rejects_unknown_pool(self):
        response = self.client.post(
            self.machines_url,
            {"op": "allocate", "pool": factory.make_name("pool")},
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)

    def test_POST_allocate_allocates_machine_by_tags_comma_separated(self):
        machine = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True
        )
        machine_tag_names = ["fast", "stable", "cute"]
        machine.tags.set(factory.make_Tag(t) for t in machine_tag_names)
        # Legacy call using comma-separated tags.
        response = self.client.post(
            self.machines_url,
            {"op": "allocate", "tags": "fast, stable"},
        )
        self.assertEqual(response.status_code, http.client.OK)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertCountEqual(machine_tag_names, response_json["tag_names"])

    def test_POST_allocate_allocates_machine_by_tags_space_separated(self):
        machine = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True
        )
        machine_tag_names = ["fast", "stable", "cute"]
        machine.tags.set(factory.make_Tag(t) for t in machine_tag_names)
        # Legacy call using space-separated tags.
        response = self.client.post(
            self.machines_url,
            {"op": "allocate", "tags": "fast stable"},
        )
        self.assertEqual(response.status_code, http.client.OK)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertCountEqual(machine_tag_names, response_json["tag_names"])

    def test_POST_allocate_allocates_machine_by_tags_comma_space_delim(self):
        machine = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True
        )
        machine_tag_names = ["fast", "stable", "cute"]
        machine.tags.set(factory.make_Tag(t) for t in machine_tag_names)
        # Legacy call using comma-and-space-separated tags.
        response = self.client.post(
            self.machines_url,
            {"op": "allocate", "tags": "fast, stable cute"},
        )
        self.assertEqual(response.status_code, http.client.OK)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertCountEqual(machine_tag_names, response_json["tag_names"])

    def test_POST_allocate_allocates_machine_by_tags_mixed_input(self):
        machine = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True
        )
        machine_tag_names = ["fast", "stable", "cute"]
        machine.tags.set(factory.make_Tag(t) for t in machine_tag_names)
        # Mixed call using comma-separated tags in a list.
        response = self.client.post(
            self.machines_url,
            {"op": "allocate", "tags": ["fast, stable", "cute"]},
        )
        self.assertEqual(response.status_code, http.client.OK)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertCountEqual(machine_tag_names, response_json["tag_names"])

    def test_POST_allocate_allocates_machine_by_storage(self):
        """Storage label is returned alongside machine data"""
        machine = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=False
        )
        factory.make_PhysicalBlockDevice(
            node=machine,
            size=11 * (1000**3),
            tags=["ssd"],
            formatted_root=True,
        )
        response = self.client.post(
            self.machines_url,
            {"op": "allocate", "storage": "needed:10(ssd)"},
        )
        self.assertEqual(response.status_code, http.client.OK)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        device_id = response_json["physicalblockdevice_set"][0]["id"]
        constraints = response_json["constraints_by_type"]
        self.assertIn("storage", constraints)
        self.assertIn("needed", constraints["storage"])
        self.assertIn(device_id, constraints["storage"]["needed"])
        self.assertNotIn("verbose_storage", constraints)

    def test_POST_allocate_allocates_machine_by_storage_with_verbose(self):
        """Storage label is returned alongside machine data"""
        machine = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=False
        )
        factory.make_PhysicalBlockDevice(
            node=machine,
            size=11 * (1000**3),
            tags=["ssd"],
            formatted_root=True,
        )
        response = self.client.post(
            self.machines_url,
            {"op": "allocate", "storage": "needed:10(ssd)", "verbose": "true"},
        )
        self.assertEqual(response.status_code, http.client.OK)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        device_id = response_json["physicalblockdevice_set"][0]["id"]
        constraints = response_json["constraints_by_type"]
        self.assertIn("storage", constraints)
        self.assertIn("needed", constraints["storage"])
        self.assertIn(device_id, constraints["storage"]["needed"])
        self.assertIn(str(machine.id), constraints.get("verbose_storage"))

    def test_POST_allocate_allocates_machine_by_interfaces(self):
        """Interface label is returned alongside machine data"""
        fabric = factory.make_Fabric("ubuntu")
        # The ID may always be '1', which won't be interesting for testing.
        for _ in range(1, random.choice([1, 3, 5])):
            factory.make_Interface()
        machine = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY, fabric=fabric
        )
        iface = machine.get_boot_interface()
        response = self.client.post(
            self.machines_url,
            {"op": "allocate", "interfaces": "needed:fabric=ubuntu"},
        )
        self.assertEqual(response.status_code, http.client.OK)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(response_json["status"], NODE_STATUS.ALLOCATED)
        constraints = response_json["constraints_by_type"]
        self.assertIn("interfaces", constraints)
        interfaces = constraints.get("interfaces")
        self.assertIn("needed", interfaces)
        self.assertIn(iface.id, interfaces["needed"])
        self.assertNotIn("verbose_interfaces", constraints)

    def test_POST_allocate_with_subnet_specifier_renders_error(self):
        space = factory.make_Space("foo")
        v1 = factory.make_VLAN(space=space)
        v2 = factory.make_VLAN(space=space)
        s1 = factory.make_Subnet(vlan=v1, space=None)
        s2 = factory.make_Subnet(vlan=v2, space=None)
        factory.make_Node_with_Interface_on_Subnet(subnet=s1)
        response = self.client.post(
            self.machines_url,
            {"op": "allocate", "subnets": "space:foo"},
        )
        self.assertEqual(http.client.CONFLICT, response.status_code)
        expected_response = (
            "No available machine matches constraints: [('subnets', "
            "['space:foo'])] (resolved to \"subnets=%d,%d\")" % (s1.pk, s2.pk)
        ).encode(settings.DEFAULT_CHARSET)
        self.assertEqual(expected_response, response.content)

    def test_POST_allocate_machine_by_interfaces_dry_run_with_verbose(self):
        """Interface label is returned alongside machine data"""
        fabric = factory.make_Fabric("ubuntu")
        # The ID may always be '1', which won't be interesting for testing.
        for _ in range(1, random.choice([1, 3, 5])):
            factory.make_Interface()
        machine = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY, fabric=fabric
        )
        iface = machine.get_boot_interface()
        response = self.client.post(
            self.machines_url,
            {
                "op": "allocate",
                "interfaces": "needed:fabric=ubuntu",
                "verbose": "true",
                "dry_run": "true",
            },
        )
        self.assertEqual(response.status_code, http.client.OK)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(response_json["status"], NODE_STATUS.READY)
        # Check that we still got the verbose constraints output even if
        # it was a dry run.
        constraints = response_json["constraints_by_type"]
        self.assertIn("interfaces", constraints)
        interfaces = constraints.get("interfaces")
        self.assertIn("needed", interfaces)
        self.assertIn(iface.id, interfaces["needed"])
        self.assertIn("verbose_interfaces", constraints)
        verbose_interfaces = constraints.get("verbose_interfaces")
        self.assertIn("needed", verbose_interfaces)
        self.assertIn(str(machine.id), verbose_interfaces["needed"])
        self.assertIn(iface.id, verbose_interfaces["needed"][str(machine.id)])

    def test_POST_allocate_allocates_machine_by_interfaces_with_verbose(self):
        """Interface label is returned alongside machine data"""
        fabric = factory.make_Fabric("ubuntu")
        # The ID may always be '1', which won't be interesting for testing.
        for _ in range(1, random.choice([1, 3, 5])):
            factory.make_Interface()
        factory.make_Node()
        machine = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY, fabric=fabric
        )
        iface = machine.get_boot_interface()
        response = self.client.post(
            self.machines_url,
            {
                "op": "allocate",
                "interfaces": "needed:fabric=ubuntu",
                "verbose": "true",
            },
        )
        self.assertEqual(response.status_code, http.client.OK)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        constraints = response_json["constraints_by_type"]
        self.assertIn("interfaces", constraints)
        interfaces = constraints.get("interfaces")
        self.assertIn("needed", interfaces)
        self.assertEqual([iface.id], interfaces["needed"])
        self.assertIn("verbose_interfaces", constraints)
        verbose_interfaces = constraints.get("verbose_interfaces")
        self.assertIn("needed", verbose_interfaces)
        self.assertIn(str(machine.id), verbose_interfaces["needed"])
        self.assertIn(iface.id, verbose_interfaces["needed"][str(machine.id)])

    def test_POST_allocate_fails_without_all_tags(self):
        # Asking for particular tags does not acquire if no machine has all
        # tags.
        machine1 = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True
        )
        machine1.tags.set(
            factory.make_Tag(t) for t in ("fast", "stable", "cute")
        )
        machine2 = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True
        )
        machine2.tags.set([factory.make_Tag("cheap")])
        response = self.client.post(
            self.machines_url,
            {"op": "allocate", "tags": "fast, cheap"},
        )
        self.assertEqual(response.status_code, http.client.CONFLICT)

    def test_POST_allocate_fails_with_unknown_tags(self):
        # Asking for a tag that does not exist gives a specific error.
        machine = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True
        )
        machine.tags.set([factory.make_Tag("fast")])
        response = self.client.post(
            self.machines_url,
            {"op": "allocate", "tags": "fast, hairy, boo"},
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        response_dict = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        # The order in which "foo" and "bar" appear is not guaranteed.
        self.assertIn("No such tag(s):", response_dict["tags"][0])
        self.assertIn("'hairy'", response_dict["tags"][0])
        self.assertIn("'boo'", response_dict["tags"][0])

    def test_POST_allocate_allocates_machine_by_subnet(self):
        subnets = [factory.make_Subnet() for _ in range(5)]
        machines = [
            factory.make_Node_with_Interface_on_Subnet(
                status=NODE_STATUS.READY, with_boot_disk=True, subnet=subnet
            )
            for subnet in subnets
        ]
        # We'll make it so that only the machine and subnet at this index will
        # match the request.
        pick = 2

        response = self.client.post(
            self.machines_url,
            {"op": "allocate", "subnets": [subnets[pick].name]},
        )

        self.assertEqual(response.status_code, http.client.OK)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(machines[pick].system_id, response_json["system_id"])

    def test_POST_allocate_allocates_machine_by_not_subnet(self):
        subnets = [factory.make_Subnet() for _ in range(5)]
        for subnet in subnets:
            factory.make_Node_with_Interface_on_Subnet(
                status=NODE_STATUS.READY, with_boot_disk=True, subnet=subnet
            )
        right_machine = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY, with_boot_disk=True
        )

        response = self.client.post(
            self.machines_url,
            {
                "op": "allocate",
                "not_subnets": [subnet.name for subnet in subnets],
            },
        )

        self.assertEqual(response.status_code, http.client.OK)
        response_json = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(right_machine.system_id, response_json["system_id"])

    def test_POST_allocate_obeys_not_in_zone(self):
        # Zone we don't want to acquire from.
        not_in_zone = factory.make_Zone()
        machines = [
            factory.make_Node(
                status=NODE_STATUS.READY, zone=not_in_zone, with_boot_disk=True
            )
            for _ in range(5)
        ]
        # Pick a machine in the middle to avoid false negatives if acquire()
        # always tries the oldest, or the newest, machine first.
        eligible_machine = machines[2]
        eligible_machine.zone = factory.make_Zone()
        eligible_machine.save()

        response = self.client.post(
            self.machines_url,
            {"op": "allocate", "not_in_zone": [not_in_zone.name]},
        )
        self.assertEqual(http.client.OK, response.status_code)
        system_id = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )["system_id"]
        self.assertEqual(eligible_machine.system_id, system_id)

    def test_POST_allocate_obeys_not_in_pool(self):
        # Pool we don't want to acquire from.
        node1 = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True
        )
        node2 = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=True
        )
        pool1 = factory.make_ResourcePool(nodes=[node1])
        factory.make_ResourcePool(nodes=[node2])

        response = self.client.post(
            self.machines_url,
            {"op": "allocate", "not_in_pool": [pool1.name]},
        )
        self.assertEqual(http.client.OK, response.status_code)
        system_id = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )["system_id"]
        self.assertEqual(node2.system_id, system_id)

    def test_POST_accept_gets_machine_out_of_declared_state(self):
        # This will change when we add provisioning.  Until then,
        # acceptance gets a machine straight to Ready state.
        self.become_admin()
        target_state = NODE_STATUS.COMMISSIONING

        self.patch(Machine, "_start").return_value = None
        machine = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.NEW
        )
        response = self.client.post(
            self.machines_url,
            {"op": "accept", "machines": [machine.system_id]},
        )
        accepted_ids = [
            accepted_machine["system_id"]
            for accepted_machine in json.loads(
                response.content.decode(settings.DEFAULT_CHARSET)
            )
        ]
        self.assertEqual(
            (http.client.OK, [machine.system_id]),
            (response.status_code, accepted_ids),
        )
        self.assertEqual(target_state, reload_object(machine).status)

    def test_POST_quietly_accepts_empty_set(self):
        response = self.client.post(self.machines_url, {"op": "accept"})
        self.assertEqual(
            (http.client.OK.value, "[]"),
            (
                response.status_code,
                response.content.decode(settings.DEFAULT_CHARSET),
            ),
        )

    def test_POST_accept_rejects_impossible_state_changes(self):
        self.become_admin()
        self.patch(Machine, "_start").return_value = None
        acceptable_states = {
            NODE_STATUS.NEW,
            NODE_STATUS.COMMISSIONING,
            NODE_STATUS.READY,
        }
        status_iter = iter(
            set(map_enum(NODE_STATUS).values()) - acceptable_states
        )
        machine = factory.make_Node(with_boot_disk=False)
        self.patch(
            machines_module.MachinesHandler.base_model.objects, "get_nodes"
        ).return_value = [machine]

        for status in status_iter:
            machine.status = status
            response = self.client.post(
                self.machines_url,
                {"op": "accept", "machines": [machine.system_id]},
            )
            self.assertEqual(response.status_code, http.client.CONFLICT)
            content = response.content.decode(settings.DEFAULT_CHARSET)
            self.assertEqual(
                content,
                f"Cannot accept node enlistment: node {machine.system_id} is in state {machine.status_name}.",
            )

    def test_POST_accept_fails_if_machine_does_not_exist(self):
        self.become_admin()
        # Make sure there is a machine, it just isn't the one being accepted
        factory.make_Node()
        machine_id = factory.make_string()
        response = self.client.post(
            self.machines_url,
            {"op": "accept", "machines": [machine_id]},
        )
        self.assertEqual(
            (
                http.client.BAD_REQUEST,
                ("Unknown machine(s): %s." % machine_id).encode(
                    settings.DEFAULT_CHARSET
                ),
            ),
            (response.status_code, response.content),
        )

    def test_POST_accept_fails_for_device(self):
        self.become_admin()
        factory.make_Device()
        machine_id = factory.make_string()
        response = self.client.post(
            self.machines_url,
            {"op": "accept", "machines": [machine_id]},
        )
        self.assertEqual(
            (
                http.client.BAD_REQUEST,
                ("Unknown machine(s): %s." % machine_id).encode(
                    settings.DEFAULT_CHARSET
                ),
            ),
            (response.status_code, response.content),
        )

    def test_POST_accept_accepts_multiple_machines(self):
        # This will change when we add provisioning.  Until then,
        # acceptance gets a machine straight to Ready state.
        self.become_admin()
        target_state = NODE_STATUS.COMMISSIONING

        self.patch(Machine, "_start").return_value = None
        machines = [
            factory.make_Node_with_Interface_on_Subnet(status=NODE_STATUS.NEW)
            for counter in range(2)
        ]
        machine_ids = [machine.system_id for machine in machines]
        response = self.client.post(
            self.machines_url,
            {"op": "accept", "machines": machine_ids},
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            [target_state] * len(machines),
            [reload_object(machine).status for machine in machines],
        )

    def test_POST_accept_returns_actually_accepted_machines(self):
        self.become_admin()
        self.patch(Machine, "_start").return_value = None
        acceptable_machines = [
            factory.make_Node_with_Interface_on_Subnet(status=NODE_STATUS.NEW)
            for counter in range(2)
        ]
        accepted_machine = factory.make_Node(status=NODE_STATUS.READY)
        machines = acceptable_machines + [accepted_machine]
        response = self.client.post(
            self.machines_url,
            {
                "op": "accept",
                "machines": [machine.system_id for machine in machines],
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        accepted_ids = [
            machine["system_id"]
            for machine in json.loads(
                response.content.decode(settings.DEFAULT_CHARSET)
            )
        ]
        self.assertCountEqual(
            [machine.system_id for machine in acceptable_machines],
            accepted_ids,
        )
        self.assertNotIn(accepted_machine.system_id, accepted_ids)

    def test_POST_quietly_releases_empty_set(self):
        response = self.client.post(self.machines_url, {"op": "release"})
        self.assertEqual(
            (http.client.OK.value, "[]"),
            (
                response.status_code,
                response.content.decode(settings.DEFAULT_CHARSET),
            ),
        )

    def test_POST_release_ignores_devices(self):
        device_ids = {factory.make_Device().system_id for _ in range(3)}
        response = self.client.post(
            self.machines_url,
            {"op": "release", "machines": device_ids},
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)

    def test_POST_release_rejects_request_from_unauthorized_user(self):
        machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User()
        )
        response = self.client.post(
            self.machines_url,
            {"op": "release", "machines": [machine.system_id]},
        )
        self.assertEqual(http.client.FORBIDDEN, response.status_code)
        self.assertEqual(NODE_STATUS.ALLOCATED, reload_object(machine).status)

    def test_POST_release_fails_if_machines_do_not_exist(self):
        # Make sure there is a machine, it just isn't among the ones to release
        factory.make_Node()
        machine_ids = {factory.make_string() for _ in range(5)}
        response = self.client.post(
            self.machines_url,
            {"op": "release", "machines": machine_ids},
        )
        # Awkward parsing, but the order may vary and it's not JSON
        s = response.content.decode(settings.DEFAULT_CHARSET)
        returned_ids = s[s.find(":") + 2 : s.rfind(".")].split(", ")
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertIn(
            "Unknown machine(s): ",
            response.content.decode(settings.DEFAULT_CHARSET),
        )
        self.assertCountEqual(machine_ids, returned_ids)

    def test_POST_release_forbidden_if_user_cannot_edit_machine(self):
        # Create a bunch of machines, owned by the logged in user
        machine_ids = {
            factory.make_Node(
                status=NODE_STATUS.ALLOCATED, owner=self.user
            ).system_id
            for _ in range(3)
        }
        # And one with another owner
        another_machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User()
        )
        machine_ids.add(another_machine.system_id)
        response = self.client.post(
            self.machines_url,
            {"op": "release", "machines": machine_ids},
        )
        expected_response = (
            "You don't have the required permission to release the following "
            "machine(s): %s." % another_machine.system_id
        ).encode(settings.DEFAULT_CHARSET)
        self.assertEqual(
            (http.client.FORBIDDEN.value, expected_response),
            (response.status_code, response.content),
        )

    def test_POST_release_forbidden_if_locked_machines(self):
        machine1 = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.user
        )
        machine2 = factory.make_Node(
            status=NODE_STATUS.DEPLOYED, owner=self.user, locked=True
        )
        # And one with no owner
        response = self.client.post(
            self.machines_url,
            {
                "op": "release",
                "machines": [machine1.system_id, machine2.system_id],
            },
        )
        expected_response = (
            "You don't have the required permission to release the following "
            "machine(s): {}.".format(machine2.system_id)
        ).encode(settings.DEFAULT_CHARSET)
        self.assertEqual(
            (http.client.FORBIDDEN.value, expected_response),
            (response.status_code, response.content),
        )

    def test_POST_release_rejects_impossible_state_changes(self):
        acceptable_states = {NODE_STATUS.READY} | RELEASABLE_STATUSES
        unacceptable_states = (
            set(map_enum(NODE_STATUS).values()) - acceptable_states
        )
        owner = self.user
        machines = [
            factory.make_Node(status=status, owner=owner)
            for status in unacceptable_states
        ]
        response = self.client.post(
            self.machines_url,
            {
                "op": "release",
                "machines": [machine.system_id for machine in machines],
            },
        )
        # Awkward parsing again, because a string is returned, not JSON
        expected = [
            f"{machine.system_id} ('{machine.display_status()}')"
            for machine in machines
            if machine.status not in acceptable_states
        ]
        s = response.content.decode(settings.DEFAULT_CHARSET)
        returned = s[s.rfind(":") + 2 : s.rfind(".")].split(", ")
        self.assertEqual(http.client.CONFLICT, response.status_code)
        self.assertIn(
            "Machine(s) cannot be released in their current state:",
            response.content.decode(settings.DEFAULT_CHARSET),
        )
        self.assertCountEqual(expected, returned)

    def test_POST_release_returns_modified_machines(self):
        owner = self.user
        self.patch(Machine, "_stop")
        self.patch(Machine, "_set_status")
        acceptable_states = RELEASABLE_STATUSES | {NODE_STATUS.READY}
        zone = factory.make_Zone()
        machines = [
            factory.make_Node(
                status=status, owner=owner, with_boot_disk=False, zone=zone
            )
            for status in acceptable_states
        ]
        response = self.client.post(
            self.machines_url,
            {
                "op": "release",
                "machines": [machine.system_id for machine in machines],
            },
        )
        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(http.client.OK, response.status_code)
        # The first machine is READY, so shouldn't be touched.
        self.assertCountEqual(
            [machine.system_id for machine in machines[1:]], parsed_result
        )

    def test_POST_release_erases_disks_when_enabled(self):
        owner = self.user
        self.patch(Machine, "_start").return_value = None
        machine = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.ALLOCATED,
            power_state=POWER_STATE.OFF,
            owner=owner,
        )
        Config.objects.set_config("enable_disk_erasing_on_release", True)
        response = self.client.post(
            self.machines_url,
            {"op": "release", "machines": [machine.system_id]},
        )
        self.assertEqual(http.client.OK.value, response.status_code, response)
        machine = reload_object(machine)
        self.assertEqual(NODE_STATUS.DISK_ERASING, machine.status)

    def test_POST_set_zone_sets_zone_on_machines(self):
        self.become_admin()
        machine = factory.make_Node()
        zone = factory.make_Zone()
        response = self.client.post(
            self.machines_url,
            {
                "op": "set_zone",
                "nodes": [machine.system_id],
                "zone": zone.name,
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        machine = reload_object(machine)
        self.assertEqual(zone, machine.zone)

    def test_POST_set_zone_does_not_affect_other_machines(self):
        self.become_admin()
        machine = factory.make_Node()
        original_zone = machine.zone
        response = self.client.post(
            self.machines_url,
            {
                "op": "set_zone",
                "nodes": [factory.make_Node().system_id],
                "zone": factory.make_Zone().name,
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        machine = reload_object(machine)
        self.assertEqual(original_zone, machine.zone)

    def test_POST_set_zone_requires_admin(self):
        machine = factory.make_Node(owner=self.user)
        original_zone = machine.zone
        response = self.client.post(
            self.machines_url,
            {
                "op": "set_zone",
                "nodes": [machine.system_id],
                "zone": factory.make_Zone().name,
            },
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        machine = reload_object(machine)
        self.assertEqual(original_zone, machine.zone)

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
            self.machines_url,
            {
                "op": "set_zone",
                "nodes": [machine.system_id],
                "zone": zone.name,
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        machine = reload_object(machine)
        self.assertEqual(zone, machine.zone)

    def test_POST_add_chassis_requires_admin(self):
        response = self.client.post(self.machines_url, {"op": "add_chassis"})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_POST_add_chassis_requires_chassis_type(self):
        self.become_admin()
        response = self.client.post(self.machines_url, {"op": "add_chassis"})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(b"No provided chassis_type!", response.content)

    def test_POST_add_chassis_invalid_chasis_type(self):
        self.become_admin()
        response = self.client.post(
            self.machines_url,
            {"op": "add_chassis", "chassis_type": "invalid"},
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertTrue(
            response.content.startswith(
                b"Invalid chassis_type: Value must be one of: "
            )
        )

    def test_POST_add_chassis_requires_hostname(self):
        self.become_admin()
        response = self.client.post(
            self.machines_url,
            {"op": "add_chassis", "chassis_type": "virsh"},
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(b"No provided hostname!", response.content)

    def test_POST_add_chassis_validates_chassis_type(self):
        self.become_admin()
        response = self.client.post(
            self.machines_url,
            {
                "op": "add_chassis",
                "chassis_type": factory.make_name("chassis_type"),
                "hostname": factory.make_url(),
            },
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_POST_add_chassis_username_required_for_required_chassis(self):
        self.become_admin()
        rack = factory.make_RackController()
        accessible_by_url = self.patch(
            machines_module.RackController.objects, "get_accessible_by_url"
        )
        accessible_by_url.return_value = rack
        self.patch(rack, "add_chassis")
        for chassis_type in (
            "hmcz",
            "mscm",
            "msftocs",
            "recs_box",
            "seamicro15k",
            "ucsm",
            "vmware",
        ):
            response = self.client.post(
                self.machines_url,
                {
                    "op": "add_chassis",
                    "chassis_type": chassis_type,
                    "hostname": factory.make_url(),
                },
            )
            self.assertEqual(
                http.client.BAD_REQUEST, response.status_code, response.content
            )
            self.assertEqual(b"No provided username!", response.content)

    def test_POST_add_chassis_password_required_for_required_chassis(self):
        self.become_admin()
        rack = factory.make_RackController()
        accessible_by_url = self.patch(
            machines_module.RackController.objects, "get_accessible_by_url"
        )
        accessible_by_url.return_value = rack
        self.patch(rack, "add_chassis")
        for chassis_type in (
            "hmcz",
            "mscm",
            "msftocs",
            "recs_box",
            "seamicro15k",
            "ucsm",
            "vmware",
        ):
            response = self.client.post(
                self.machines_url,
                {
                    "op": "add_chassis",
                    "chassis_type": chassis_type,
                    "hostname": factory.make_url(),
                    "username": factory.make_name("username"),
                },
            )
            self.assertEqual(
                http.client.BAD_REQUEST, response.status_code, response.content
            )
            self.assertEqual(b"No provided password!", response.content)

    def test_POST_add_chassis_proxmox_requires_password_or_token(self):
        self.become_admin()
        rack = factory.make_RackController()
        chassis_mock = self.patch(rack, "add_chassis")
        response = self.client.post(
            self.machines_url,
            {
                "op": "add_chassis",
                "rack_controller": rack.system_id,
                "chassis_type": "proxmox",
                "hostname": factory.make_url(),
                "username": factory.make_name("username"),
            },
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(
            (b"You must use a password or token with Proxmox."),
            response.content,
        )
        self.assertEqual(chassis_mock.call_count, 0)

    def test_POST_add_chassis_proxmox_requires_password_xor_token(self):
        self.become_admin()
        rack = factory.make_RackController()
        chassis_mock = self.patch(rack, "add_chassis")
        response = self.client.post(
            self.machines_url,
            {
                "op": "add_chassis",
                "rack_controller": rack.system_id,
                "chassis_type": "proxmox",
                "hostname": factory.make_url(),
                "username": factory.make_name("username"),
                "password": factory.make_name("password"),
                "token_name": factory.make_name("token_name"),
                "token_secret": factory.make_name("token_secret"),
            },
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(
            b"You may only use a password or token with Proxmox, not both.",
            response.content,
        )
        self.assertEqual(chassis_mock.call_count, 0)

    def test_POST_add_chassis_proxmox_requires_token_name_and_secret(self):
        self.become_admin()
        rack = factory.make_RackController()
        chassis_mock = self.patch(rack, "add_chassis")
        response = self.client.post(
            self.machines_url,
            {
                "op": "add_chassis",
                "rack_controller": rack.system_id,
                "chassis_type": "proxmox",
                "hostname": factory.make_url(),
                "username": factory.make_name("username"),
                random.choice(
                    ["token_name", "token_secret"]
                ): factory.make_name("token"),
            },
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(
            (b"Proxmox requires both a token_name and token_secret."),
            response.content,
        )
        self.assertEqual(chassis_mock.call_count, 0)

    def test_POST_add_chassis_username_disallowed_on_virsh_and_powerkvm(self):
        self.become_admin()
        rack = factory.make_RackController()
        accessible_by_url = self.patch(
            machines_module.RackController.objects, "get_accessible_by_url"
        )
        accessible_by_url.return_value = rack
        self.patch(rack, "add_chassis")
        for chassis_type in ("powerkvm", "virsh"):
            response = self.client.post(
                self.machines_url,
                {
                    "op": "add_chassis",
                    "chassis_type": chassis_type,
                    "hostname": factory.make_url(),
                    "username": factory.make_name("username"),
                },
            )
            self.assertEqual(
                http.client.BAD_REQUEST, response.status_code, response.content
            )
            self.assertEqual(
                (
                    "username can not be specified when using the %s "
                    "chassis." % chassis_type
                ).encode("utf-8"),
                response.content,
            )

    def test_POST_add_chassis_sends_accept_all_when_true(self):
        self.become_admin()
        rack = factory.make_RackController()
        accessible_by_url = self.patch(
            machines_module.RackController.objects, "get_accessible_by_url"
        )
        accessible_by_url.return_value = rack
        add_chassis = self.patch(rack, "add_chassis")
        hostname = factory.make_url()
        response = self.client.post(
            self.machines_url,
            {
                "op": "add_chassis",
                "chassis_type": "virsh",
                "hostname": hostname,
                "accept_all": "true",
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        add_chassis.assert_called_once_with(
            self.user.username,
            "virsh",
            hostname,
            None,
            None,
            True,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            False,
        )

    def test_POST_add_chassis_sends_accept_all_false_when_not_true(self):
        self.become_admin()
        rack = factory.make_RackController()
        accessible_by_url = self.patch(
            machines_module.RackController.objects, "get_accessible_by_url"
        )
        accessible_by_url.return_value = rack
        add_chassis = self.patch(rack, "add_chassis")
        hostname = factory.make_url()
        response = self.client.post(
            self.machines_url,
            {
                "op": "add_chassis",
                "chassis_type": "virsh",
                "hostname": hostname,
                "accept_all": factory.make_name("accept_all"),
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        add_chassis.assert_called_once_with(
            self.user.username,
            "virsh",
            hostname,
            None,
            None,
            False,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            False,
        )

    def test_POST_add_chassis_sends_prefix_filter(self):
        self.become_admin()
        rack = factory.make_RackController()
        accessible_by_url = self.patch(
            machines_module.RackController.objects, "get_accessible_by_url"
        )
        accessible_by_url.return_value = rack
        add_chassis = self.patch(rack, "add_chassis")
        hostname = factory.make_url()
        for chassis_type in ("powerkvm", "virsh", "vmware", "proxmox", "hmcz"):
            prefix_filter = factory.make_name("prefix_filter")
            password = factory.make_name("password")
            params = {
                "op": "add_chassis",
                "chassis_type": chassis_type,
                "hostname": hostname,
                "password": password,
                "prefix_filter": prefix_filter,
            }
            if chassis_type in {"vmware", "proxmox", "hmcz"}:
                username = factory.make_name("username")
                params["username"] = username
            else:
                username = None
            response = self.client.post(self.machines_url, params)
            self.assertEqual(
                http.client.OK, response.status_code, response.content
            )
            add_chassis.assert_called_with(
                self.user.username,
                chassis_type,
                hostname,
                username,
                password,
                False,
                None,
                prefix_filter,
                None,
                None,
                None,
                None,
                None,
                False,
            )

    def test_POST_add_chassis_only_allows_prefix_filter_on_virtual_chassis(
        self,
    ):
        self.become_admin()
        for chassis_type in (
            "mscm",
            "msftocs",
            "recs_box",
            "seamicro15k",
            "ucsm",
        ):
            response = self.client.post(
                self.machines_url,
                {
                    "op": "add_chassis",
                    "chassis_type": chassis_type,
                    "hostname": factory.make_url(),
                    "username": factory.make_name("username"),
                    "password": factory.make_name("password"),
                    "prefix_filter": factory.make_name("prefix_filter"),
                },
            )
            self.assertEqual(
                http.client.BAD_REQUEST, response.status_code, response.content
            )
            self.assertEqual(
                (
                    "prefix_filter is unavailable with the %s chassis type"
                    % chassis_type
                ).encode("utf-8"),
                response.content,
            )

    def test_POST_add_chassis_seamicro_validates_power_control(self):
        self.become_admin()
        response = self.client.post(
            self.machines_url,
            {
                "op": "add_chassis",
                "chassis_type": "seamicro15k",
                "hostname": factory.make_url(),
                "username": factory.make_name("username"),
                "password": factory.make_name("password"),
                "power_control": factory.make_name("power_control"),
            },
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_POST_add_chassis_seamicro_allows_acceptable_power_controls(self):
        self.become_admin()
        rack = factory.make_RackController()
        accessible_by_url = self.patch(
            machines_module.RackController.objects, "get_accessible_by_url"
        )
        accessible_by_url.return_value = rack
        self.patch(rack, "add_chassis")
        for power_control in ("ipmi", "restapi", "restapi2"):
            hostname = factory.make_url()
            username = factory.make_name("username")
            password = factory.make_name("password")
            response = self.client.post(
                self.machines_url,
                {
                    "op": "add_chassis",
                    "chassis_type": "seamicro15k",
                    "hostname": hostname,
                    "username": username,
                    "password": password,
                    "power_control": power_control,
                },
            )
            self.assertEqual(
                http.client.OK, response.status_code, response.content
            )
            self.assertEqual(
                (
                    "Asking %s to add machines from chassis %s"
                    % (rack.hostname, hostname)
                ).encode("utf-8"),
                response.content,
            )

    def test_POST_add_chassis_only_allow_power_control_on_seamicro15k(self):
        self.become_admin()
        for chassis_type in (
            "mscm",
            "msftocs",
            "ucsm",
            "virsh",
            "vmware",
            "powerkvm",
            "proxmox",
        ):
            params = {
                "op": "add_chassis",
                "chassis_type": chassis_type,
                "hostname": factory.make_url(),
                "password": factory.make_name("password"),
                "power_control": "ipmi",
            }
            if chassis_type not in ("virsh", "powerkvm"):
                params["username"] = factory.make_name("username")
            response = self.client.post(self.machines_url, params)
            self.assertEqual(
                http.client.BAD_REQUEST, response.status_code, response.content
            )
            self.assertEqual(
                (
                    "power_control is unavailable with the %s chassis type"
                    % chassis_type
                ).encode("utf-8"),
                response.content,
            )

    def test_POST_add_chassis_sends_port_with_vmware_and_msftocs(self):
        self.become_admin()
        rack = factory.make_RackController()
        accessible_by_url = self.patch(
            machines_module.RackController.objects, "get_accessible_by_url"
        )
        accessible_by_url.return_value = rack
        add_chassis = self.patch(rack, "add_chassis")
        hostname = factory.make_url()
        username = factory.make_name("username")
        password = factory.make_name("password")
        port = random.randint(1, 65535)
        for chassis_type in ("msftocs", "recs_box", "vmware"):
            response = self.client.post(
                self.machines_url,
                {
                    "op": "add_chassis",
                    "chassis_type": chassis_type,
                    "hostname": hostname,
                    "username": username,
                    "password": password,
                    "port": port,
                },
            )
            self.assertEqual(
                http.client.OK, response.status_code, response.content
            )
            add_chassis.assert_called_with(
                self.user.username,
                chassis_type,
                hostname,
                username,
                password,
                False,
                None,
                None,
                None,
                port,
                None,
                None,
                None,
                False,
            )

    def test_POST_add_chassis_only_allows_port_with_vmware_and_msftocs(self):
        self.become_admin()
        for chassis_type in (
            "mscm",
            "powerkvm",
            "seamicro15k",
            "ucsm",
            "virsh",
        ):
            params = {
                "op": "add_chassis",
                "chassis_type": chassis_type,
                "hostname": factory.make_url(),
                "password": factory.make_name("password"),
                "port": random.randint(1, 65535),
            }
            if chassis_type not in ("virsh", "powerkvm"):
                params["username"] = factory.make_name("username")
            response = self.client.post(self.machines_url, params)
            self.assertEqual(
                http.client.BAD_REQUEST, response.status_code, response.content
            )
            self.assertEqual(
                (
                    "port is unavailable with the %s chassis type"
                    % chassis_type
                ).encode("utf-8"),
                response.content,
            )

    def test_POST_add_chassis_checks_port_too_high(self):
        self.become_admin()
        for chassis_type in ("msftocs", "recs_box", "vmware"):
            params = {
                "op": "add_chassis",
                "chassis_type": chassis_type,
                "hostname": factory.make_url(),
                "username": factory.make_name("username"),
                "password": factory.make_name("password"),
                "port": 65536,
            }
            response = self.client.post(self.machines_url, params)
            self.assertEqual(
                http.client.BAD_REQUEST, response.status_code, response.content
            )
            self.assertEqual(
                b"Invalid port: Please enter a number that is 65535 or smaller",
                response.content,
            )

    def test_POST_add_chassis_checks_port_too_low(self):
        self.become_admin()
        for chassis_type in ("msftocs", "recs_box", "vmware"):
            params = {
                "op": "add_chassis",
                "chassis_type": chassis_type,
                "hostname": factory.make_url(),
                "username": factory.make_name("username"),
                "password": factory.make_name("password"),
                "port": random.randint(-2, 0),
            }
            response = self.client.post(self.machines_url, params)
            self.assertEqual(
                http.client.BAD_REQUEST, response.status_code, response.content
            )
            self.assertEqual(
                b"Invalid port: Please enter a number that is 1 or greater",
                response.content,
            )

    def test_POST_add_chassis_sends_protcol_with_vmware(self):
        self.become_admin()
        rack = factory.make_RackController()
        accessible_by_url = self.patch(
            machines_module.RackController.objects, "get_accessible_by_url"
        )
        accessible_by_url.return_value = rack
        add_chassis = self.patch(rack, "add_chassis")
        hostname = factory.make_url()
        username = factory.make_name("username")
        password = factory.make_name("password")
        protocol = factory.make_name("protocol")
        response = self.client.post(
            self.machines_url,
            {
                "op": "add_chassis",
                "chassis_type": "vmware",
                "hostname": hostname,
                "username": username,
                "password": password,
                "protocol": protocol,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        add_chassis.assert_called_with(
            self.user.username,
            "vmware",
            hostname,
            username,
            password,
            False,
            None,
            None,
            None,
            None,
            protocol,
            None,
            None,
            False,
        )

    def test_POST_add_chassis_only_allows_protocol_with_vmware(self):
        self.become_admin()
        for chassis_type in (
            "mscm",
            "msftocs",
            "powerkvm",
            "seamicro15k",
            "ucsm",
            "virsh",
        ):
            params = {
                "op": "add_chassis",
                "chassis_type": chassis_type,
                "hostname": factory.make_url(),
                "password": factory.make_name("password"),
                "protocol": factory.make_name("protocol"),
            }
            if chassis_type not in ("virsh", "powerkvm"):
                params["username"] = factory.make_name("username")
            response = self.client.post(self.machines_url, params)
            self.assertEqual(
                http.client.BAD_REQUEST, response.status_code, response.content
            )
            self.assertEqual(
                (
                    "protocol is unavailable with the %s chassis type"
                    % chassis_type
                ).encode("utf-8"),
                response.content,
            )

    def test_POST_add_chassis_accept_domain_by_name(self):
        self.become_admin()
        rack = factory.make_RackController()
        accessible_by_url = self.patch(
            machines_module.RackController.objects, "get_accessible_by_url"
        )
        accessible_by_url.return_value = rack
        add_chassis = self.patch(rack, "add_chassis")
        hostname = factory.make_url()
        domain = factory.make_Domain()
        response = self.client.post(
            self.machines_url,
            {
                "op": "add_chassis",
                "chassis_type": "virsh",
                "hostname": hostname,
                "domain": domain.name,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        add_chassis.assert_called_with(
            self.user.username,
            "virsh",
            hostname,
            None,
            None,
            False,
            domain.name,
            None,
            None,
            None,
            None,
            None,
            None,
            False,
        )

    def test_POST_add_chassis_accept_domain_by_id(self):
        self.become_admin()
        rack = factory.make_RackController()
        accessible_by_url = self.patch(
            machines_module.RackController.objects, "get_accessible_by_url"
        )
        accessible_by_url.return_value = rack
        add_chassis = self.patch(rack, "add_chassis")
        hostname = factory.make_url()
        domain = factory.make_Domain()
        response = self.client.post(
            self.machines_url,
            {
                "op": "add_chassis",
                "chassis_type": "virsh",
                "hostname": hostname,
                "domain": domain.id,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        add_chassis.assert_called_with(
            self.user.username,
            "virsh",
            hostname,
            None,
            None,
            False,
            domain.name,
            None,
            None,
            None,
            None,
            None,
            None,
            False,
        )

    def test_POST_add_chassis_validates_domain(self):
        self.become_admin()
        domain = factory.make_name("domain")
        response = self.client.post(
            self.machines_url,
            {
                "op": "add_chassis",
                "chassis_type": "virsh",
                "hostname": factory.make_url(),
                "domain": domain,
            },
        )
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )
        self.assertEqual(
            ("Unable to find specified domain %s" % domain).encode("utf-8"),
            response.content,
        )

    def test_POST_add_chassis_accepts_system_id_for_rack_controller(self):
        self.become_admin()
        subnet = factory.make_Subnet()
        rack = factory.make_RackController(subnet=subnet)
        add_chassis = self.patch(node_module.RackController, "add_chassis")
        factory.make_RackController(subnet=subnet)
        accessible_by_url = self.patch(
            machines_module.RackController.objects, "get_accessible_by_url"
        )
        hostname = factory.pick_ip_in_Subnet(subnet)
        response = self.client.post(
            self.machines_url,
            {
                "op": "add_chassis",
                "chassis_type": "virsh",
                "hostname": hostname,
                "rack_controller": rack.system_id,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        accessible_by_url.assert_not_called()
        add_chassis.assert_called_with(
            self.user.username,
            "virsh",
            hostname,
            None,
            None,
            False,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            False,
        )

    def test_POST_add_chassis_accepts_hostname_for_rack_controller(self):
        self.become_admin()
        subnet = factory.make_Subnet()
        rack = factory.make_RackController(subnet=subnet)
        add_chassis = self.patch(node_module.RackController, "add_chassis")
        factory.make_RackController(subnet=subnet)
        accessible_by_url = self.patch(
            machines_module.RackController.objects, "get_accessible_by_url"
        )
        hostname = factory.pick_ip_in_Subnet(subnet)
        response = self.client.post(
            self.machines_url,
            {
                "op": "add_chassis",
                "chassis_type": "virsh",
                "hostname": hostname,
                "rack_controller": rack.hostname,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        accessible_by_url.assert_not_called()
        add_chassis.assert_called_with(
            self.user.username,
            "virsh",
            hostname,
            None,
            None,
            False,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            False,
        )

    def test_POST_add_chassis_rejects_invalid_rack_controller(self):
        self.become_admin()
        subnet = factory.make_Subnet()
        factory.make_RackController(subnet=subnet)
        self.patch(node_module.RackController, "add_chassis")
        accessible_by_url = self.patch(
            machines_module.RackController.objects, "get_accessible_by_url"
        )
        hostname = factory.pick_ip_in_Subnet(subnet)
        bad_rack = factory.make_name("rack_controller")
        response = self.client.post(
            self.machines_url,
            {
                "op": "add_chassis",
                "chassis_type": "virsh",
                "hostname": hostname,
                "rack_controller": bad_rack,
            },
        )
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )
        self.assertEqual(
            ("Unable to find specified rack %s" % bad_rack).encode("utf-8"),
            response.content,
        )
        accessible_by_url.assert_not_called()

    def test_POST_add_chassis_all_racks_when_no_racks_avalible(self):
        self.become_admin()
        rack1 = factory.make_RackController(hostname="rack-a")
        rack2 = factory.make_RackController(hostname="rack-b")
        add_chassis1 = self.patch(rack1, "add_chassis")
        add_chassis2 = self.patch(rack2, "add_chassis")
        all_racks = self.patch(machines_module.RackController.objects, "all")
        all_racks.return_value = [rack1, rack2]
        accessible_by_url = self.patch(
            machines_module.RackController.objects, "get_accessible_by_url"
        )
        accessible_by_url.return_value = None
        hostname = factory.make_url()
        response = self.client.post(
            self.machines_url,
            {
                "op": "add_chassis",
                "chassis_type": "virsh",
                "hostname": hostname,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        add_chassis1.assert_called_with(
            self.user.username,
            "virsh",
            hostname,
            None,
            None,
            False,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            False,
        )
        add_chassis2.assert_called_with(
            self.user.username,
            "virsh",
            hostname,
            None,
            None,
            False,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            False,
        )

    def test_POST_clone_error(self):
        self.become_admin()
        source = factory.make_Machine(with_boot_disk=False)
        factory.make_Interface(node=source, name="eth0")
        destination = factory.make_Machine(
            status=NODE_STATUS.READY, with_boot_disk=False
        )
        factory.make_Interface(node=destination, name="eth1")
        response = self.client.post(
            self.machines_url,
            {
                "op": "clone",
                "source": source.system_id,
                "destinations": destination.system_id,
                "interfaces": "true",
            },
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_POST_clone(self):
        self.become_admin()
        source = factory.make_Machine(with_boot_disk=False)
        factory.make_Interface(node=source, name="eth0")
        destination = factory.make_Machine(
            status=NODE_STATUS.READY, with_boot_disk=False
        )
        factory.make_Interface(node=destination, name="eth0")
        response = self.client.post(
            self.machines_url,
            {
                "op": "clone",
                "source": source.system_id,
                "destinations": destination.system_id,
                "interfaces": "true",
            },
        )
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )


class TestPowerState(APITransactionTestCase.ForUser):
    def setUp(self):
        super().setUp()
        self.useFixture(RegionEventLoopFixture("database-tasks", "rpc"))
        self.useFixture(RunningEventLoopFixture())

    def get_machine_uri(self, machine):
        """Get the API URI for a machine."""
        return reverse("machine_handler", args=[machine.system_id])

    def assertPowerState(self, machine, state):
        dbtasks = eventloop.services.getServiceNamed("database-tasks")
        dbtasks.syncTask().wait(
            timeout=5
        )  # Wait for all pending tasks to run.
        self.assertEqual(state, reload_object(machine).power_state)

    def test_returns_actual_state(self):
        machine = factory.make_Node_with_Interface_on_Subnet(power_type="ipmi")
        random_state = random.choice(["on", "off", "error"])

        self.patch(Node, "_power_control_node").return_value = succeed(
            {"state": random_state}
        )

        response = self.client.get(
            self.get_machine_uri(machine), {"op": "query_power_state"}
        )
        self.assertEqual(response.status_code, http.client.OK)
        response = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual({"state": random_state}, response)
        # The machine's power state is now `random_state`.
        self.assertPowerState(machine, random_state)


class TestGetAllocationOptions(MAASTestCase):
    def test_defaults(self):
        request = factory.make_fake_request(method="POST", data={})
        options = get_allocation_options(request)
        expected_options = AllocationOptions(
            agent_name="",
            bridge_all=False,
            bridge_type=BRIDGE_TYPE.STANDARD,
            bridge_fd=0,
            bridge_stp=False,
            comment=None,
            install_rackd=False,
            install_kvm=False,
            register_vmhost=False,
            ephemeral_deploy=False,
            enable_hw_sync=False,
        )
        self.assertEqual(expected_options, options)

    def test_sets_bridge_all_if_install_kvm(self):
        request = factory.make_fake_request(
            method="POST", data=dict(install_kvm="true")
        )
        options = get_allocation_options(request)
        expected_options = AllocationOptions(
            agent_name="",
            bridge_all=True,
            bridge_type=BRIDGE_TYPE.STANDARD,
            bridge_fd=0,
            bridge_stp=False,
            comment=None,
            install_rackd=False,
            install_kvm=True,
            register_vmhost=False,
            ephemeral_deploy=False,
            enable_hw_sync=False,
        )
        self.assertEqual(expected_options, options)

    def test_sets_bridge_all_if_register_vmhost(self):
        request = factory.make_fake_request(
            method="POST",
            data={"register_vmhost": True},
        )
        options = get_allocation_options(request)
        self.assertEqual(
            options,
            AllocationOptions(
                agent_name="",
                bridge_all=True,
                bridge_type=BRIDGE_TYPE.STANDARD,
                bridge_fd=0,
                bridge_stp=False,
                comment=None,
                install_rackd=False,
                install_kvm=False,
                register_vmhost=True,
                ephemeral_deploy=False,
                enable_hw_sync=False,
            ),
        )

    def test_non_defaults(self):
        request = factory.make_fake_request(
            method="POST",
            data=dict(
                install_rackd="true",
                install_kvm="true",
                register_vmhost="true",
                bridge_all="true",
                bridge_type=BRIDGE_TYPE.OVS,
                bridge_stp="true",
                bridge_fd="42",
                agent_name="maas",
                comment="don't panic",
                ephemeral_deploy="true",
                enable_hw_sync="true",
            ),
        )
        options = get_allocation_options(request)
        expected_options = AllocationOptions(
            agent_name="maas",
            bridge_all=True,
            bridge_type=BRIDGE_TYPE.OVS,
            bridge_fd=42,
            bridge_stp=True,
            comment="don't panic",
            install_rackd=True,
            install_kvm=True,
            register_vmhost=True,
            ephemeral_deploy=True,
            enable_hw_sync=True,
        )
        self.assertEqual(expected_options, options)
