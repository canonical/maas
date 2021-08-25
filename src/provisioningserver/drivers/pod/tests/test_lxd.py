# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from os.path import exists, join
import random
from unittest.mock import ANY, call, MagicMock, Mock, PropertyMock, sentinel

from pylxd.exceptions import LXDAPIException
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
    KnownHostInterface,
)
from provisioningserver.drivers.pod import (
    RequestedMachine,
    RequestedMachineBlockDevice,
    RequestedMachineInterface,
)
from provisioningserver.drivers.pod import lxd as lxd_module
from provisioningserver.maas_certificates import get_maas_cert_tuple
from provisioningserver.refresh.node_info_scripts import LXD_OUTPUT_NAME
from provisioningserver.rpc.exceptions import PodInvalidResources
from provisioningserver.utils import (
    debian_to_kernel_architecture,
    kernel_to_debian_architecture,
)
from provisioningserver.utils.network import generate_mac_address


def make_requested_machine(num_disks=1, known_host_interfaces=None, **kwargs):
    if known_host_interfaces is None:
        known_host_interfaces = [
            KnownHostInterface(
                ifname="lxdbr0",
                attach_type=InterfaceAttachType.BRIDGE,
                attach_name="lxdbr0",
                dhcp_enabled=True,
            ),
        ]
    block_devices = [
        RequestedMachineBlockDevice(
            size=random.randint(1024 ** 3, 4 * 1024 ** 3),
            tags=[factory.make_name("tag")],
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
        known_host_interfaces=known_host_interfaces,
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

    def mock_get_client(self, driver):
        get_client = self.patch(driver, "_get_client")
        client = get_client.return_value.__enter__.return_value
        return get_client, client

    def mock_client(self, trusted=True, fail_trusting=False):
        clients = []

        def make_client(trusted):
            client = MagicMock(trusted=trusted)
            client.host_info = {
                "api_extensions": sorted(lxd_module.LXD_REQUIRED_EXTENSIONS),
                "environment": {
                    "architectures": ["x86_64", "i686"],
                    "kernel_architecture": "x86_64",
                    "server_name": "lxd-server",
                    "server_version": "4.1",
                },
            }
            if fail_trusting:
                mock_response = Mock(status_code=403)
                mock_response.json.return_value = {"error": "auth failed"}
                client.certificates.create.side_effect = LXDAPIException(
                    mock_response
                )
            clients.append(client)
            return client

        client_class = self.patch(lxd_module, "Client")
        if isinstance(trusted, bool):
            client = make_client(trusted)
            client_class.return_value = client
            return client_class, client
        else:
            trusted = list(trusted)
            client_class.side_effect = lambda *args, **kwargs: make_client(
                trusted.pop(0)
            )
            return client_class, clients

    def mock_get_machine(self, driver):
        get_machine = self.patch(driver, "_get_machine")
        return get_machine.return_value.__enter__.return_value

    def make_parameters_context(self, extra=None):
        params = {
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
        if not extra:
            extra = {}
        return {**params, **extra}

    def test_missing_packages(self):
        driver = lxd_module.LXDPodDriver()
        missing = driver.detect_missing_packages()
        self.assertItemsEqual([], missing)

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
        Client, client = self.mock_client()
        driver = lxd_module.LXDPodDriver()
        endpoint = driver.get_url(context)
        with driver._get_client(None, context) as returned_client:
            self.assertThat(
                Client,
                MockCalledOnceWith(
                    endpoint=endpoint,
                    project=context["project"],
                    cert=get_maas_cert_tuple(),
                    verify=False,
                ),
            )
            self.assertIs(client, returned_client)

    def test_get_client_with_certificate_and_key(self):
        context = self.make_parameters_context(
            {"key": "KEY", "certificate": "CERT"}
        )
        Client, client = self.mock_client()
        driver = lxd_module.LXDPodDriver()
        endpoint = driver.get_url(context)
        with driver._get_client(None, context):
            Client.assert_called_once_with(
                endpoint=endpoint,
                project=context["project"],
                cert=ANY,
                verify=False,
            )
            cert_path, key_path = Client.mock_calls[0].kwargs["cert"]
            with open(cert_path) as fd:
                self.assertEqual("CERT", fd.read())
            with open(key_path) as fd:
                self.assertEqual("KEY", fd.read())
        # the files are removed after the client is done
        self.assertFalse(exists(cert_path))
        self.assertFalse(exists(key_path))

    def test_get_client_with_certificate_and_key_trust_provided(self):
        context = self.make_parameters_context(
            {"key": "KEY", "certificate": "CERT"}
        )
        del context["password"]
        Client, clients = self.mock_client(trusted=(False, True, True))
        driver = lxd_module.LXDPodDriver()
        endpoint = driver.get_url(context)
        with driver._get_client(None, context) as returned_client:
            Client.assert_has_calls(
                [
                    call(
                        endpoint=endpoint,
                        project=context["project"],
                        cert=ANY,
                        verify=False,
                    ),
                    call(
                        endpoint=endpoint,
                        project=context["project"],
                        cert=get_maas_cert_tuple(),
                        verify=False,
                    ),
                    call(
                        endpoint=endpoint,
                        project=context["project"],
                        cert=ANY,
                        verify=False,
                    ),
                ]
            )
            # provided certs are used, not builtin ones
            self.assertNotEqual(returned_client.cert, get_maas_cert_tuple())
            # the builtin cert is used to try to trust the provided one
            client_with_builtin_certs = clients[1]
            client_with_builtin_certs.certificates.create.assert_called_with(
                "", b"CERT"
            )

    def test_get_client_with_certificate_and_key_untrusted(self):
        context = self.make_parameters_context(
            {"key": "KEY", "certificate": "CERT"}
        )
        del context["password"]
        Client, clients = self.mock_client(
            trusted=(False, True), fail_trusting=True
        )
        driver = lxd_module.LXDPodDriver()
        pod_id = factory.make_name("pod_id")
        error_msg = f"VM Host {pod_id}: Certificate is not trusted and no password was given"
        endpoint = driver.get_url(context)
        with ExpectedException(
            lxd_module.LXDPodError, error_msg
        ), driver._get_client(pod_id, context) as returned_client:
            Client.assert_has_calls(
                [
                    call(
                        endpoint=endpoint,
                        project=context["project"],
                        cert=ANY,
                        verify=False,
                    ),
                    call(
                        endpoint=endpoint,
                        project=context["project"],
                        cert=get_maas_cert_tuple(),
                        verify=False,
                    ),
                    call(
                        endpoint=endpoint,
                        project=context["project"],
                        cert=ANY,
                        verify=False,
                    ),
                ]
            )
            self.assertFalse(returned_client.trusted)
            # provided certs are used, not builtin ones
            self.assertNotEqual(returned_client.cert, get_maas_cert_tuple())
            # the builtin cert is used to try to trust the provided one
            client_with_builtin_certs = clients[1]
            client_with_builtin_certs.certificates.create.assert_called_with(
                "", b"CERT"
            )

    def test_get_client_default_project(self):
        context = self.make_parameters_context()
        context.pop("project")
        Client, client = self.mock_client()
        driver = lxd_module.LXDPodDriver()
        endpoint = driver.get_url(context)
        with driver._get_client(None, context) as returned_client:
            Client.assert_called_once_with(
                endpoint=endpoint,
                project="default",
                cert=get_maas_cert_tuple(),
                verify=False,
            )
            self.assertEqual(client, returned_client)

    def test_get_client_override_project(self):
        context = self.make_parameters_context()
        Client, client = self.mock_client()
        driver = lxd_module.LXDPodDriver()
        endpoint = driver.get_url(context)
        project = factory.make_string()
        with driver._get_client(
            None, context, project=project
        ) as returned_client:
            Client.assert_called_once_with(
                endpoint=endpoint,
                project=project,
                cert=get_maas_cert_tuple(),
                verify=False,
            )
            self.assertEqual(client, returned_client)

    def test_get_client_raises_error_when_not_trusted_and_no_password(self):
        context = self.make_parameters_context({"password": None})
        pod_id = factory.make_name("pod_id")
        _, client = self.mock_client(trusted=False)
        driver = lxd_module.LXDPodDriver()
        error_msg = f"VM Host {pod_id}: Certificate is not trusted and no password was given"
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            with driver._get_client(pod_id, context):
                self.fail("should not get here")

    def test_get_client_raises_error_when_cannot_connect(self):
        context = self.make_parameters_context()
        pod_id = factory.make_name("pod_id")
        Client, _ = self.mock_client()
        Client.side_effect = lxd_module.ClientConnectionFailed()
        driver = lxd_module.LXDPodDriver()
        error_msg = f"Pod {pod_id}: Failed to connect to the LXD REST API."
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            with driver._get_client(pod_id, context):
                self.fail("should not get here")

    def test_get_client_raises_error_when_authenticate_fails(self):
        context = self.make_parameters_context()
        pod_id = factory.make_name("pod_id")
        _, client = self.mock_client(trusted=False)
        mock_response = Mock(status_code=403)
        mock_response.json.return_value = {"error": "auth failed"}
        client.authenticate.side_effect = LXDAPIException(mock_response)
        driver = lxd_module.LXDPodDriver()
        error_msg = (
            f"VM Host {pod_id}: Password authentication failed: auth failed"
        )
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            with driver._get_client(pod_id, context):
                self.fail("should not get here")

    def test_get_machine(self):
        context = self.make_parameters_context()
        driver = lxd_module.LXDPodDriver()
        mock_get_client, client = self.mock_get_client(driver)
        mock_machine = Mock()
        client.virtual_machines.get.return_value = mock_machine
        with driver._get_machine(None, context) as returned_machine:
            mock_get_client.assert_called_once_with(None, context)
            self.assertEqual(mock_machine, returned_machine)

    def test_get_machine_raises_error_when_machine_not_found(self):
        context = self.make_parameters_context()
        pod_id = factory.make_name("pod_id")
        instance_name = context.get("instance_name")
        driver = lxd_module.LXDPodDriver()
        _, client = self.mock_get_client(driver)
        client.virtual_machines.get.side_effect = lxd_module.NotFound("Error")
        error_msg = f"Pod {pod_id}: LXD VM {instance_name} not found."
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            with driver._get_machine(pod_id, context):
                self.fail("should not get here")

    @inlineCallbacks
    def test_power_on(self):
        context = self.make_parameters_context()
        driver = lxd_module.LXDPodDriver()
        mock_machine = self.mock_get_machine(driver)
        mock_machine.status_code = 110
        yield driver.power_on(None, context)
        mock_machine.start.assert_called_once_with()

    @inlineCallbacks
    def test_power_off(self):
        context = self.make_parameters_context()
        driver = lxd_module.LXDPodDriver()
        mock_machine = self.mock_get_machine(driver)
        mock_machine.status_code = 103
        yield driver.power_off(None, context)
        mock_machine.stop.assert_called_once_with()

    @inlineCallbacks
    def test_power_query(self):
        context = self.make_parameters_context()
        driver = lxd_module.LXDPodDriver()
        mock_machine = self.mock_get_machine(driver)
        mock_machine.status_code = 103
        state = yield driver.power_query(None, context)
        self.assertEqual(state, "on")

    @inlineCallbacks
    def test_power_query_raises_error_on_unknown_state(self):
        context = self.make_parameters_context()
        pod_id = factory.make_name("pod_id")
        driver = lxd_module.LXDPodDriver()
        mock_machine = self.mock_get_machine(driver)
        mock_machine.status_code = 106
        error_msg = f"Pod {pod_id}: Unknown power status code: {mock_machine.status_code}"
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            yield driver.power_query(pod_id, context)

    @inlineCallbacks
    def test_discover_checks_required_extensions(self):
        context = self.make_parameters_context()
        driver = lxd_module.LXDPodDriver()
        _, client = self.mock_client()
        client.host_info["api_extensions"].remove("projects")
        error_msg = (
            "Please upgrade your LXD host to 4.16 or higher "
            "to support the following extensions: projects"
        )
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            yield driver.discover(None, context)

    @inlineCallbacks
    def test_discover(self):
        context = self.make_parameters_context()
        driver = lxd_module.LXDPodDriver()
        _, client = self.mock_client()
        mac_address = factory.make_mac_address()
        lxd_net1 = Mock(type="physical")
        lxd_net1.state.return_value = Mock(hwaddr=mac_address)
        # virtual interfaces are excluded
        lxd_net2 = Mock(type="bridge")
        lxd_net2.state.return_value = Mock(hwaddr=factory.make_mac_address())
        client.networks.all.return_value = [lxd_net1, lxd_net2]
        discovered_pod = yield driver.discover(None, context)
        self.assertItemsEqual(["amd64/generic"], discovered_pod.architectures)
        self.assertEqual("lxd-server", discovered_pod.name)
        self.assertEqual(discovered_pod.version, "4.1")
        self.assertItemsEqual([mac_address], discovered_pod.mac_addresses)
        self.assertEqual(-1, discovered_pod.cores)
        self.assertEqual(-1, discovered_pod.cpu_speed)
        self.assertEqual(-1, discovered_pod.memory)
        self.assertEqual(0, discovered_pod.local_storage)
        self.assertEqual(-1, discovered_pod.hints.cores)
        self.assertEqual(-1, discovered_pod.hints.cpu_speed)
        self.assertEqual(-1, discovered_pod.hints.local_storage)
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
        _, client = self.mock_client()
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
        _, client = self.mock_client()
        client.project = project_name
        client.projects.exists.return_value = True
        driver = lxd_module.LXDPodDriver()
        yield driver.discover(None, context)
        client.projects.exists.assert_called_once_with(project_name)
        client.projects.create.assert_not_called()

    @inlineCallbacks
    def test_discover_new_project(self):
        context = self.make_parameters_context()
        project_name = context["project"]
        _, client = self.mock_client()
        client.project = project_name
        client.projects.exists.return_value = False
        driver = lxd_module.LXDPodDriver()
        yield driver.discover(None, context)
        client.projects.exists.assert_called_once_with(project_name)
        client.projects.create.assert_called_once_with(
            name=project_name,
            description="Project managed by MAAS",
            config={
                "features.images": "false",
                "features.profiles": "true",
                "features.storage.volumes": "false",
            },
        )

    @inlineCallbacks
    def test_discover_projects_checks_required_extensions(self):
        context = self.make_parameters_context()
        driver = lxd_module.LXDPodDriver()
        _, client = self.mock_client()
        client.host_info["api_extensions"].remove("virtual-machines")
        error_msg = (
            "Please upgrade your LXD host to 4.16 or higher "
            "to support the following extensions: virtual-machines"
        )
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            yield driver.discover_projects(None, context)

    @inlineCallbacks
    def test_discover_projects(self):
        context = self.make_parameters_context()
        driver = lxd_module.LXDPodDriver()
        _, client = self.mock_client()
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
        _, client = self.mock_client()
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
                storage_pool=expanded_devices["root"]["pool"],
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
        _, client = self.mock_client()
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
        _, client = self.mock_client()
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

    def test_get_discovered_machine_with_request(self):
        request = make_requested_machine(num_disks=2)
        driver = lxd_module.LXDPodDriver()
        _, client = self.mock_get_client(driver)
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
        volume.config = {"size": request.block_devices[1].size}
        usable_pool = Mock()
        usable_pool.name = factory.make_name("pool")
        usable_pool.volumes.create.return_value = volume
        usable_pool.volumes.get.return_value = volume
        mock_get_usable_storage_pool.return_value = usable_pool
        client.storage_pools.get.return_value = usable_pool
        mock_machine = Mock(architecture="x86_64")
        expanded_config = {
            "limits.cpu": "2",
            "limits.memory": "1024",
            "volatile.eth0.hwaddr": "00:16:3e:78:be:04",
        }
        expanded_devices = {
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
        }
        mock_machine.expanded_config = expanded_config
        mock_machine.expanded_devices = expanded_devices
        client.virtual_machines.create.return_value = mock_machine
        discovered_machine = driver._get_discovered_machine(
            client, mock_machine, [usable_pool], request
        )
        # invert sort as the root device shows up last because of name ordering
        discovered_devices = sorted(
            discovered_machine.block_devices, reverse=True
        )
        for idx, device in enumerate(discovered_devices):
            self.assertEqual(device.size, request.block_devices[idx].size)
            self.assertEqual(device.tags, request.block_devices[idx].tags)

    def test_get_hugepages_info_int_value_as_bool(self):
        driver = lxd_module.LXDPodDriver()
        _, client = self.mock_client()
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
        _, client = self.mock_client()
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
        _, client = self.mock_client()
        client.resources = {
            factory.make_name("rkey"): factory.make_name("rvalue")
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
    def test_compose_no_interface_constraints(self):
        pod_id = factory.make_name("pod_id")
        context = self.make_parameters_context()
        request = make_requested_machine()
        driver = lxd_module.LXDPodDriver()
        _, client = self.mock_get_client(driver)
        client.profiles.exists.return_value = False
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
            "profiles": [],
            "source": {"type": "none"},
            "devices": {
                "root": {
                    "path": "/",
                    "type": "disk",
                    "pool": usable_pool.name,
                    "size": str(request.block_devices[0].size),
                    "boot.priority": "0",
                },
                "eth0": {
                    "name": "eth0",
                    "type": "nic",
                    "parent": "lxdbr0",
                    "nictype": "bridged",
                    "boot.priority": "1",
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
                ),
            ),
        )

    @inlineCallbacks
    def test_compose_no_host_known_interfaces(self):
        pod_id = factory.make_name("pod_id")
        context = self.make_parameters_context()
        request = make_requested_machine(known_host_interfaces=[])
        driver = lxd_module.LXDPodDriver()
        _, client = self.mock_get_client(driver)
        client.profiles.exists.return_value = False
        mock_storage_pools = Mock()
        client.storage_pools.all.return_value = mock_storage_pools
        mock_get_usable_storage_pool = self.patch(
            driver, "_get_usable_storage_pool"
        )
        usable_pool = Mock()
        usable_pool.name = factory.make_name("pool")
        mock_get_usable_storage_pool.return_value = usable_pool
        with ExpectedException(
            lxd_module.LXDPodError,
            "No host network to attach VM interfaces to",
        ):
            yield driver.compose(pod_id, context, request)

    @inlineCallbacks
    def test_compose_no_host_known_interfaces_with_dhcp(self):
        pod_id = factory.make_name("pod_id")
        context = self.make_parameters_context()
        request = make_requested_machine()
        for host_interface in request.known_host_interfaces:
            host_interface.dhcp_enabled = False
        driver = lxd_module.LXDPodDriver()
        _, client = self.mock_get_client(driver)
        client.profiles.exists.return_value = False
        mock_storage_pools = Mock()
        client.storage_pools.all.return_value = mock_storage_pools
        mock_get_usable_storage_pool = self.patch(
            driver, "_get_usable_storage_pool"
        )
        usable_pool = Mock()
        usable_pool.name = factory.make_name("pool")
        mock_get_usable_storage_pool.return_value = usable_pool
        with ExpectedException(
            lxd_module.LXDPodError,
            "No host network to attach VM interfaces to",
        ):
            yield driver.compose(pod_id, context, request)

    @inlineCallbacks
    def test_compose_multiple_disks(self):
        pod_id = factory.make_name("pod_id")
        context = self.make_parameters_context()
        request = make_requested_machine(num_disks=2)
        driver = lxd_module.LXDPodDriver()
        _, client = self.mock_get_client(driver)
        client.profiles.exists.return_value = False
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
            "profiles": [],
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
                attach_type=InterfaceAttachType.BRIDGE,
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
        _, client = self.mock_get_client(driver)
        client.profiles.exists.return_value = False
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
            "profiles": [],
            "source": {"type": "none"},
            "devices": {
                "root": {
                    "path": "/",
                    "type": "disk",
                    "pool": usable_pool.name,
                    "size": str(request.block_devices[0].size),
                    "boot.priority": "0",
                },
                **{iface["name"]: iface for iface in expected_interfaces},
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
                ),
            ),
        )

    @inlineCallbacks
    def test_compose_with_maas_profile(self):
        pod_id = factory.make_name("pod_id")
        context = self.make_parameters_context()
        request = make_requested_machine()
        driver = lxd_module.LXDPodDriver()
        _, client = self.mock_get_client(driver)
        mock_profiles_exists = client.profiles.exists
        mock_profiles_exists.return_value = True
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
            "profiles": ["maas"],
            "source": {"type": "none"},
            "devices": {
                "root": {
                    "path": "/",
                    "type": "disk",
                    "pool": usable_pool.name,
                    "size": str(request.block_devices[0].size),
                    "boot.priority": "0",
                },
                "eth0": {
                    "name": "eth0",
                    "type": "nic",
                    "nictype": "bridged",
                    "parent": "lxdbr0",
                    "boot.priority": "1",
                },
            },
        }

        discovered_machine, empty_hints = yield driver.compose(
            pod_id, context, request
        )
        client.virtual_machines.create.assert_called_once_with(
            definition, wait=True
        )
        mock_profiles_exists.assert_called_once_with("maas")

    @inlineCallbacks
    def test_decompose(self):
        pod_id = factory.make_name("pod_id")
        context = self.make_parameters_context()
        driver = lxd_module.LXDPodDriver()
        _, client = self.mock_get_client(driver)
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
                ),
            ),
        )

    @inlineCallbacks
    def test_decompose_extra_volumes_warn_if_delete_fails(self):
        pod_id = factory.make_name("pod_id")
        context = self.make_parameters_context()
        driver = lxd_module.LXDPodDriver()
        _, client = self.mock_get_client(driver)
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
        _, client = self.mock_get_client(driver)
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
        _, client = self.mock_get_client(driver)
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
        _, client = self.mock_get_client(driver)
        client.virtual_machines.get.return_value = None
        yield driver.decompose(pod_id, context)
        instance_name = context["instance_name"]
        mock_log.warning.assert_called_with(
            f"Pod {pod_id}: machine {instance_name} not found"
        )


class TestGetLXDNICDevice(MAASTestCase):
    def test_bridged(self):
        ifname = factory.make_name("ifname")
        interface = RequestedMachineInterface(
            ifname=ifname,
            attach_name=factory.make_name("bridge_name"),
            attach_type=InterfaceAttachType.BRIDGE,
        )
        device = lxd_module.get_lxd_nic_device(
            ifname, interface, sentinel.default_parent
        )
        self.assertEqual(
            {
                "name": ifname,
                "parent": interface.attach_name,
                "nictype": "bridged",
                "type": "nic",
            },
            device,
        )

    def test_macvlan(self):
        ifname = factory.make_name("ifname")
        interface = RequestedMachineInterface(
            ifname=ifname,
            attach_name=factory.make_name("bridge_name"),
            attach_type=InterfaceAttachType.MACVLAN,
        )
        device = lxd_module.get_lxd_nic_device(
            ifname, interface, sentinel.default_parent
        )
        self.assertEqual(
            {
                "name": ifname,
                "parent": interface.attach_name,
                "nictype": "macvlan",
                "type": "nic",
            },
            device,
        )

    def test_sriov(self):
        ifname = factory.make_name("ifname")
        interface = RequestedMachineInterface(
            ifname=ifname,
            attach_name=factory.make_name("sriov"),
            attach_type=InterfaceAttachType.SRIOV,
        )
        generated_mac_address = generate_mac_address()
        mock_generate_mac = self.patch(lxd_module, "generate_mac_address")
        mock_generate_mac.return_value = generated_mac_address
        device = lxd_module.get_lxd_nic_device(
            ifname, interface, sentinel.default_parent
        )
        self.assertEqual(
            {
                "name": ifname,
                "hwaddr": generated_mac_address,
                "parent": interface.attach_name,
                "nictype": "sriov",
                "type": "nic",
            },
            device,
        )

    def test_sriov_vlan(self):
        ifname = factory.make_name("ifname")
        interface = RequestedMachineInterface(
            ifname=ifname,
            attach_name=factory.make_name("sriov"),
            attach_type=InterfaceAttachType.SRIOV,
            attach_vlan=42,
        )
        generated_mac_address = generate_mac_address()
        mock_generate_mac = self.patch(lxd_module, "generate_mac_address")
        mock_generate_mac.return_value = generated_mac_address
        device = lxd_module.get_lxd_nic_device(
            ifname, interface, sentinel.default_parent
        )
        self.assertEqual(
            {
                "name": ifname,
                "hwaddr": generated_mac_address,
                "parent": interface.attach_name,
                "nictype": "sriov",
                "type": "nic",
                "vlan": "42",
            },
            device,
        )

    def test_empty_interface_request_parent_macvlan(self):
        ifname = factory.make_name("ifname")
        interface = RequestedMachineInterface()
        parent_ifname = factory.make_name("ifname")
        default_parent = KnownHostInterface(
            ifname=parent_ifname,
            attach_type=InterfaceAttachType.MACVLAN,
            attach_name=parent_ifname,
        )
        device = lxd_module.get_lxd_nic_device(
            ifname, interface, default_parent
        )
        self.assertEqual(
            device,
            {
                "name": ifname,
                "parent": parent_ifname,
                "nictype": InterfaceAttachType.MACVLAN,
                "type": "nic",
            },
        )

    def test_empty_interface_request_parent_bridge(self):
        ifname = factory.make_name("ifname")
        interface = RequestedMachineInterface()
        parent_ifname = factory.make_name("ifname")
        default_parent = KnownHostInterface(
            ifname=parent_ifname,
            attach_type=InterfaceAttachType.BRIDGE,
            attach_name=parent_ifname,
        )
        device = lxd_module.get_lxd_nic_device(
            ifname, interface, default_parent
        )
        self.assertEqual(
            device,
            {
                "name": ifname,
                "parent": parent_ifname,
                "nictype": "bridged",
                "type": "nic",
            },
        )


class TestGetLXDMachineDefinition(MAASTestCase):
    def test_definition(self):
        request = make_requested_machine()
        definition = lxd_module.get_lxd_machine_definition(request)
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
                "profiles": [],
                "source": {"type": "none"},
            },
        )

    def test_hugepages(self):
        request = make_requested_machine(hugepages_backed=True)
        definition = lxd_module.get_lxd_machine_definition(request)
        self.assertEqual(
            definition["config"]["limits.memory.hugepages"], "true"
        )

    def test_pinned_cores(self):
        request = make_requested_machine(pinned_cores=[0, 3, 5])
        definition = lxd_module.get_lxd_machine_definition(request)
        self.assertEqual(definition["config"]["limits.cpu"], "0,3,5")

    def test_pinned_single(self):
        request = make_requested_machine(pinned_cores=[4])
        definition = lxd_module.get_lxd_machine_definition(request)
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
