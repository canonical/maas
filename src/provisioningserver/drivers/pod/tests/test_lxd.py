# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.pod.lxd`."""

__all__ = []

from os.path import join
from unittest.mock import Mock

from testtools.matchers import Equals, MatchesStructure
from testtools.testcase import ExpectedException
from twisted.internet.defer import inlineCallbacks

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver.drivers.pod import Capabilities
from provisioningserver.drivers.pod import lxd as lxd_module
from provisioningserver.drivers.pod.lxd import LXDPodDriver
from provisioningserver.maas_certificates import (
    MAAS_CERTIFICATE,
    MAAS_PRIVATE_KEY,
)
from provisioningserver.refresh.node_info_scripts import LXD_OUTPUT_NAME
from provisioningserver.utils import kernel_to_debian_architecture


class TestLXDPodDriver(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def test_missing_packages(self):
        driver = LXDPodDriver()
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
        }

    def make_parameters(self, context):
        return (
            context.get("power_address"),
            context.get("instance_name"),
            context.get("password"),
        )

    def test_get_url(self):
        driver = LXDPodDriver()
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

    @inlineCallbacks
    def test__get_client(self):
        context = self.make_parameters_context()
        Client = self.patch(lxd_module, "Client")
        client = Client.return_value
        client.has_api_extension.return_value = True
        client.trusted = False
        driver = LXDPodDriver()
        endpoint = driver.get_url(context)
        returned_client = yield driver.get_client(None, context)
        self.assertThat(
            Client,
            MockCalledOnceWith(
                endpoint=endpoint,
                cert=(MAAS_CERTIFICATE, MAAS_PRIVATE_KEY),
                verify=False,
            ),
        )
        self.assertThat(
            client.authenticate, MockCalledOnceWith(context["password"])
        )
        self.assertEquals(client, returned_client)

    @inlineCallbacks
    def test_get_client_raises_error_when_not_trusted_and_no_password(self):
        context = self.make_parameters_context()
        context["password"] = None
        pod_id = factory.make_name("pod_id")
        Client = self.patch(lxd_module, "Client")
        client = Client.return_value
        client.trusted = False
        driver = LXDPodDriver()
        error_msg = f"Pod {pod_id}: Certificate is not trusted and no password was given."
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            yield driver.get_client(pod_id, context)

    @inlineCallbacks
    def test_get_client_raises_error_when_cannot_connect(self):
        context = self.make_parameters_context()
        pod_id = factory.make_name("pod_id")
        Client = self.patch(lxd_module, "Client")
        Client.side_effect = lxd_module.ClientConnectionFailed()
        driver = LXDPodDriver()
        error_msg = f"Pod {pod_id}: Failed to connect to the LXD REST API."
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            yield driver.get_client(pod_id, context)

    @inlineCallbacks
    def test__get_machine(self):
        context = self.make_parameters_context()
        driver = LXDPodDriver()
        Client = self.patch(driver, "get_client")
        client = Client.return_value
        mock_machine = Mock()
        client.virtual_machines.get.return_value = mock_machine
        returned_machine = yield driver.get_machine(None, context)
        self.assertThat(Client, MockCalledOnceWith(None, context))
        self.assertEquals(mock_machine, returned_machine)

    @inlineCallbacks
    def test_get_machine_raises_error_when_machine_not_found(self):
        context = self.make_parameters_context()
        pod_id = factory.make_name("pod_id")
        instance_name = context.get("instance_name")
        driver = LXDPodDriver()
        Client = self.patch(driver, "get_client")
        client = Client.return_value
        client.virtual_machines.get.side_effect = lxd_module.NotFound("Error")
        error_msg = f"Pod {pod_id}: LXD VM {instance_name} not found."
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            yield driver.get_machine(pod_id, context)

    @inlineCallbacks
    def test__power_on(self):
        context = self.make_parameters_context()
        driver = LXDPodDriver()
        mock_machine = self.patch(driver, "get_machine").return_value
        mock_machine.status_code = 110
        yield driver.power_on(None, context)
        self.assertThat(mock_machine.start, MockCalledOnceWith())

    @inlineCallbacks
    def test__power_off(self):
        context = self.make_parameters_context()
        driver = LXDPodDriver()
        mock_machine = self.patch(driver, "get_machine").return_value
        mock_machine.status_code = 103
        yield driver.power_off(None, context)
        self.assertThat(mock_machine.stop, MockCalledOnceWith())

    @inlineCallbacks
    def test__power_query(self):
        context = self.make_parameters_context()
        driver = LXDPodDriver()
        mock_machine = self.patch(driver, "get_machine").return_value
        mock_machine.status_code = 103
        state = yield driver.power_query(None, context)
        self.assertThat(state, Equals("on"))

    @inlineCallbacks
    def test_power_query_raises_error_on_unknown_state(self):
        context = self.make_parameters_context()
        pod_id = factory.make_name("pod_id")
        driver = LXDPodDriver()
        mock_machine = self.patch(driver, "get_machine").return_value
        mock_machine.status_code = 106
        error_msg = f"Pod {pod_id}: Unknown power status code: {mock_machine.status_code}"
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            yield driver.power_query(pod_id, context)

    @inlineCallbacks
    def test_discover_requires_client_to_have_vm_support(self):
        context = self.make_parameters_context()
        driver = LXDPodDriver()
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
    def test__discover(self):
        context = self.make_parameters_context()
        driver = LXDPodDriver()
        Client = self.patch(lxd_module, "Client")
        client = Client.return_value
        client.has_api_extension.return_value = True
        name = factory.make_name("hostname")
        client.host_info = {
            "environment": {
                "architectures": ["x86_64", "i686"],
                "server_name": name,
            }
        }
        mac_address = factory.make_mac_address()
        client.resources = {
            "network": {"cards": [{"ports": [{"address": mac_address}]}]}
        }
        discovered_pod = yield driver.discover(None, context)
        self.assertItemsEqual(
            ["amd64/generic", "i386/generic"], discovered_pod.architectures
        )
        self.assertEquals(name, discovered_pod.name)
        self.assertItemsEqual([mac_address], discovered_pod.mac_addresses)
        self.assertEquals(-1, discovered_pod.cores)
        self.assertEquals(-1, discovered_pod.cpu_speed)
        self.assertEquals(-1, discovered_pod.memory)
        self.assertEquals(-1, discovered_pod.local_storage)
        self.assertEquals(-1, discovered_pod.local_disks)
        self.assertEquals(-1, discovered_pod.iscsi_storage)
        self.assertEquals(-1, discovered_pod.hints.cores)
        self.assertEquals(-1, discovered_pod.hints.cpu_speed)
        self.assertEquals(-1, discovered_pod.hints.local_storage)
        self.assertEquals(-1, discovered_pod.hints.local_disks)
        self.assertEquals(-1, discovered_pod.hints.iscsi_storage)
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
    def test__get_discovered_pod_storage_pool(self):
        driver = LXDPodDriver()
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
        discovered_pod_storage_pool = yield driver.get_discovered_pod_storage_pool(
            mock_storage_pool
        )

        self.assertEquals(
            mock_storage_pool.name, discovered_pod_storage_pool.id
        )
        self.assertEquals(
            mock_storage_pool.name, discovered_pod_storage_pool.name
        )
        self.assertEquals(
            mock_storage_pool.config["source"],
            discovered_pod_storage_pool.path,
        )
        self.assertEquals(
            mock_storage_pool.driver, discovered_pod_storage_pool.type
        )
        self.assertEquals(
            mock_resources.space["total"], discovered_pod_storage_pool.storage
        )

    @inlineCallbacks
    def test__get_discovered_machine(self):
        driver = LXDPodDriver()
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
        discovered_machine = yield driver.get_discovered_machine(
            mock_machine, [mock_storage_pool], cpu_speed=2500
        )

        self.assertEquals(mock_machine.name, discovered_machine.hostname)

        self.assertEquals(
            kernel_to_debian_architecture(mock_machine.architecture),
            discovered_machine.architecture,
        )
        self.assertEquals(
            lxd_module.LXD_VM_POWER_STATE[mock_machine.status_code],
            discovered_machine.power_state,
        )
        self.assertEquals(2, discovered_machine.cores)
        self.assertEquals(2500, discovered_machine.cpu_speed)
        self.assertEquals(1024, discovered_machine.memory)
        self.assertEquals(
            mock_machine.name,
            discovered_machine.power_parameters["instance_name"],
        )
        self.assertThat(
            discovered_machine.block_devices[0],
            MatchesStructure.byEquality(
                model=None,
                serial=None,
                id_path=lxd_module.LXD_VM_ID_PATH + "root",
                size=10 * 1000 ** 3,
                block_size=512,
                tags=[],
                type="physical",
                storage_pool=expanded_devices["root"]["pool"],
                iscsi_target=None,
            ),
        )
        self.assertThat(
            discovered_machine.interfaces[0],
            MatchesStructure.byEquality(
                mac_address=expanded_config["volatile.eth0.hwaddr"],
                vid=0,
                tags=[],
                boot=True,
                attach_type=expanded_devices["eth0"]["nictype"],
                attach_name="eth0",
            ),
        )
        self.assertThat(
            discovered_machine.interfaces[1],
            MatchesStructure.byEquality(
                mac_address=expanded_config["volatile.eth1.hwaddr"],
                vid=0,
                tags=[],
                boot=False,
                attach_type=expanded_devices["eth1"]["nictype"],
                attach_name="eth1",
            ),
        )
        self.assertItemsEqual([], discovered_machine.tags)

    @inlineCallbacks
    def test_get_discovered_machine_sets_power_state_to_unknown_for_unknown(
        self
    ):
        driver = LXDPodDriver()
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
        discovered_machine = yield driver.get_discovered_machine(
            mock_machine, [mock_storage_pool], cpu_speed=2500
        )

        self.assertEquals("unknown", discovered_machine.power_state)

    @inlineCallbacks
    def test__get_commissioning_data(self):
        driver = LXDPodDriver()
        context = self.make_parameters_context()
        Client = self.patch(lxd_module, "Client")
        client = Client.return_value
        client.resources = {
            factory.make_name("key"): factory.make_name("value")
        }
        commissioning_data = yield driver.get_commissioning_data(1, context)
        self.assertDictEqual(
            {LXD_OUTPUT_NAME: client.resources}, commissioning_data
        )
