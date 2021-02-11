# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.pod.lxd`."""

from os.path import join
import random
from unittest.mock import ANY, Mock, PropertyMock, sentinel

from testtools.matchers import Equals, IsInstance, MatchesAll, MatchesStructure
from testtools.testcase import ExpectedException
from twisted.internet.defer import inlineCallbacks

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver import maas_certificates
from provisioningserver.drivers.pod import (
    Capabilities,
    DiscoveredMachineBlockDevice,
    DiscoveredMachineInterface,
    DiscoveredPodHints,
    InterfaceAttachType,
)
from provisioningserver.drivers.pod import (
    RequestedMachine,
    RequestedMachineBlockDevice,
    RequestedMachineInterface,
)
from provisioningserver.drivers.pod import lxd as lxd_module
from provisioningserver.maas_certificates import (
    MAAS_CERTIFICATE,
    MAAS_PRIVATE_KEY,
)
from provisioningserver.refresh.node_info_scripts import LXD_OUTPUT_NAME
from provisioningserver.rpc.exceptions import PodInvalidResources
from provisioningserver.utils import (
    debian_to_kernel_architecture,
    kernel_to_debian_architecture,
)
from provisioningserver.utils.network import generate_mac_address


def make_requested_machine(num_disks=1, **kwargs):
    block_devices = [
        RequestedMachineBlockDevice(
            size=random.randint(1024 ** 3, 4 * 1024 ** 3)
        )
        for _ in range(num_disks)
    ]
    interfaces = [RequestedMachineInterface()]
    return RequestedMachine(
        hostname=factory.make_name("hostname"),
        architecture="amd64/generic",
        cores=random.randint(2, 4),
        memory=random.randint(1024, 4096),
        cpu_speed=random.randint(2000, 3000),
        block_devices=block_devices,
        interfaces=interfaces,
        **kwargs,
    )


class TestLXDByteSuffixes(MAASTestCase):
    def test_convert_lxd_byte_suffixes_with_integers(self):
        numbers = [
            random.randint(1, 10)
            for _ in range(len(lxd_module.LXD_BYTE_SUFFIXES))
        ]
        expected_results = [
            numbers[idx] * value
            for idx, value in enumerate(lxd_module.LXD_BYTE_SUFFIXES.values())
        ]
        actual_results = [
            lxd_module.convert_lxd_byte_suffixes(str(numbers[idx]) + key)
            for idx, key in enumerate(lxd_module.LXD_BYTE_SUFFIXES.keys())
        ]
        self.assertSequenceEqual(expected_results, actual_results)


class TestLXDPodDriver(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def setUp(self):
        super().setUp()
        # Generating the cert tuple can be slow and aren't necessary
        # for the tests.
        self.patch(maas_certificates, "generate_certificate_if_needed")

    def test_missing_packages(self):
        driver = lxd_module.LXDPodDriver()
        missing = driver.detect_missing_packages()
        self.assertItemsEqual([], missing)

    def make_parameters_context(self):
        return {
            "power_address": "".join(
                [
                    factory.make_name("power_address"),
                    ":%s" % factory.pick_port(),
                ]
            ),
            "instance_name": factory.make_name("instance_name"),
            "password": factory.make_name("password"),
            "project": factory.make_name("project"),
        }

    def test_get_url(self):
        driver = lxd_module.LXDPodDriver()
        context = {"power_address": factory.make_hostname()}

        # Test ip adds protocol and port
        self.assertEqual(
            join("https://", "%s:%d" % (context["power_address"], 8443)),
            driver.get_url(context),
        )

        # Test ip:port adds protocol
        context["power_address"] += ":1234"
        self.assertEqual(
            join("https://", "%s" % context["power_address"]),
            driver.get_url(context),
        )

        # Test protocol:ip adds port
        context["power_address"] = join("https://", factory.make_hostname())
        self.assertEqual(
            "%s:%d" % (context.get("power_address"), 8443),
            driver.get_url(context),
        )

        # Test protocol:ip:port doesn't do anything
        context["power_address"] += ":1234"
        self.assertEqual(context.get("power_address"), driver.get_url(context))

    def test_get_client(self):
        context = self.make_parameters_context()
        Client = self.patch(lxd_module, "Client")
        client = Client.return_value
        client.has_api_extension.return_value = True
        client.trusted = False
        driver = lxd_module.LXDPodDriver()
        endpoint = driver.get_url(context)
        returned_client = driver._get_client(None, context)
        self.assertThat(
            Client,
            MockCalledOnceWith(
                endpoint=endpoint,
                project=context["project"],
                cert=(MAAS_CERTIFICATE, MAAS_PRIVATE_KEY),
                verify=False,
            ),
        )
        self.assertThat(
            client.authenticate, MockCalledOnceWith(context["password"])
        )
        self.assertEqual(client, returned_client)

    def test_get_client_default_project(self):
        context = self.make_parameters_context()
        context.pop("project")
        Client = self.patch(lxd_module, "Client")
        client = Client.return_value
        client.has_api_extension.return_value = True
        client.trusted = False
        driver = lxd_module.LXDPodDriver()
        endpoint = driver.get_url(context)
        returned_client = driver._get_client(None, context)
        self.assertThat(
            Client,
            MockCalledOnceWith(
                endpoint=endpoint,
                project="default",
                cert=(MAAS_CERTIFICATE, MAAS_PRIVATE_KEY),
                verify=False,
            ),
        )
        self.assertThat(
            client.authenticate, MockCalledOnceWith(context["password"])
        )
        self.assertEqual(client, returned_client)

    def test_get_client_override_project(self):
        context = self.make_parameters_context()
        Client = self.patch(lxd_module, "Client")
        client = Client.return_value
        client.has_api_extension.return_value = True
        client.trusted = False
        driver = lxd_module.LXDPodDriver()
        endpoint = driver.get_url(context)
        project = factory.make_string()
        returned_client = driver._get_client(None, context, project=project)
        self.assertThat(
            Client,
            MockCalledOnceWith(
                endpoint=endpoint,
                project=project,
                cert=(MAAS_CERTIFICATE, MAAS_PRIVATE_KEY),
                verify=False,
            ),
        )
        self.assertThat(
            client.authenticate, MockCalledOnceWith(context["password"])
        )
        self.assertEqual(client, returned_client)

    def test_get_client_raises_error_when_not_trusted_and_no_password(self):
        context = self.make_parameters_context()
        context["password"] = None
        pod_id = factory.make_name("pod_id")
        Client = self.patch(lxd_module, "Client")
        client = Client.return_value
        client.trusted = False
        driver = lxd_module.LXDPodDriver()
        error_msg = f"Pod {pod_id}: Certificate is not trusted and no password was given."
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            driver._get_client(pod_id, context)

    def test_get_client_raises_error_when_cannot_connect(self):
        context = self.make_parameters_context()
        pod_id = factory.make_name("pod_id")
        Client = self.patch(lxd_module, "Client")
        Client.side_effect = lxd_module.ClientConnectionFailed()
        driver = lxd_module.LXDPodDriver()
        error_msg = f"Pod {pod_id}: Failed to connect to the LXD REST API."
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            driver._get_client(pod_id, context)

    def test_get_machine(self):
        context = self.make_parameters_context()
        driver = lxd_module.LXDPodDriver()
        Client = self.patch(driver, "_get_client")
        client = Client.return_value
        mock_machine = Mock()
        client.virtual_machines.get.return_value = mock_machine
        returned_machine = driver._get_machine(None, context)
        self.assertThat(Client, MockCalledOnceWith(None, context))
        self.assertEqual(mock_machine, returned_machine)

    def test_get_machine_raises_error_when_machine_not_found(self):
        context = self.make_parameters_context()
        pod_id = factory.make_name("pod_id")
        instance_name = context.get("instance_name")
        driver = lxd_module.LXDPodDriver()
        Client = self.patch(driver, "_get_client")
        client = Client.return_value
        client.virtual_machines.get.side_effect = lxd_module.NotFound("Error")
        error_msg = f"Pod {pod_id}: LXD VM {instance_name} not found."
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            driver._get_machine(pod_id, context)

    @inlineCallbacks
    def test_power_on(self):
        context = self.make_parameters_context()
        driver = lxd_module.LXDPodDriver()
        mock_machine = self.patch(driver, "_get_machine").return_value
        mock_machine.status_code = 110
        yield driver.power_on(None, context)
        self.assertThat(mock_machine.start, MockCalledOnceWith())

    @inlineCallbacks
    def test_power_off(self):
        context = self.make_parameters_context()
        driver = lxd_module.LXDPodDriver()
        mock_machine = self.patch(driver, "_get_machine").return_value
        mock_machine.status_code = 103
        yield driver.power_off(None, context)
        self.assertThat(mock_machine.stop, MockCalledOnceWith())

    @inlineCallbacks
    def test_power_query(self):
        context = self.make_parameters_context()
        driver = lxd_module.LXDPodDriver()
        mock_machine = self.patch(driver, "_get_machine").return_value
        mock_machine.status_code = 103
        state = yield driver.power_query(None, context)
        self.assertThat(state, Equals("on"))

    @inlineCallbacks
    def test_power_query_raises_error_on_unknown_state(self):
        context = self.make_parameters_context()
        pod_id = factory.make_name("pod_id")
        driver = lxd_module.LXDPodDriver()
        mock_machine = self.patch(driver, "_get_machine").return_value
        mock_machine.status_code = 106
        error_msg = f"Pod {pod_id}: Unknown power status code: {mock_machine.status_code}"
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            yield driver.power_query(pod_id, context)

    @inlineCallbacks
    def test_discover_requires_client_to_have_vm_support(self):
        context = self.make_parameters_context()
        driver = lxd_module.LXDPodDriver()
        Client = self.patch(lxd_module, "Client")
        client = Client.return_value
        client.has_api_extension.return_value = False
        error_msg = "Please upgrade your LXD host to *."
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            yield driver.discover(None, context)
        self.assertThat(
            client.has_api_extension, MockCalledOnceWith("virtual-machines")
        )

    @inlineCallbacks
    def test_discover(self):
        context = self.make_parameters_context()
        driver = lxd_module.LXDPodDriver()
        Client = self.patch(lxd_module, "Client")
        client = Client.return_value
        client.has_api_extension.return_value = True
        name = factory.make_name("hostname")
        client.host_info = {
            "environment": {
                "architectures": ["x86_64", "i686"],
                "kernel_architecture": "x86_64",
                "server_name": name,
            }
        }
        mac_address = factory.make_mac_address()
        lxd_net1 = Mock(type="physical")
        lxd_net1.state.return_value = Mock(hwaddr=mac_address)
        # virtual interfaces are excluded
        lxd_net2 = Mock(type="bridge")
        lxd_net2.state.return_value = Mock(hwaddr=factory.make_mac_address())
        client.networks.all.return_value = [lxd_net1, lxd_net2]
        discovered_pod = yield driver.discover(None, context)
        self.assertItemsEqual(["amd64/generic"], discovered_pod.architectures)
        self.assertEqual(name, discovered_pod.name)
        self.assertItemsEqual([mac_address], discovered_pod.mac_addresses)
        self.assertEqual(-1, discovered_pod.cores)
        self.assertEqual(-1, discovered_pod.cpu_speed)
        self.assertEqual(-1, discovered_pod.memory)
        self.assertEqual(0, discovered_pod.local_storage)
        self.assertEqual(-1, discovered_pod.local_disks)
        self.assertEqual(-1, discovered_pod.iscsi_storage)
        self.assertEqual(-1, discovered_pod.hints.cores)
        self.assertEqual(-1, discovered_pod.hints.cpu_speed)
        self.assertEqual(-1, discovered_pod.hints.local_storage)
        self.assertEqual(-1, discovered_pod.hints.local_disks)
        self.assertEqual(-1, discovered_pod.hints.iscsi_storage)
        self.assertItemsEqual(
            [
                Capabilities.COMPOSABLE,
                Capabilities.DYNAMIC_LOCAL_STORAGE,
                Capabilities.OVER_COMMIT,
                Capabilities.STORAGE_POOLS,
            ],
            discovered_pod.capabilities,
        )
        self.assertItemsEqual([], discovered_pod.machines)
        self.assertItemsEqual([], discovered_pod.tags)
        self.assertItemsEqual([], discovered_pod.storage_pools)

    @inlineCallbacks
    def test_discover_includes_unknown_type_interfaces(self):
        context = self.make_parameters_context()
        driver = lxd_module.LXDPodDriver()
        Client = self.patch(lxd_module, "Client")
        client = Client.return_value
        client.has_api_extension.return_value = True
        name = factory.make_name("hostname")
        client.host_info = {
            "environment": {
                "architectures": ["x86_64", "i686"],
                "kernel_architecture": "x86_64",
                "server_name": name,
            }
        }
        mac_address = factory.make_mac_address()
        lxd_network = Mock(type="unknown")
        lxd_network.state.return_value = Mock(hwaddr=mac_address)
        client.networks.all.return_value = [lxd_network]
        discovered_pod = yield driver.discover(None, context)
        self.assertEqual(discovered_pod.mac_addresses, [mac_address])

    @inlineCallbacks
    def test_discover_existing_project(self):
        context = self.make_parameters_context()
        project_name = context["project"]
        Client = self.patch(lxd_module, "Client")
        client = Client.return_value
        client.project = project_name
        client.has_api_extension.return_value = True
        client.host_info = {
            "environment": {
                "architectures": ["x86_64", "i686"],
                "kernel_architecture": "x86_64",
                "server_name": factory.make_name("hostname"),
            }
        }
        client.projects.exists.return_value = True
        driver = lxd_module.LXDPodDriver()
        yield driver.discover(None, context)
        client.projects.exists.assert_called_once_with(project_name)
        client.projects.create.assert_not_called()

    @inlineCallbacks
    def test_discover_new_project(self):
        context = self.make_parameters_context()
        project_name = context["project"]
        Client = self.patch(lxd_module, "Client")
        client = Client.return_value
        client.project = project_name
        client.has_api_extension.return_value = True
        client.host_info = {
            "environment": {
                "architectures": ["x86_64", "i686"],
                "kernel_architecture": "x86_64",
                "server_name": factory.make_name("hostname"),
            }
        }
        client.projects.exists.return_value = False
        driver = lxd_module.LXDPodDriver()
        yield driver.discover(None, context)
        client.projects.exists.assert_called_once_with(project_name)
        client.projects.create.assert_called_once_with(
            name=project_name,
            description="Project managed by MAAS",
            config={
                "features.images": "false",
                "features.profiles": "false",
                "features.storage.volumes": "false",
            },
        )

    @inlineCallbacks
    def test_discover_projects_requires_projects_support(self):
        context = self.make_parameters_context()
        driver = lxd_module.LXDPodDriver()
        Client = self.patch(lxd_module, "Client")
        client = Client.return_value
        client.has_api_extension.return_value = False
        error_msg = "Please upgrade your LXD host to *."
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            yield driver.discover_projects(None, context)
        self.assertThat(
            client.has_api_extension, MockCalledOnceWith("projects")
        )

    @inlineCallbacks
    def test_discover_projects(self):
        context = self.make_parameters_context()
        driver = lxd_module.LXDPodDriver()
        Client = self.patch(lxd_module, "Client")
        client = Client.return_value
        client.has_api_extension.return_value = True
        name = factory.make_name("hostname")
        client.host_info = {
            "environment": {
                "architectures": ["x86_64", "i686"],
                "kernel_architecture": "x86_64",
                "server_name": name,
            }
        }
        proj1 = Mock()
        proj1.name = "proj1"
        proj1.description = "Project 1"
        proj2 = Mock()
        proj2.name = "proj2"
        proj2.description = "Project 2"
        client.projects.all.return_value = [proj1, proj2]
        projects = yield driver.discover_projects(None, context)
        self.assertEqual(
            projects,
            [
                {"name": "proj1", "description": "Project 1"},
                {"name": "proj2", "description": "Project 2"},
            ],
        )

    def test_get_discovered_pod_storage_pool(self):
        driver = lxd_module.LXDPodDriver()
        mock_storage_pool = Mock()
        mock_storage_pool.name = factory.make_name("pool")
        mock_storage_pool.driver = "dir"
        mock_storage_pool.config = {
            "size": "61203283968",
            "source": "/home/chb/mnt/l2/disks/default.img",
            "volume.size": "0",
            "zfs.pool_name": "default",
        }
        mock_resources = Mock()
        mock_resources.space = {"used": 207111192576, "total": 306027577344}
        mock_storage_pool.resources.get.return_value = mock_resources
        discovered_pod_storage_pool = driver._get_discovered_pod_storage_pool(
            mock_storage_pool
        )

        self.assertEqual(
            mock_storage_pool.name, discovered_pod_storage_pool.id
        )
        self.assertEqual(
            mock_storage_pool.name, discovered_pod_storage_pool.name
        )
        self.assertEqual(
            mock_storage_pool.config["source"],
            discovered_pod_storage_pool.path,
        )
        self.assertEqual(
            mock_storage_pool.driver, discovered_pod_storage_pool.type
        )
        self.assertEqual(
            mock_resources.space["total"], discovered_pod_storage_pool.storage
        )

    def test_get_discovered_machine(self):
        driver = lxd_module.LXDPodDriver()
        Client = self.patch(lxd_module, "Client")
        client = Client.return_value
        mock_machine = Mock()
        mock_machine.name = factory.make_name("machine")
        mock_machine.architecture = "x86_64"
        expanded_config = {
            "limits.cpu": "2",
            "limits.memory": "1024MiB",
            "volatile.eth0.hwaddr": "00:16:3e:78:be:04",
            "volatile.eth1.hwaddr": "00:16:3e:f9:fc:cb",
            "volatile.eth2.hwaddr": "00:16:3e:f9:fc:cc",
        }
        expanded_devices = {
            "eth0": {
                "name": "eth0",
                "network": "lxdbr0",
                "type": "nic",
            },
            "eth1": {
                "name": "eth1",
                "nictype": "bridged",
                "parent": "br1",
                "type": "nic",
            },
            "eth2": {
                "name": "eth2",
                "nictype": "macvlan",
                "parent": "eno2",
                "type": "nic",
            },
            # SR-IOV devices created by MAAS have an explicit MAC set on
            # the device, so that it knows what the MAC will be.
            "eth3": {
                "name": "eth3",
                "hwaddr": "00:16:3e:f9:fc:dd",
                "nictype": "sriov",
                "parent": "eno3",
                "type": "nic",
            },
            "eth4": {
                "name": "eth4",
                "hwaddr": "00:16:3e:f9:fc:ee",
                "nictype": "sriov",
                "parent": "eno3",
                "vlan": "33",
                "type": "nic",
            },
            # An interface not created by MAAS, thus lacking an explicit
            # MAC.
            "eth5": {
                "name": "eth5",
                "nictype": "sriov",
                "parent": "eno3",
                "vlan": "44",
                "type": "nic",
            },
            "root": {
                "path": "/",
                "pool": "default",
                "type": "disk",
                "size": "20GB",
            },
        }
        mock_machine.expanded_config = expanded_config
        mock_machine.expanded_devices = expanded_devices
        mock_machine.status_code = 102
        mock_storage_pool = Mock()
        mock_storage_pool.name = "default"
        mock_storage_pool_resources = Mock()
        mock_storage_pool_resources.space = {
            "used": 207111192576,
            "total": 306027577344,
        }
        mock_storage_pool.resources.get.return_value = (
            mock_storage_pool_resources
        )
        mock_machine.storage_pools.get.return_value = mock_storage_pool
        mock_network = Mock()
        mock_network.type = "bridge"
        mock_network.name = "lxdbr0"
        client.networks.get.return_value = mock_network
        discovered_machine = driver._get_discovered_machine(
            client, mock_machine, [mock_storage_pool]
        )

        self.assertEqual(mock_machine.name, discovered_machine.hostname)
        self.assertEqual("uefi", discovered_machine.bios_boot_method)

        self.assertEqual(
            kernel_to_debian_architecture(mock_machine.architecture),
            discovered_machine.architecture,
        )
        self.assertEqual(
            lxd_module.LXD_VM_POWER_STATE[mock_machine.status_code],
            discovered_machine.power_state,
        )
        self.assertEqual(2, discovered_machine.cores)
        self.assertEqual(1024, discovered_machine.memory)
        self.assertEqual(
            mock_machine.name,
            discovered_machine.power_parameters["instance_name"],
        )
        self.assertEqual(
            discovered_machine.block_devices[0],
            DiscoveredMachineBlockDevice(
                model="QEMU HARDDISK",
                serial="lxd_root",
                id_path="/dev/disk/by-id/scsi-0QEMU_QEMU_HARDDISK_lxd_root",
                size=20 * 1000 ** 3,
                block_size=512,
                tags=[],
                type="physical",
                storage_pool=expanded_devices["root"]["pool"],
                iscsi_target=None,
            ),
        )
        self.assertEqual(
            discovered_machine.interfaces[0],
            DiscoveredMachineInterface(
                mac_address=expanded_config["volatile.eth0.hwaddr"],
                vid=0,
                tags=[],
                boot=True,
                attach_type=InterfaceAttachType.BRIDGE,
                attach_name="lxdbr0",
            ),
        )
        self.assertEqual(
            discovered_machine.interfaces[1],
            DiscoveredMachineInterface(
                mac_address=expanded_config["volatile.eth1.hwaddr"],
                vid=0,
                tags=[],
                boot=False,
                attach_type=InterfaceAttachType.BRIDGE,
                attach_name="br1",
            ),
        )
        self.assertEqual(
            discovered_machine.interfaces[2],
            DiscoveredMachineInterface(
                mac_address=expanded_config["volatile.eth2.hwaddr"],
                vid=0,
                tags=[],
                boot=False,
                attach_type=InterfaceAttachType.MACVLAN,
                attach_name="eno2",
            ),
        )
        self.assertEqual(
            discovered_machine.interfaces[3],
            DiscoveredMachineInterface(
                mac_address=expanded_devices["eth3"]["hwaddr"],
                vid=0,
                tags=[],
                boot=False,
                attach_type=InterfaceAttachType.SRIOV,
                attach_name="eno3",
            ),
        )
        self.assertEqual(
            discovered_machine.interfaces[4],
            DiscoveredMachineInterface(
                mac_address=expanded_devices["eth4"]["hwaddr"],
                vid=33,
                tags=[],
                boot=False,
                attach_type=InterfaceAttachType.SRIOV,
                attach_name="eno3",
            ),
        )
        self.assertEqual(
            discovered_machine.interfaces[5],
            DiscoveredMachineInterface(
                mac_address=None,
                vid=44,
                tags=[],
                boot=False,
                attach_type=InterfaceAttachType.SRIOV,
                attach_name="eno3",
            ),
        )
        self.assertItemsEqual([], discovered_machine.tags)
        self.assertFalse(discovered_machine.hugepages_backed)
        self.assertEqual(discovered_machine.pinned_cores, [])

    def test_get_discovered_machine_project(self):
        driver = lxd_module.LXDPodDriver()
        project = factory.make_string()
        Client = self.patch(lxd_module, "Client")
        client = Client.return_value
        client.project = project
        mock_machine = Mock()
        mock_machine.name = factory.make_name("machine")
        mock_machine.architecture = "x86_64"
        mock_machine.expanded_config = {
            "limits.cpu": "2",
            "limits.memory": "1024MiB",
            "volatile.eth0.hwaddr": "00:16:3e:78:be:04",
        }
        mock_machine.expanded_devices = {}
        mock_machine.status_code = 102
        mock_storage_pool = Mock()
        mock_storage_pool.name = "default"
        mock_storage_pool_resources = Mock()
        mock_storage_pool_resources.space = {
            "used": 207111192576,
            "total": 306027577344,
        }
        mock_storage_pool.resources.get.return_value = (
            mock_storage_pool_resources
        )
        mock_machine.storage_pools.get.return_value = mock_storage_pool
        mock_network = Mock()
        mock_network.type = "bridge"
        mock_network.name = "lxdbr0"
        client.networks.get.return_value = mock_network
        discovered_machine = driver._get_discovered_machine(
            client, mock_machine, [mock_storage_pool]
        )
        self.assertEqual(
            discovered_machine.power_parameters["project"], project
        )

    def test_get_discovered_machine_vm_info(self):
        driver = lxd_module.LXDPodDriver()
        Client = self.patch(lxd_module, "Client")
        client = Client.return_value
        mock_machine = Mock()
        mock_machine.name = factory.make_name("machine")
        mock_machine.architecture = "x86_64"
        expanded_config = {
            "limits.cpu": "0-2",
            "limits.memory.hugepages": "true",
        }
        mock_machine.expanded_config = expanded_config
        mock_machine.expanded_devices = {}
        discovered_machine = driver._get_discovered_machine(
            client, mock_machine, []
        )
        self.assertTrue(discovered_machine.hugepages_backed)
        self.assertEqual(discovered_machine.pinned_cores, [0, 1, 2])

    def test_get_hugepages_info_int_value_as_bool(self):
        driver = lxd_module.LXDPodDriver()
        Client = self.patch(lxd_module, "Client")
        client = Client.return_value
        mock_machine = Mock()
        mock_machine.name = factory.make_name("machine")
        mock_machine.architecture = "x86_64"
        expanded_config = {
            "limits.memory.hugepages": "1",
        }
        mock_machine.expanded_config = expanded_config
        mock_machine.expanded_devices = {}
        discovered_machine = driver._get_discovered_machine(
            client, mock_machine, []
        )
        self.assertTrue(discovered_machine.hugepages_backed)

    def test_get_discovered_machine_sets_power_state_to_unknown_for_unknown(
        self,
    ):
        driver = lxd_module.LXDPodDriver()
        Client = self.patch(lxd_module, "Client")
        client = Client.return_value
        mock_machine = Mock()
        mock_machine.name = factory.make_name("machine")
        mock_machine.architecture = "x86_64"
        expanded_config = {
            "limits.cpu": "2",
            "limits.memory": "1024",
            "volatile.eth0.hwaddr": "00:16:3e:78:be:04",
            "volatile.eth1.hwaddr": "00:16:3e:f9:fc:cb",
        }
        expanded_devices = {
            "eth0": {
                "name": "eth0",
                "nictype": "bridged",
                "parent": "lxdbr0",
                "type": "nic",
            },
            "eth1": {
                "name": "eth1",
                "nictype": "bridged",
                "parent": "virbr1",
                "type": "nic",
            },
            "root": {"path": "/", "pool": "default", "type": "disk"},
        }
        mock_machine.expanded_config = expanded_config
        mock_machine.expanded_devices = expanded_devices
        mock_machine.status_code = 100
        mock_storage_pool = Mock()
        mock_storage_pool.name = "default"
        mock_storage_pool_resources = Mock()
        mock_storage_pool_resources.space = {
            "used": 207111192576,
            "total": 306027577344,
        }
        mock_storage_pool.resources.get.return_value = (
            mock_storage_pool_resources
        )
        mock_machine.storage_pools.get.return_value = mock_storage_pool
        discovered_machine = driver._get_discovered_machine(
            client, mock_machine, [mock_storage_pool]
        )
        self.assertEqual("unknown", discovered_machine.power_state)

    @inlineCallbacks
    def test_get_commissioning_data(self):
        driver = lxd_module.LXDPodDriver()
        context = self.make_parameters_context()
        Client = self.patch(lxd_module, "Client")
        client = Client.return_value
        client.resources = {
            factory.make_name("rkey"): factory.make_name("rvalue")
        }
        client.host_info = {
            factory.make_name("hkey"): factory.make_name("hvalue")
        }

        def mock_iface(name, mac):
            iface = Mock()
            iface.state.return_value = {"hwaddr": mac}
            iface.configure_mock(name=name)
            return iface

        client.networks.all.return_value = [
            mock_iface("eth0", "aa:bb:cc:dd:ee:ff"),
            mock_iface("eth1", "ff:ee:dd:cc:bb:aa"),
        ]
        commissioning_data = yield driver.get_commissioning_data(1, context)

        self.assertDictEqual(
            {
                LXD_OUTPUT_NAME: {
                    **client.host_info,
                    "resources": client.resources,
                    "networks": {
                        "eth0": {"hwaddr": "aa:bb:cc:dd:ee:ff"},
                        "eth1": {"hwaddr": "ff:ee:dd:cc:bb:aa"},
                    },
                }
            },
            commissioning_data,
        )

    def test_get_usable_storage_pool(self):
        driver = lxd_module.LXDPodDriver()
        pools = [
            Mock(
                **{
                    "resources.get.return_value": Mock(
                        space={"total": 2 ** i * 2048, "used": 2 * i * 1500}
                    )
                }
            )
            for i in range(3)
        ]
        # Override name attribute on Mock and calculate the available
        for pool in pools:
            type(pool).name = PropertyMock(
                return_value=factory.make_name("pool_name")
            )
        disk = RequestedMachineBlockDevice(
            size=2048,  # Only the first pool will have this availability.
            tags=[],
        )
        self.assertEqual(
            pools[0], driver._get_usable_storage_pool(disk, pools)
        )

    def test_get_usable_storage_pool_filters_on_disk_tags(self):
        driver = lxd_module.LXDPodDriver()
        pools = [
            Mock(
                **{
                    "resources.get.return_value": Mock(
                        space={"total": 2 ** i * 2048, "used": 2 * i * 1500}
                    )
                }
            )
            for i in range(3)
        ]
        # Override name attribute on Mock and calculate the available
        for pool in pools:
            type(pool).name = PropertyMock(
                return_value=factory.make_name("pool_name")
            )
        selected_pool = pools[1]
        disk = RequestedMachineBlockDevice(
            size=1024, tags=[selected_pool.name]
        )
        self.assertEqual(
            pools[1], driver._get_usable_storage_pool(disk, pools)
        )

    def test_get_usable_storage_pool_filters_on_disk_tags_raises_invalid(self):
        driver = lxd_module.LXDPodDriver()
        pools = [
            Mock(
                **{
                    "resources.get.return_value": Mock(
                        space={"total": 2 ** i * 2048, "used": 2 * i * 1500}
                    )
                }
            )
            for i in range(3)
        ]
        # Override name attribute on Mock and calculate the available
        for pool in pools:
            type(pool).name = PropertyMock(
                return_value=factory.make_name("pool_name")
            )
        selected_pool = pools[1]
        disk = RequestedMachineBlockDevice(
            size=2048, tags=[selected_pool.name]
        )
        self.assertRaises(
            PodInvalidResources, driver._get_usable_storage_pool, disk, pools
        )

    def test_get_usable_storage_pool_filters_on_default_pool_name(self):
        driver = lxd_module.LXDPodDriver()
        pools = [
            Mock(
                **{
                    "resources.get.return_value": Mock(
                        space={"total": 2 ** i * 2048, "used": 2 * i * 1500}
                    )
                }
            )
            for i in range(3)
        ]
        # Override name attribute on Mock and calculate the available
        for pool in pools:
            type(pool).name = PropertyMock(
                return_value=factory.make_name("pool_name")
            )
        disk = RequestedMachineBlockDevice(size=2048, tags=[])
        self.assertEqual(
            pools[0],
            driver._get_usable_storage_pool(disk, pools, pools[0].name),
        )

    def test_get_usable_storage_pool_filters_on_default_pool_name_raises_invalid(
        self,
    ):
        driver = lxd_module.LXDPodDriver()
        pools = [
            Mock(
                **{
                    "resources.get.return_value": Mock(
                        space={"total": 2 ** i * 2048, "used": 2 * i * 1500}
                    )
                }
            )
            for i in range(3)
        ]
        # Override name attribute on Mock and calculate the available
        for pool in pools:
            type(pool).name = PropertyMock(
                return_value=factory.make_name("pool_name")
            )
        disk = RequestedMachineBlockDevice(size=2048 + 1, tags=[])
        self.assertRaises(
            PodInvalidResources,
            driver._get_usable_storage_pool,
            disk,
            pools,
            pools[0].name,
        )

    @inlineCallbacks
    def test_compose_errors_if_not_default_or_maas_profile(self):
        pod_id = factory.make_name("pod_id")
        driver = lxd_module.LXDPodDriver()
        Client = self.patch(driver, "_get_client")
        client = Client.return_value
        client.profiles.get.side_effect = [
            lxd_module.NotFound("Error"),
            lxd_module.NotFound("Error"),
        ]
        error_msg = (
            f"Pod {pod_id}: MAAS needs LXD to have either a 'maas' "
            "profile or a 'default' profile, defined."
        )
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            yield driver.compose(pod_id, {}, None)

    @inlineCallbacks
    def test_compose_no_interface_constraints(self):
        pod_id = factory.make_name("pod_id")
        context = self.make_parameters_context()
        request = make_requested_machine()
        driver = lxd_module.LXDPodDriver()
        Client = self.patch(driver, "_get_client")
        client = Client.return_value
        mock_profile = Mock()
        mock_profile.name = random.choice(["maas", "default"])
        profile_devices = {
            "eth0": {
                "name": "eth0",
                "nictype": "bridged",
                "parent": "lxdbr0",
                "type": "nic",
            },
            "eth1": {
                "boot.priority": "1",
                "name": "eth1",
                "nictype": "bridged",
                "parent": "virbr1",
                "type": "nic",
            },
            "root": {
                "boot.priority": "0",
                "path": "/",
                "pool": "default",
                "type": "disk",
                "size": "20GB",
            },
        }
        mock_profile.devices = profile_devices
        client.profiles.get.return_value = mock_profile
        mock_storage_pools = Mock()
        client.storage_pools.all.return_value = mock_storage_pools
        mock_get_usable_storage_pool = self.patch(
            driver, "_get_usable_storage_pool"
        )
        usable_pool = Mock()
        usable_pool.name = factory.make_name("pool")
        mock_get_usable_storage_pool.return_value = usable_pool
        mock_machine = Mock()
        client.virtual_machines.create.return_value = mock_machine
        mock_get_discovered_machine = self.patch(
            driver, "_get_discovered_machine"
        )
        mock_get_discovered_machine.return_value = sentinel.discovered_machine
        definition = {
            "name": request.hostname,
            "architecture": debian_to_kernel_architecture(
                request.architecture
            ),
            "config": {
                "limits.cpu": str(request.cores),
                "limits.memory": str(request.memory * 1024 ** 2),
                "limits.memory.hugepages": "false",
                "security.secureboot": "false",
            },
            "profiles": [mock_profile.name],
            "source": {"type": "none"},
            "devices": {
                "root": {
                    "path": "/",
                    "type": "disk",
                    "pool": usable_pool.name,
                    "size": str(request.block_devices[0].size),
                    "boot.priority": "0",
                },
                "eth1": profile_devices["eth1"],
                "eth0": {"type": "none"},
            },
        }

        discovered_machine, empty_hints = yield driver.compose(
            pod_id, context, request
        )
        self.assertThat(
            client.virtual_machines.create,
            MockCalledOnceWith(definition, wait=True),
        )
        self.assertEqual(sentinel.discovered_machine, discovered_machine)
        self.assertThat(
            empty_hints,
            MatchesAll(
                IsInstance(DiscoveredPodHints),
                MatchesStructure(
                    cores=Equals(-1),
                    cpu_speed=Equals(-1),
                    memory=Equals(-1),
                    local_storage=Equals(-1),
                    local_disks=Equals(-1),
                    iscsi_storage=Equals(-1),
                ),
            ),
        )

    @inlineCallbacks
    def test_compose_multiple_disks(self):
        pod_id = factory.make_name("pod_id")
        context = self.make_parameters_context()
        request = make_requested_machine(num_disks=2)
        driver = lxd_module.LXDPodDriver()
        Client = self.patch(driver, "_get_client")
        client = Client.return_value
        mock_profile = Mock()
        mock_profile.name = random.choice(["maas", "default"])
        profile_devices = {
            "eth0": {
                "name": "eth0",
                "nictype": "bridged",
                "parent": "lxdbr0",
                "type": "nic",
            },
        }
        mock_profile.devices = profile_devices
        client.profiles.get.return_value = mock_profile
        mock_storage_pools = Mock()
        client.storage_pools.all.return_value = mock_storage_pools
        mock_get_usable_storage_pool = self.patch(
            driver, "_get_usable_storage_pool"
        )
        # a volume is created for the second disk
        volume = Mock()
        volume.name = factory.make_name("vol")
        usable_pool = Mock()
        usable_pool.name = factory.make_name("pool")
        usable_pool.volumes.create.return_value = volume
        mock_get_usable_storage_pool.return_value = usable_pool
        mock_machine = Mock()
        client.virtual_machines.create.return_value = mock_machine
        mock_get_discovered_machine = self.patch(
            driver, "_get_discovered_machine"
        )
        mock_get_discovered_machine.return_value = sentinel.discovered_machine
        definition = {
            "name": request.hostname,
            "architecture": debian_to_kernel_architecture(
                request.architecture
            ),
            "config": {
                "limits.cpu": str(request.cores),
                "limits.memory": str(request.memory * 1024 ** 2),
                "limits.memory.hugepages": "false",
                "security.secureboot": "false",
            },
            "profiles": [mock_profile.name],
            "source": {"type": "none"},
            "devices": {
                "root": {
                    "path": "/",
                    "type": "disk",
                    "pool": usable_pool.name,
                    "size": str(request.block_devices[0].size),
                    "boot.priority": "0",
                },
                "disk1": {
                    "path": "",
                    "type": "disk",
                    "pool": usable_pool.name,
                    "source": volume.name,
                },
                "eth0": {
                    "boot.priority": "1",
                    "name": "eth0",
                    "nictype": "bridged",
                    "parent": "lxdbr0",
                    "type": "nic",
                },
            },
        }

        discovered_machine, empty_hints = yield driver.compose(
            pod_id, context, request
        )
        self.assertThat(
            client.virtual_machines.create,
            MockCalledOnceWith(definition, wait=True),
        )
        self.assertEqual(sentinel.discovered_machine, discovered_machine)
        self.assertThat(
            empty_hints,
            MatchesAll(
                IsInstance(DiscoveredPodHints),
                MatchesStructure(
                    cores=Equals(-1),
                    cpu_speed=Equals(-1),
                    memory=Equals(-1),
                    local_storage=Equals(-1),
                    local_disks=Equals(-1),
                    iscsi_storage=Equals(-1),
                ),
            ),
        )
        # a volume for the additional disk is created
        usable_pool.volumes.create.assert_called_with(
            "custom",
            {
                "name": ANY,
                "content_type": "block",
                "config": {
                    "size": str(request.block_devices[1].size),
                },
            },
        )

    @inlineCallbacks
    def test_compose_multiple_interface_constraints(self):
        pod_id = factory.make_name("pod_id")
        context = self.make_parameters_context()
        request = make_requested_machine()
        request.interfaces = [
            RequestedMachineInterface(
                ifname=factory.make_name("ifname"),
                attach_name=factory.make_name("bridge_name"),
                attach_type="bridge",
                attach_options=None,
            )
            for _ in range(3)
        ]
        # LXD uses 'bridged' while MAAS uses 'bridge' so convert
        # the nictype as this is what we expect from LXDPodDriver.compose.
        expected_interfaces = [
            {
                "name": request.interfaces[i].ifname,
                "parent": request.interfaces[i].attach_name,
                "nictype": "bridged",
                "type": "nic",
            }
            for i in range(3)
        ]
        expected_interfaces[0]["boot.priority"] = "1"
        driver = lxd_module.LXDPodDriver()
        Client = self.patch(driver, "_get_client")
        client = Client.return_value
        mock_profile = Mock()
        mock_profile.name = random.choice(["maas", "default"])
        profile_devices = {
            "eth0": {
                "name": "eth0",
                "nictype": "bridged",
                "parent": "lxdbr0",
                "type": "nic",
            },
            "eth1": {
                "boot.priority": "1",
                "name": "eth1",
                "nictype": "bridged",
                "parent": "virbr1",
                "type": "nic",
            },
            "root": {
                "boot.priority": "0",
                "path": "/",
                "pool": "default",
                "type": "disk",
                "size": "20GB",
            },
        }
        mock_profile.devices = profile_devices
        client.profiles.get.return_value = mock_profile
        mock_storage_pools = Mock()
        client.storage_pools.all.return_value = mock_storage_pools
        mock_get_usable_storage_pool = self.patch(
            driver, "_get_usable_storage_pool"
        )
        usable_pool = Mock()
        usable_pool.name = factory.make_name("pool")
        mock_get_usable_storage_pool.return_value = usable_pool
        mock_machine = Mock()
        client.virtual_machines.create.return_value = mock_machine
        mock_get_discovered_machine = self.patch(
            driver, "_get_discovered_machine"
        )
        mock_get_discovered_machine.return_value = sentinel.discovered_machine
        definition = {
            "name": request.hostname,
            "architecture": debian_to_kernel_architecture(
                request.architecture
            ),
            "config": {
                "limits.cpu": str(request.cores),
                "limits.memory": str(request.memory * 1024 ** 2),
                "limits.memory.hugepages": "false",
                "security.secureboot": "false",
            },
            "profiles": [mock_profile.name],
            "source": {"type": "none"},
            "devices": {
                "root": {
                    "path": "/",
                    "type": "disk",
                    "pool": usable_pool.name,
                    "size": str(request.block_devices[0].size),
                    "boot.priority": "0",
                },
                expected_interfaces[0]["name"]: expected_interfaces[0],
                expected_interfaces[1]["name"]: expected_interfaces[1],
                expected_interfaces[2]["name"]: expected_interfaces[2],
                "eth1": {"type": "none"},
                "eth0": {"type": "none"},
            },
        }

        discovered_machine, empty_hints = yield driver.compose(
            pod_id, context, request
        )
        self.assertThat(
            client.virtual_machines.create,
            MockCalledOnceWith(definition, wait=True),
        )
        self.assertEqual(sentinel.discovered_machine, discovered_machine)
        self.assertThat(
            empty_hints,
            MatchesAll(
                IsInstance(DiscoveredPodHints),
                MatchesStructure(
                    cores=Equals(-1),
                    cpu_speed=Equals(-1),
                    memory=Equals(-1),
                    local_storage=Equals(-1),
                    local_disks=Equals(-1),
                    iscsi_storage=Equals(-1),
                ),
            ),
        )

    @inlineCallbacks
    def test_decompose(self):
        pod_id = factory.make_name("pod_id")
        context = self.make_parameters_context()
        driver = lxd_module.LXDPodDriver()
        Client = self.patch(driver, "_get_client")
        client = Client.return_value
        devices = {
            "root": {
                "path": "/",
                "type": "disk",
                "pool": "default",
            },
        }
        mock_machine = Mock(devices=devices)
        client.virtual_machines.get.return_value = mock_machine
        empty_hints = yield driver.decompose(pod_id, context)

        self.assertThat(
            mock_machine.stop, MockCalledOnceWith(force=True, wait=True)
        )
        self.assertThat(mock_machine.delete, MockCalledOnceWith(wait=True))
        self.assertThat(
            empty_hints,
            MatchesAll(
                IsInstance(DiscoveredPodHints),
                MatchesStructure(
                    cores=Equals(-1),
                    cpu_speed=Equals(-1),
                    memory=Equals(-1),
                    local_storage=Equals(-1),
                    local_disks=Equals(-1),
                    iscsi_storage=Equals(-1),
                ),
            ),
        )

    @inlineCallbacks
    def test_decompose_extra_volumes_warn_if_delete_fails(self):
        pod_id = factory.make_name("pod_id")
        context = self.make_parameters_context()
        driver = lxd_module.LXDPodDriver()
        Client = self.patch(driver, "_get_client")
        client = Client.return_value
        devices = {
            "root": {
                "path": "/",
                "type": "disk",
                "pool": "default",
            },
            "disk1": {
                "path": "",
                "type": "disk",
                "pool": "default",
                "source": "vol",
            },
        }
        mock_machine = Mock(devices=devices, client=client)
        client.virtual_machines.get.return_value = mock_machine
        pool = Mock()
        client.storage_pools.get.return_value = pool
        pool.volumes.get.return_value = None  # volume not found
        mock_log = self.patch(lxd_module, "maaslog")
        yield driver.decompose(pod_id, context)
        mock_log.warning.assert_called_with(
            f"Pod {pod_id}: failed to delete volume vol in pool default"
        )

    @inlineCallbacks
    def test_decompose_removes_extra_volumes(self):
        pod_id = factory.make_name("pod_id")
        context = self.make_parameters_context()
        driver = lxd_module.LXDPodDriver()
        Client = self.patch(driver, "_get_client")
        client = Client.return_value
        devices = {
            "root": {
                "path": "/",
                "type": "disk",
                "pool": "default",
            },
            "disk1": {
                "path": "",
                "type": "disk",
                "pool": "default",
                "source": "vol",
            },
        }
        mock_machine = Mock(devices=devices, client=client)
        client.virtual_machines.get.return_value = mock_machine
        pool = Mock()
        client.storage_pools.get.return_value = pool
        volume = Mock()
        pool.volumes.get.return_value = volume
        yield driver.decompose(pod_id, context)
        pool.volumes.get.assert_called_once_with("custom", "vol")
        volume.delete.assert_called_once()

    @inlineCallbacks
    def test_decompose_on_stopped_instance(self):
        pod_id = factory.make_name("pod_id")
        context = self.make_parameters_context()
        driver = lxd_module.LXDPodDriver()
        Client = self.patch(driver, "_get_client")
        client = Client.return_value
        devices = {
            "root": {
                "path": "/",
                "type": "disk",
                "pool": "default",
            },
        }
        mock_machine = Mock(devices=devices)
        # Simulate the case where the VM is already stopped
        mock_machine.status_code = 102  # 102 - Stopped
        client.virtual_machines.get.return_value = mock_machine
        yield driver.decompose(pod_id, context)

        mock_machine.stop.assert_not_called()
        mock_machine.delete.assert_called_once_with(wait=True)

    @inlineCallbacks
    def test_decompose_missing_vm(self):
        pod_id = factory.make_name("pod_id")
        context = self.make_parameters_context()
        mock_log = self.patch(lxd_module, "maaslog")
        driver = lxd_module.LXDPodDriver()
        Client = self.patch(driver, "_get_client")
        client = Client.return_value
        client.virtual_machines.get.return_value = None
        yield driver.decompose(pod_id, context)
        instance_name = context["instance_name"]
        mock_log.warning.assert_called_with(
            f"Pod {pod_id}: machine {instance_name} not found"
        )


class TestLXDGetNicDevice(MAASTestCase):
    def test_bridged(self):
        interface = RequestedMachineInterface(
            ifname=factory.make_name("ifname"),
            attach_name=factory.make_name("bridge_name"),
            attach_type=InterfaceAttachType.BRIDGE,
        )
        device = lxd_module.get_lxd_nic_device(interface)
        self.assertEqual(
            {
                "name": interface.ifname,
                "parent": interface.attach_name,
                "nictype": "bridged",
                "type": "nic",
            },
            device,
        )

    def test_macvlan(self):
        interface = RequestedMachineInterface(
            ifname=factory.make_name("ifname"),
            attach_name=factory.make_name("bridge_name"),
            attach_type=InterfaceAttachType.MACVLAN,
        )
        device = lxd_module.get_lxd_nic_device(interface)
        self.assertEqual(
            {
                "name": interface.ifname,
                "parent": interface.attach_name,
                "nictype": "macvlan",
                "type": "nic",
            },
            device,
        )

    def test_sriov(self):
        interface = RequestedMachineInterface(
            ifname=factory.make_name("ifname"),
            attach_name=factory.make_name("sriov"),
            attach_type=InterfaceAttachType.SRIOV,
        )
        generated_mac_address = generate_mac_address()
        mock_generate_mac = self.patch(lxd_module, "generate_mac_address")
        mock_generate_mac.return_value = generated_mac_address
        device = lxd_module.get_lxd_nic_device(interface)
        self.assertEqual(
            {
                "name": interface.ifname,
                "hwaddr": generated_mac_address,
                "parent": interface.attach_name,
                "nictype": "sriov",
                "type": "nic",
            },
            device,
        )

    def test_sriov_vlan(self):
        interface = RequestedMachineInterface(
            ifname=factory.make_name("ifname"),
            attach_name=factory.make_name("sriov"),
            attach_type=InterfaceAttachType.SRIOV,
            attach_vlan=42,
        )
        generated_mac_address = generate_mac_address()
        mock_generate_mac = self.patch(lxd_module, "generate_mac_address")
        mock_generate_mac.return_value = generated_mac_address
        device = lxd_module.get_lxd_nic_device(interface)
        self.assertEqual(
            {
                "name": interface.ifname,
                "hwaddr": generated_mac_address,
                "parent": interface.attach_name,
                "nictype": "sriov",
                "type": "nic",
                "vlan": "42",
            },
            device,
        )


class TestGetLXDMachineDefinition(MAASTestCase):
    def test_definition(self):
        request = make_requested_machine()
        definition = lxd_module.get_lxd_machine_definition(
            request,
            "maas-profile",
        )
        self.assertEqual(
            definition,
            {
                "architecture": "x86_64",
                "config": {
                    "limits.cpu": str(request.cores),
                    "limits.memory": str(request.memory * 1024 * 1024),
                    "limits.memory.hugepages": "false",
                    "security.secureboot": "false",
                },
                "name": request.hostname,
                "profiles": ["maas-profile"],
                "source": {"type": "none"},
            },
        )

    def test_hugepages(self):
        request = make_requested_machine(hugepages_backed=True)
        definition = lxd_module.get_lxd_machine_definition(
            request,
            "maas-profile",
        )
        self.assertEqual(
            definition["config"]["limits.memory.hugepages"], "true"
        )

    def test_pinned_cores(self):
        request = make_requested_machine(pinned_cores=[0, 3, 5])
        definition = lxd_module.get_lxd_machine_definition(
            request,
            "maas-profile",
        )
        self.assertEqual(definition["config"]["limits.cpu"], "0,3,5")

    def test_pinned_single(self):
        request = make_requested_machine(pinned_cores=[4])
        definition = lxd_module.get_lxd_machine_definition(
            request,
            "maas-profile",
        )
        self.assertEqual(definition["config"]["limits.cpu"], "4-4")


class TestParseCPUCores(MAASTestCase):
    def test_count(self):
        self.assertEqual(lxd_module._parse_cpu_cores("10"), (10, []))

    def test_list(self):
        self.assertEqual(lxd_module._parse_cpu_cores("0,2,4"), (3, [0, 2, 4]))

    def test_range(self):
        self.assertEqual(lxd_module._parse_cpu_cores("0-3"), (4, [0, 1, 2, 3]))

    def test_range_single(self):
        self.assertEqual(lxd_module._parse_cpu_cores("2-2"), (1, [2]))

    def test_mixed(self):
        self.assertEqual(
            lxd_module._parse_cpu_cores("0,2,10-12,14-16,18-18"),
            (9, [0, 2, 10, 11, 12, 14, 15, 16, 18]),
        )


class TestGetBool(MAASTestCase):
    def test_none(self):
        self.assertFalse(lxd_module._get_bool(None))

    def test_mixed_case(self):
        self.assertTrue(lxd_module._get_bool("tRuE"))

    def test_number(self):
        self.assertTrue(lxd_module._get_bool("1"))

    def test_number_false(self):
        self.assertFalse(lxd_module._get_bool("0"))
