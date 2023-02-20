# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import dataclasses
from functools import lru_cache
from os import environ, path
from pathlib import Path
import random
import tempfile
from typing import Optional, Tuple
from unittest.mock import ANY, MagicMock, Mock, PropertyMock, sentinel

from fixtures import EnvironmentVariable, TempDir
from pylxd.exceptions import ClientConnectionFailed, LXDAPIException, NotFound
from requests import Session
from testtools.testcase import ExpectedException
from twisted.internet.defer import inlineCallbacks

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
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
from provisioningserver.refresh.node_info_scripts import (
    COMMISSIONING_OUTPUT_NAME,
    RUN_MACHINE_RESOURCES,
)
from provisioningserver.rpc.exceptions import PodInvalidResources
from provisioningserver.testing.certificates import (
    get_sample_cert,
    SampleCertificateFixture,
)
from provisioningserver.utils import (
    debian_to_kernel_architecture,
    kernel_to_debian_architecture,
)
from provisioningserver.utils.network import generate_mac_address


class FakeErrorResponse:
    def __init__(self, error, status_code=500):
        self.status_code = status_code
        self._error = error

    def json(self):
        return {"error": self._error}


class FakeNetworkState:
    def __init__(self, hwaddr):
        self.hwaddr = hwaddr

    def __iter__(self):
        yield ("hwaddr", self.hwaddr)


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
            size=random.randint(1024**3, 4 * 1024**3),
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


twisted_test_factory = MAASTwistedRunTest.make_factory(
    timeout=environ.get("MAAS_WAIT_FOR_REACTOR", 60.0)
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


@dataclasses.dataclass
class FakeClient:
    """A fake pylxd.Client."""

    fake_lxd: "FakeLXD"
    endpoint: str
    project: str
    cert: Optional[Tuple[str, str]]
    verify: bool
    session: Session

    _PROXIES = (
        "host_info",
        "certificates",
        "networks",
        "profiles",
        "projects",
        "resources",
        "storage_pools",
        "virtual_machines",
    )

    def __post_init__(self):
        self.trusted = False
        self._fail_auth = False
        self.host_info = self.fake_lxd.host_info
        self.api = FakeAPINode(self.session)

    def authenticate(self, password):
        if self._fail_auth:
            raise LXDAPIException(FakeErrorResponse("auth failed", 403))

        self.trusted = True

    def __getattr__(self, name):
        if name in self._PROXIES:
            return getattr(self.fake_lxd, name)
        raise AttributeError(name)


@dataclasses.dataclass
class FakeAPINode:
    """A fake pylxd.client._APINode"""

    session: Session


class FakeLXD:
    """A fake LXD server."""

    def __init__(self, name="lxd-server", clustered=False):
        # global details
        self.host_info = {
            "api_extensions": sorted(lxd_module.LXD_REQUIRED_EXTENSIONS),
            "environment": {
                "architectures": ["x86_64", "i686"],
                "kernel_architecture": "x86_64",
                "server_name": name,
                "server_version": "4.1",
                "server_clustered": clustered,
            },
        }
        self.resources = {}
        # fake collections
        self.certificates = MagicMock()
        self.networks = MagicMock()
        self.profiles = MagicMock()
        self.projects = MagicMock()
        self.storage_pools = MagicMock()
        self.virtual_machines = MagicMock()
        if clustered:
            self.cluster = MagicMock()
            self.cluster.members = MagicMock()

        self._client_behaviors = None

        self.clients = []

    def make_client(
        self,
        endpoint="https://lxd",
        project="default",
        cert=None,
        verify=False,
        session=None,
    ):
        client = FakeClient(
            fake_lxd=self,
            endpoint=endpoint,
            project=project,
            cert=cert,
            verify=verify,
            session=session,
        )

        if self._client_behaviors is not None:
            try:
                behaviors = self._client_behaviors.pop(0)
            except IndexError:
                raise Exception("Requested more clients than expected")
            # apply behaviors
            if behaviors.get("fail_connect"):
                raise ClientConnectionFailed()
            if behaviors.get("fail_auth"):
                client._fail_auth = True
            trusted = behaviors.get("trusted")
            if trusted is not None:
                client.trusted = trusted

        self.clients.append(client)
        return client

    def add_client_behavior(self, **behaviors):
        if self._client_behaviors is None:
            self._client_behaviors = []
        self._client_behaviors.append(behaviors)


class FakeLXDCluster:
    """A fake cluster of LXD servers"""

    def __init__(self, num_pods=1):
        self.pods = [
            FakeLXD(name="lxd-server-%d" % i, clustered=True)
            for i in range(0, num_pods)
        ]
        self.pod_addresses = []

        self.clients = []
        self.client_idx = 0
        for pod in self.pods:
            self.clients.append(pod.make_client)

        self._make_members()

    def _make_members(self):
        members = []
        for i, pod in enumerate(self.pods):
            member = Mock()
            member.architectures = pod.host_info["environment"][
                "architectures"
            ]
            member.server_name = pod.host_info["environment"]["server_name"]
            member.url = "http://lxd-%d" % i
            self.pod_addresses.append(member.url)
            members.append(member)
        for pod in self.pods:
            pod.cluster.members.all.return_value = members

    def make_client(
        self,
        endpoint="https://lxd",
        project="default",
        cert=None,
        verify=False,
        session=None,
    ):
        if self.client_idx == len(self.clients):
            self.client_idx = 0
        client = self.clients[self.client_idx](
            endpoint, project, cert, verify, session
        )
        client._PROXIES += ("cluster", "cluster/members")
        self.client_idx += 1
        return client


def _make_maas_certs(test_case):
    tempdir = Path(test_case.useFixture(TempDir()).path)
    test_case.useFixture(EnvironmentVariable("MAAS_ROOT", str(tempdir)))
    test_case.certs_dir = tempdir / "etc/maas/certificates"
    test_case.certs_dir.mkdir(parents=True)
    maas_cert = test_case.certs_dir / "maas.crt"
    maas_cert.touch()
    maas_key = test_case.certs_dir / "maas.key"
    maas_key.touch()
    return str(maas_cert), str(maas_key)


@lru_cache()
def _make_context(
    with_cert=True, with_password=True, extra=(), sample_cert=None
):
    params = {
        "power_address": f"{factory.make_name('power_address')}:{factory.pick_port()}",
        "instance_name": factory.make_name("instance_name"),
        "project": factory.make_name("project"),
    }
    if with_cert:
        if sample_cert is None:
            sample_cert = get_sample_cert()
        params["certificate"] = sample_cert.certificate_pem()
        params["key"] = sample_cert.private_key_pem()
    if with_password:
        params["password"] = factory.make_name("password")
    return {**params, **dict(extra)}


class TestClusteredLXDPodDriver(MAASTestCase):
    run_tests_with = twisted_test_factory

    def setUp(self):
        super().setUp()
        self.fake_lxd_cluster = FakeLXDCluster(num_pods=3)
        self.fake_lxd = self.fake_lxd_cluster.pods[0]
        self.driver = lxd_module.LXDPodDriver()
        self.driver._pylxd_client_class = self.fake_lxd_cluster.make_client

    def make_maas_certs(self):
        return _make_maas_certs(self)

    def make_context(self, with_cert=True, with_password=True, extra=()):
        return _make_context(with_cert, with_password, extra)

    @inlineCallbacks
    def test_discover_discovers_cluster(self):
        mac_address = factory.make_mac_address()
        lxd_net1 = Mock(type="physical")
        lxd_net1.state.return_value = FakeNetworkState(mac_address)
        # virtual interfaces are excluded
        lxd_net2 = Mock(type="bridge")
        lxd_net2.state.return_value = FakeNetworkState(
            factory.make_mac_address()
        )
        self.fake_lxd.networks.all.return_value = [lxd_net1, lxd_net2]
        context = self.make_context()
        expected_names = [
            pod.host_info["environment"]["server_name"]
            for pod in self.fake_lxd_cluster.pods
        ]
        discovered_cluster = yield self.driver.discover(None, context)
        self.assertEqual(context["instance_name"], discovered_cluster.name)
        self.assertEqual(context["project"], discovered_cluster.project)
        discovered_names = [pod.name for pod in discovered_cluster.pods]
        self.assertCountEqual(expected_names, discovered_names)
        self.assertCountEqual(
            self.fake_lxd_cluster.pod_addresses,
            discovered_cluster.pod_addresses,
        )

    @inlineCallbacks
    def test_compose_specifies_target(self):
        request = make_requested_machine()
        self.fake_lxd.profiles.exists.return_value = True
        mock_storage_pools = Mock()
        self.fake_lxd.storage_pools.all.return_value = mock_storage_pools
        mock_get_usable_storage_pool = self.patch(
            self.driver, "_get_usable_storage_pool"
        )
        usable_pool = Mock()
        usable_pool.name = factory.make_name("pool")
        mock_get_usable_storage_pool.return_value = usable_pool
        mock_machine = Mock()
        self.fake_lxd.virtual_machines.create.return_value = mock_machine
        mock_get_discovered_machine = self.patch(
            self.driver, "_get_discovered_machine"
        )
        mock_get_discovered_machine.return_value = sentinel.discovered_machine
        definition = {
            "name": request.hostname,
            "architecture": debian_to_kernel_architecture(
                request.architecture
            ),
            "config": {
                "limits.cpu": str(request.cores),
                "limits.memory": str(request.memory * 1024**2),
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

        discovered_machine, empty_hints = yield self.driver.compose(
            None, self.make_context(), request
        )
        self.fake_lxd.virtual_machines.create.assert_called_once_with(
            definition,
            wait=True,
            target=self.fake_lxd.host_info["environment"]["server_name"],
        )
        self.fake_lxd.profiles.exists.assert_called_once_with("maas")


class TestLXDPodDriver(MAASTestCase):
    run_tests_with = twisted_test_factory

    def setUp(self):
        super().setUp()
        self.fake_lxd = FakeLXD()
        self.driver = lxd_module.LXDPodDriver()
        self.driver._pylxd_client_class = self.fake_lxd.make_client
        fixture = self.useFixture(
            SampleCertificateFixture(
                Path(tempfile.gettempdir()) / "maas-test-cert.pem"
            )
        )

        self.sample_cert = fixture.cert

    def make_maas_certs(self):
        return _make_maas_certs(self)

    def make_context(self, with_cert=True, with_password=True, extra=()):
        return _make_context(
            with_cert, with_password, extra, sample_cert=self.sample_cert
        )

    def test_missing_packages(self):
        self.assertEqual(self.driver.detect_missing_packages(), [])

    def test_get_url(self):
        context = {"power_address": factory.make_hostname()}

        # Test ip adds protocol and port
        self.assertEqual(
            f"https://{context['power_address']}:8443",
            self.driver.get_url(context),
        )

        # Test ip:port adds protocol
        context["power_address"] += ":1234"
        self.assertEqual(
            f"https://{context['power_address']}",
            self.driver.get_url(context),
        )

        # Test protocol:ip adds port
        context["power_address"] = f"https://{factory.make_hostname()}"
        self.assertEqual(
            f"{context['power_address']}:8443",
            self.driver.get_url(context),
        )

        # Test protocol:ip:port doesn't do anything
        context["power_address"] += ":1234"
        self.assertEqual(
            context.get("power_address"), self.driver.get_url(context)
        )

    def test_get_client(self):
        context = self.make_context()
        with self.driver._get_client(None, context) as client:
            self.assertEqual(client.endpoint, self.driver.get_url(context))
            self.assertEqual(client.project, context["project"])
            self.assertIsInstance(client.cert, tuple)
            self.assertFalse(client.verify)

    def test_get_client_should_not_trust_environment(self):
        context = self.make_context()
        with self.driver._get_client(None, context) as client:
            self.assertFalse(client.api.session.trust_env)

    def test_get_client_no_certificates_no_password(self):
        context = self.make_context(with_cert=False, with_password=False)
        pod_id = factory.make_name("pod_id")
        error_msg = f"VM Host {pod_id}: No certificates available"
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            with self.driver._get_client(pod_id, context):
                self.fail("should not get here")

    def test_get_client_with_certificate_and_key(self):
        context = self.make_context()
        with self.driver._get_client(None, context) as client:
            with open(client.cert[0]) as fd:
                self.assertEqual(fd.read(), context["certificate"])
            with open(client.cert[1]) as fd:
                self.assertEqual(fd.read(), context["key"])
        self.assertFalse(path.exists(client.cert[0]))
        self.assertFalse(path.exists(client.cert[1]))

    def test_get_client_with_invalid_certificate_or_key(self):
        context = self.make_context(
            extra=(("certificate", "random"), ("key", "stuff"))
        )
        pod_id = factory.make_name("pod_id")
        error_msg = f"VM Host {pod_id}: Invalid PEM material"
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            with self.driver._get_client(pod_id, context):
                self.fail("should not get here")

    def test_get_client_with_certificate_and_key_trust_provided(self):
        maas_certs = self.make_maas_certs()
        context = self.make_context(with_password=False)
        self.fake_lxd.add_client_behavior()
        self.fake_lxd.add_client_behavior(trusted=True)
        self.fake_lxd.add_client_behavior(trusted=True)
        with self.driver._get_client(None, context) as client:
            # provided certs are used, not builtin ones
            self.assertNotEqual(client.cert, maas_certs)
        # the builtin cert is used to try to trust the provided one
        client_with_builtin_certs = self.fake_lxd.clients[1]
        self.assertEqual(client_with_builtin_certs.cert, maas_certs)
        client_with_builtin_certs.certificates.create.assert_called_with(
            "", self.sample_cert.certificate_pem().encode("ascii")
        )

    def test_get_client_with_certificate_and_key_untrusted(self):
        maas_certs = self.make_maas_certs()
        context = self.make_context(with_password=False)
        self.fake_lxd.add_client_behavior()
        self.fake_lxd.add_client_behavior(trusted=True)
        self.fake_lxd.add_client_behavior(trusted=False)
        pod_id = factory.make_name("pod_id")
        error_msg = f"VM Host {pod_id}: Certificate is not trusted and no password was given"
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            with self.driver._get_client(pod_id, context) as client:
                self.assertFalse(client.trusted)
                # provided certs are used, not builtin ones
                self.assertNotEqual(client.cert, maas_certs)
        # the builtin cert is used to try to trust the provided one
        client_with_builtin_certs = self.fake_lxd.clients[1]
        client_with_builtin_certs.certificates.create.assert_called_with(
            "", self.sample_cert.certificate_pem().encode("ascii")
        )

    def test_get_client_default_project(self):
        context = self.make_context()
        del context["project"]
        with self.driver._get_client(None, context) as client:
            self.assertEqual(client.project, "default")

    def test_get_client_override_project(self):
        context = self.make_context()
        project = factory.make_string()
        with self.driver._get_client(None, context, project=project) as client:
            self.assertEqual(client.project, project)

    def test_get_client_raises_error_when_not_trusted_and_no_password(self):
        context = self.make_context(with_password=False)
        pod_id = factory.make_name("pod_id")
        error_msg = f"VM Host {pod_id}: Certificate is not trusted and no password was given"
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            with self.driver._get_client(pod_id, context):
                self.fail("should not get here")

    def test_get_client_raises_error_when_cannot_connect(self):
        self.fake_lxd.add_client_behavior(fail_connect=True)
        pod_id = factory.make_name("pod_id")
        error_msg = f"Pod {pod_id}: Failed to connect to the LXD REST API."
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            with self.driver._get_client(pod_id, self.make_context()):
                self.fail("should not get here")

    def test_get_client_raises_error_when_authenticate_fails(self):
        self.fake_lxd.add_client_behavior(fail_auth=True)
        pod_id = factory.make_name("pod_id")
        error_msg = (
            f"VM Host {pod_id}: Password authentication failed: auth failed"
        )
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            with self.driver._get_client(pod_id, self.make_context()):
                self.fail("should not get here")

    def test_get_machine(self):
        fake_machine = self.fake_lxd.virtual_machines.get.return_value
        with self.driver._get_machine(None, self.make_context()) as machine:
            self.assertIs(machine, fake_machine)

    def test_get_machine_not_found(self):
        context = self.make_context()
        self.fake_lxd.virtual_machines.get.side_effect = NotFound("not found")
        instance_name = context.get("instance_name")
        pod_id = factory.make_name("pod_id")
        error_msg = f"Pod {pod_id}: LXD VM {instance_name} not found."
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            with self.driver._get_machine(pod_id, context):
                self.fail("should not get here")

    @inlineCallbacks
    def test_power_on(self):
        pod_id = factory.make_name("pod_id")
        machine = self.fake_lxd.virtual_machines.get.return_value
        machine.status_code = 110
        mock_log = self.patch(lxd_module, "maaslog")
        yield self.driver.power_on(pod_id, self.make_context())
        machine.start.assert_called_once_with()
        mock_log.debug.assert_called_once_with(f"power_on: {pod_id} is off")

    @inlineCallbacks
    def test_power_on_noop_if_on(self):
        pod_id = factory.make_name("pod_id")
        machine = self.fake_lxd.virtual_machines.get.return_value
        machine.status_code = 103
        mock_log = self.patch(lxd_module, "maaslog")
        yield self.driver.power_on(pod_id, self.make_context())
        machine.start.assert_not_called()
        mock_log.debug.assert_called_once_with(f"power_on: {pod_id} is on")

    @inlineCallbacks
    def test_power_off(self):
        pod_id = factory.make_name("pod_id")
        machine = self.fake_lxd.virtual_machines.get.return_value
        machine.status_code = 103
        mock_log = self.patch(lxd_module, "maaslog")
        yield self.driver.power_off(pod_id, self.make_context())
        machine.stop.assert_called_once_with()
        mock_log.debug.assert_called_once_with(f"power_off: {pod_id} is on")

    @inlineCallbacks
    def test_power_off_noop_if_off(self):
        pod_id = factory.make_name("pod_id")
        machine = self.fake_lxd.virtual_machines.get.return_value
        machine.status_code = 110
        mock_log = self.patch(lxd_module, "maaslog")
        yield self.driver.power_off(pod_id, self.make_context())
        machine.stop.assert_not_called()
        mock_log.debug.assert_called_once_with(f"power_off: {pod_id} is off")

    @inlineCallbacks
    def test_power_query(self):
        machine = self.fake_lxd.virtual_machines.get.return_value
        machine.status_code = 103
        state = yield self.driver.power_query(None, self.make_context())
        self.assertEqual(state, "on")

    @inlineCallbacks
    def test_power_query_raises_error_on_unknown_state(self):
        machine = self.fake_lxd.virtual_machines.get.return_value
        machine.status_code = 106
        pod_id = factory.make_name("pod_id")
        error_msg = f"Pod {pod_id}: Unknown power status code: 106"
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            yield self.driver.power_query(pod_id, self.make_context())

    @inlineCallbacks
    def test_discover_checks_required_extensions(self):
        self.fake_lxd.host_info["api_extensions"].remove("projects")
        error_msg = (
            "Please upgrade your LXD host to 4.16 or higher "
            "to support the following extensions: projects"
        )
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            yield self.driver.discover(None, self.make_context())

    @inlineCallbacks
    def test_discover(self):
        mac_address = factory.make_mac_address()
        lxd_net1 = Mock(type="physical")
        lxd_net1.state.return_value = FakeNetworkState(mac_address)
        # virtual interfaces are excluded
        lxd_net2 = Mock(type="bridge")
        lxd_net2.state.return_value = FakeNetworkState(
            factory.make_mac_address()
        )
        self.fake_lxd.networks.all.return_value = [lxd_net1, lxd_net2]
        discovered_pod = yield self.driver.discover(None, self.make_context())
        self.assertEqual(["amd64/generic"], discovered_pod.architectures)
        self.assertEqual("lxd-server", discovered_pod.name)
        self.assertEqual(discovered_pod.version, "4.1")
        self.assertEqual([mac_address], discovered_pod.mac_addresses)
        self.assertEqual(-1, discovered_pod.cores)
        self.assertEqual(-1, discovered_pod.cpu_speed)
        self.assertEqual(-1, discovered_pod.memory)
        self.assertEqual(0, discovered_pod.local_storage)
        self.assertEqual(-1, discovered_pod.hints.cores)
        self.assertEqual(-1, discovered_pod.hints.cpu_speed)
        self.assertEqual(-1, discovered_pod.hints.local_storage)
        self.assertEqual(
            [
                Capabilities.COMPOSABLE,
                Capabilities.DYNAMIC_LOCAL_STORAGE,
                Capabilities.OVER_COMMIT,
                Capabilities.STORAGE_POOLS,
            ],
            discovered_pod.capabilities,
        )
        self.assertEqual([], discovered_pod.machines)
        self.assertEqual([], discovered_pod.tags)
        self.assertEqual([], discovered_pod.storage_pools)

    @inlineCallbacks
    def test_discover_includes_unknown_type_interfaces(self):
        mac_address = factory.make_mac_address()
        network = Mock(type="unknown")
        network.state.return_value = FakeNetworkState(mac_address)
        self.fake_lxd.networks.all.return_value = [network]
        discovered_pod = yield self.driver.discover(None, self.make_context())
        self.assertEqual(discovered_pod.mac_addresses, [mac_address])

    @inlineCallbacks
    def test_discover_existing_project(self):
        context = self.make_context()
        project_name = context["project"]
        self.fake_lxd.projects.exists.return_value = True
        yield self.driver.discover(None, context)
        self.fake_lxd.projects.exists.assert_called_once_with(project_name)
        self.fake_lxd.projects.create.assert_not_called()

    @inlineCallbacks
    def test_discover_new_project(self):
        context = self.make_context()
        project_name = context["project"]
        self.fake_lxd.projects.exists.return_value = False
        yield self.driver.discover(None, context)
        self.fake_lxd.projects.exists.assert_called_once_with(project_name)
        self.fake_lxd.projects.create.assert_called_once_with(
            name=project_name,
            description="Project managed by MAAS",
        )

    @inlineCallbacks
    def test_discover_projects_checks_required_extensions(self):
        self.fake_lxd.host_info["api_extensions"].remove("virtual-machines")
        error_msg = (
            "Please upgrade your LXD host to 4.16 or higher "
            "to support the following extensions: virtual-machines"
        )
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            yield self.driver.discover_projects(None, self.make_context())

    @inlineCallbacks
    def test_discover_new_vmhost_untrusted_cert(self):
        context = self.make_context(with_password=False)
        self.fake_lxd.add_client_behavior(trusted=False)
        error_msg = "VM Host None: Certificate is not trusted and no password was given"
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            yield self.driver.discover(None, context)

    @inlineCallbacks
    def test_discover_existing_vmhost_untrusted_cert(self):
        context = self.make_context(with_password=False)
        self.fake_lxd.add_client_behavior(trusted=False)
        pod_id = factory.make_name("pod_id")
        error_msg = f"VM Host {pod_id}: Certificate is not trusted and no password was given"
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            yield self.driver.discover(pod_id, context)

    @inlineCallbacks
    def test_discover_projects(self):
        proj1 = Mock()
        proj1.name = "proj1"
        proj1.description = "Project 1"
        proj2 = Mock()
        proj2.name = "proj2"
        proj2.description = "Project 2"
        self.fake_lxd.projects.all.return_value = [proj1, proj2]
        projects = yield self.driver.discover_projects(
            None, self.make_context()
        )
        self.assertEqual(
            projects,
            [
                {"name": "proj1", "description": "Project 1"},
                {"name": "proj2", "description": "Project 2"},
            ],
        )

    def test_get_discovered_storage_pool(self):
        mock_storage_pool = Mock()
        mock_storage_pool.name = factory.make_name("pool")
        mock_storage_pool.driver = "dir"
        mock_storage_pool.config = {
            "source": "/home/chb/mnt/l2/disks/default.img",
            "volume.size": "0",
            "zfs.pool_name": "default",
        }
        mock_resources = Mock()
        mock_resources.space = {"used": 207111192576, "total": 306027577344}
        mock_storage_pool.resources.get.return_value = mock_resources
        discovered_pod_storage_pool = self.driver._get_discovered_storage_pool(
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

    def test_get_discovered_storage_pool_no_source(self):
        mock_storage_pool = Mock()
        mock_storage_pool.name = factory.make_name("pool")
        mock_storage_pool.driver = "dir"
        mock_storage_pool.config = {
            "volume.size": "0",
            "zfs.pool_name": "default",
        }
        mock_resources = Mock()
        mock_resources.space = {"used": 207111192576, "total": 306027577344}
        mock_storage_pool.resources.get.return_value = mock_resources
        discovered_pod_storage_pool = self.driver._get_discovered_storage_pool(
            mock_storage_pool
        )
        self.assertEqual(discovered_pod_storage_pool.path, "Unknown")

    def test_get_discovered_storage_pool_no_config(self):
        mock_storage_pool = Mock()
        mock_storage_pool.name = factory.make_name("pool")
        mock_storage_pool.driver = "dir"
        mock_storage_pool.config = None
        mock_resources = Mock()
        mock_resources.space = {"used": 207111192576, "total": 306027577344}
        mock_storage_pool.resources.get.return_value = mock_resources
        discovered_pod_storage_pool = self.driver._get_discovered_storage_pool(
            mock_storage_pool
        )
        self.assertEqual(discovered_pod_storage_pool.path, "Unknown")

    def test_get_discovered_machine(self):
        mock_machine = Mock()
        mock_machine.name = factory.make_name("machine")
        mock_machine.architecture = "x86_64"
        mock_machine.location = "FakeLXD"
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
        self.fake_lxd.networks.get.return_value = mock_network
        client = self.fake_lxd.make_client()
        discovered_machine = self.driver._get_discovered_machine(
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
                size=20 * 1000**3,
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
        self.assertEqual([], discovered_machine.tags)
        self.assertFalse(discovered_machine.hugepages_backed)
        self.assertEqual(discovered_machine.pinned_cores, [])

    def test_get_discovered_machine_project(self):
        project = factory.make_string()
        client = self.fake_lxd.make_client(project=project)
        mock_machine = Mock()
        mock_machine.name = factory.make_name("machine")
        mock_machine.architecture = "x86_64"
        mock_machine.expanded_config = {
            "limits.cpu": "2",
            "limits.memory": "1024MiB",
            "volatile.eth0.hwaddr": "00:16:3e:78:be:04",
        }
        mock_machine.location = "FakeLXD"
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
        self.fake_lxd.networks.get.return_value = mock_network
        discovered_machine = self.driver._get_discovered_machine(
            client, mock_machine, [mock_storage_pool]
        )
        self.assertEqual(
            discovered_machine.power_parameters["project"], project
        )

    def test_get_discovered_machine_vm_info(self):
        mock_machine = Mock()
        mock_machine.name = factory.make_name("machine")
        mock_machine.architecture = "x86_64"
        mock_machine.location = "FakeLXD"
        expanded_config = {
            "limits.cpu": "0-2",
            "limits.memory.hugepages": "true",
        }
        mock_machine.expanded_config = expanded_config
        mock_machine.expanded_devices = {}
        client = self.fake_lxd.make_client()
        discovered_machine = self.driver._get_discovered_machine(
            client, mock_machine, []
        )
        self.assertTrue(discovered_machine.hugepages_backed)
        self.assertEqual(discovered_machine.pinned_cores, [0, 1, 2])

    def test_get_discovered_machine_with_non_pool_backed_disk(self):
        mock_machine = Mock()
        mock_machine.name = factory.make_name("machine")
        mock_machine.architecture = "x86_64"
        mock_machine.location = "FakeLXD"
        mock_machine.expanded_config = {}
        mock_machine.expanded_devices = {
            "iso": {
                "source": "/ubuntu.iso",
                "type": "disk",
            }
        }
        client = self.fake_lxd.make_client()
        discovered_machine = self.driver._get_discovered_machine(
            client, mock_machine, []
        )
        [discovered_device] = discovered_machine.block_devices
        self.assertEqual(discovered_device.serial, "lxd_iso")
        self.assertIsNone(discovered_device.storage_pool)

    def test_get_discovered_machine_with_request(self):
        request = make_requested_machine(num_disks=2)
        driver = lxd_module.LXDPodDriver()
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
        self.fake_lxd.profiles.get.return_value = mock_profile
        mock_storage_pools = Mock()
        self.fake_lxd.storage_pools.all.return_value = mock_storage_pools
        mock_get_usable_storage_pool = self.patch(
            self.driver, "_get_usable_storage_pool"
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
        self.fake_lxd.storage_pools.get.return_value = usable_pool
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
        mock_machine.location = "FakeLXD"
        self.fake_lxd.virtual_machines.create.return_value = mock_machine
        discovered_machine = driver._get_discovered_machine(
            self.fake_lxd.make_client(), mock_machine, [usable_pool], request
        )
        # invert sort as the root device shows up last because of name ordering
        discovered_devices = sorted(
            discovered_machine.block_devices, reverse=True
        )
        for idx, device in enumerate(discovered_devices):
            self.assertEqual(device.size, request.block_devices[idx].size)
            self.assertEqual(device.tags, request.block_devices[idx].tags)

    def test_get_hugepages_info_int_value_as_bool(self):
        mock_machine = Mock()
        mock_machine.name = factory.make_name("machine")
        mock_machine.architecture = "x86_64"
        mock_machine.location = "FakeLXD"
        expanded_config = {
            "limits.memory.hugepages": "1",
        }
        mock_machine.expanded_config = expanded_config
        mock_machine.expanded_devices = {}
        discovered_machine = self.driver._get_discovered_machine(
            self.fake_lxd.make_client(), mock_machine, []
        )
        self.assertTrue(discovered_machine.hugepages_backed)

    def test_get_discovered_machine_sets_power_state_to_unknown_for_unknown(
        self,
    ):
        mock_machine = Mock()
        mock_machine.name = factory.make_name("machine")
        mock_machine.architecture = "x86_64"
        mock_machine.location = "FakeLXD"
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
        discovered_machine = self.driver._get_discovered_machine(
            self.fake_lxd.make_client(), mock_machine, [mock_storage_pool]
        )
        self.assertEqual("unknown", discovered_machine.power_state)

    @inlineCallbacks
    def test_get_commissioning_data(self):
        def mock_iface(name, mac):
            iface = Mock()
            iface.state.return_value = FakeNetworkState(mac)
            iface.configure_mock(name=name)
            return iface

        self.fake_lxd.networks.all.return_value = [
            mock_iface("eth0", "aa:bb:cc:dd:ee:ff"),
            mock_iface("eth1", "ff:ee:dd:cc:bb:aa"),
        ]
        commissioning_data = yield self.driver.get_commissioning_data(
            1, self.make_context()
        )

        details = {
            **self.fake_lxd.host_info,
            "resources": self.fake_lxd.resources,
            "networks": {
                "eth0": {"hwaddr": "aa:bb:cc:dd:ee:ff"},
                "eth1": {"hwaddr": "ff:ee:dd:cc:bb:aa"},
            },
        }
        self.assertEqual(
            commissioning_data,
            {
                RUN_MACHINE_RESOURCES: details,
                COMMISSIONING_OUTPUT_NAME: details,
            },
        )

    @inlineCallbacks
    def test_get_commissioning_data_not_found(self):
        def mock_iface(name, mac, error=None):
            def state():
                if error is not None:
                    raise error
                return FakeNetworkState(mac)

            iface = Mock()
            iface.state.side_effect = state
            iface.configure_mock(name=name)
            return iface

        self.fake_lxd.networks.all.return_value = [
            mock_iface(
                "eth0",
                "aa:bb:cc:dd:ee:ff",
                error=NotFound("Not found"),
            ),
            mock_iface(
                "eth1",
                "ff:ee:dd:cc:bb:aa",
                error=LXDAPIException(
                    FakeErrorResponse('Network interface "eth1" not found')
                ),
            ),
            mock_iface("eth2", "ee:dd:cc:bb:aa:ff"),
        ]
        commissioning_data = yield self.driver.get_commissioning_data(
            1, self.make_context()
        )

        details = {
            **self.fake_lxd.host_info,
            "resources": self.fake_lxd.resources,
            "networks": {
                "eth2": {"hwaddr": "ee:dd:cc:bb:aa:ff"},
            },
        }
        self.assertEqual(
            commissioning_data,
            {
                RUN_MACHINE_RESOURCES: details,
                COMMISSIONING_OUTPUT_NAME: details,
            },
        )

    @inlineCallbacks
    def test_get_commissioning_data_api_error(self):
        def mock_iface(name, mac, error=None):
            def state():
                if error is not None:
                    raise error
                return FakeNetworkState(mac)

            iface = Mock()
            iface.state.side_effect = state
            iface.configure_mock(name=name)
            return iface

        self.fake_lxd.networks.all.return_value = [
            mock_iface(
                "eth1",
                "aa:bb:cc:dd:ee:ff",
                error=LXDAPIException(FakeErrorResponse("Some error")),
            ),
            mock_iface("eth1", "ff:ee:dd:cc:bb:aa"),
        ]
        try:
            yield self.driver.get_commissioning_data(1, self.make_context())
        except LXDAPIException as error:
            self.assertEqual("Some error", str(error))
        else:
            raise AssertionError("LXDAPIException wasn't raised.")

    def test_get_usable_storage_pool(self):
        pools = [
            Mock(
                **{
                    "resources.get.return_value": Mock(
                        space={"total": 2**i * 2048, "used": 2 * i * 1500}
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
            pools[0], self.driver._get_usable_storage_pool(disk, pools)
        )

    def test_get_usable_storage_pool_filters_on_disk_tags(self):
        pools = [
            Mock(
                **{
                    "resources.get.return_value": Mock(
                        space={"total": 2**i * 2048, "used": 2 * i * 1500}
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
            pools[1], self.driver._get_usable_storage_pool(disk, pools)
        )

    def test_get_usable_storage_pool_filters_on_disk_tags_raises_invalid(self):
        pools = [
            Mock(
                **{
                    "resources.get.return_value": Mock(
                        space={"total": 2**i * 2048, "used": 2 * i * 1500}
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
            PodInvalidResources,
            self.driver._get_usable_storage_pool,
            disk,
            pools,
        )

    def test_get_usable_storage_pool_filters_on_default_pool_name(self):
        pools = [
            Mock(
                **{
                    "resources.get.return_value": Mock(
                        space={"total": 2**i * 2048, "used": 2 * i * 1500}
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
            self.driver._get_usable_storage_pool(disk, pools, pools[0].name),
        )

    def test_get_usable_storage_pool_filters_on_default_pool_name_raises_invalid(
        self,
    ):
        pools = [
            Mock(
                **{
                    "resources.get.return_value": Mock(
                        space={"total": 2**i * 2048, "used": 2 * i * 1500}
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
            self.driver._get_usable_storage_pool,
            disk,
            pools,
            pools[0].name,
        )

    @inlineCallbacks
    def test_compose_no_interface_constraints(self):
        pod_id = factory.make_name("pod_id")
        context = self.make_context()
        request = make_requested_machine()
        self.fake_lxd.profiles.exists.return_value = False
        mock_storage_pools = Mock()
        self.fake_lxd.storage_pools.all.return_value = mock_storage_pools
        mock_get_usable_storage_pool = self.patch(
            self.driver, "_get_usable_storage_pool"
        )
        usable_pool = Mock()
        usable_pool.name = factory.make_name("pool")
        mock_get_usable_storage_pool.return_value = usable_pool
        mock_machine = Mock()
        self.fake_lxd.virtual_machines.create.return_value = mock_machine
        mock_get_discovered_machine = self.patch(
            self.driver, "_get_discovered_machine"
        )
        mock_get_discovered_machine.return_value = sentinel.discovered_machine
        definition = {
            "name": request.hostname,
            "architecture": debian_to_kernel_architecture(
                request.architecture
            ),
            "config": {
                "limits.cpu": str(request.cores),
                "limits.memory": str(request.memory * 1024**2),
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

        discovered_machine, _ = yield self.driver.compose(
            pod_id, context, request
        )
        self.fake_lxd.virtual_machines.create.assert_called_once_with(
            definition, wait=True
        )

    @inlineCallbacks
    def test_compose_no_host_known_interfaces(self):
        request = make_requested_machine(known_host_interfaces=[])
        self.fake_lxd.profiles.exists.return_value = False
        mock_storage_pools = Mock()
        self.fake_lxd.storage_pools.all.return_value = mock_storage_pools
        mock_get_usable_storage_pool = self.patch(
            self.driver, "_get_usable_storage_pool"
        )
        usable_pool = Mock()
        usable_pool.name = factory.make_name("pool")
        mock_get_usable_storage_pool.return_value = usable_pool
        with ExpectedException(
            lxd_module.LXDPodError,
            "No host network to attach VM interfaces to",
        ):
            yield self.driver.compose(None, self.make_context(), request)

    @inlineCallbacks
    def test_compose_no_host_known_interfaces_with_dhcp(self):
        request = make_requested_machine()
        for host_interface in request.known_host_interfaces:
            host_interface.dhcp_enabled = False
        self.fake_lxd.profiles.exists.return_value = False
        mock_storage_pools = Mock()
        self.fake_lxd.storage_pools.all.return_value = mock_storage_pools
        mock_get_usable_storage_pool = self.patch(
            self.driver, "_get_usable_storage_pool"
        )
        usable_pool = Mock()
        usable_pool.name = factory.make_name("pool")
        mock_get_usable_storage_pool.return_value = usable_pool
        with ExpectedException(
            lxd_module.LXDPodError,
            "No host network to attach VM interfaces to",
        ):
            yield self.driver.compose(None, self.make_context(), request)

    @inlineCallbacks
    def test_compose_checks_required_extensions(self):
        self.fake_lxd.host_info["api_extensions"].remove("projects")
        error_msg = (
            "Please upgrade your LXD host to 4.16 or higher "
            "to support the following extensions: projects"
        )
        with ExpectedException(lxd_module.LXDPodError, error_msg):
            yield self.driver.compose(
                None, self.make_context(), make_requested_machine()
            )

    @inlineCallbacks
    def test_compose_multiple_disks(self):
        pod_id = factory.make_name("pod_id")
        request = make_requested_machine(num_disks=2)
        self.fake_lxd.profiles.exists.return_value = False

        mock_get_usable_storage_pool = self.patch(
            self.driver, "_get_usable_storage_pool"
        )
        # a volume is created for the second disk
        volume = Mock()
        volume.config = {
            "size": str(request.block_devices[1].size),
        }
        volume.name = factory.make_name("vol")
        usable_pool = Mock()
        usable_pool.name = factory.make_name("pool")
        usable_pool.volumes.create.return_value = volume
        usable_pool.volumes.get.return_value = volume
        mock_get_usable_storage_pool.return_value = usable_pool
        self.fake_lxd.storage_pools.get.return_value = usable_pool

        # LXD sorts the devices in a way the root dist is always last
        expanded_devices = {
            "disk1": {
                "path": "",
                "pool": usable_pool.name,
                "source": volume.name,
                "type": "disk",
            },
            "eth0": {
                "boot.priority": "1",
                "name": "eth0",
                "nictype": "bridged",
                "parent": "maas-kvm",
                "type": "nic",
            },
            "root": {
                "path": "/",
                "pool": usable_pool.name,
                "size": str(request.block_devices[0].size),
                "type": "disk",
                "boot.priority": 0,
            },
        }
        mock_machine = Mock(
            name=factory.make_name(),
            architecture=debian_to_kernel_architecture(request.architecture),
            expanded_devices=expanded_devices,
            expanded_config={},
            location="FakeLXD",
            status_code=101,
        )
        self.fake_lxd.virtual_machines.create.return_value = mock_machine

        definition = {
            "name": request.hostname,
            "architecture": debian_to_kernel_architecture(
                request.architecture
            ),
            "config": {
                "limits.cpu": str(request.cores),
                "limits.memory": str(request.memory * 1024**2),
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

        discovered_machine, _ = yield self.driver.compose(
            pod_id, self.make_context(), request
        )
        self.fake_lxd.virtual_machines.create.assert_called_once_with(
            definition, wait=True
        )

        # assert the device order was preserved
        self.assertEqual(
            request.block_devices[0].size,
            discovered_machine.block_devices[0].size,
        )
        self.assertEqual(
            request.block_devices[1].size,
            discovered_machine.block_devices[1].size,
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
        # the nictype as this is what we expect from LXDPodSelf.Driver.compose.
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
        self.fake_lxd.profiles.exists.return_value = False
        mock_storage_pools = Mock()
        self.fake_lxd.storage_pools.all.return_value = mock_storage_pools
        mock_get_usable_storage_pool = self.patch(
            self.driver, "_get_usable_storage_pool"
        )
        usable_pool = Mock()
        usable_pool.name = factory.make_name("pool")
        mock_get_usable_storage_pool.return_value = usable_pool
        mock_machine = Mock()
        self.fake_lxd.virtual_machines.create.return_value = mock_machine
        mock_get_discovered_machine = self.patch(
            self.driver, "_get_discovered_machine"
        )
        mock_get_discovered_machine.return_value = sentinel.discovered_machine
        definition = {
            "name": request.hostname,
            "architecture": debian_to_kernel_architecture(
                request.architecture
            ),
            "config": {
                "limits.cpu": str(request.cores),
                "limits.memory": str(request.memory * 1024**2),
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

        discovered_machine, _ = yield self.driver.compose(
            None, self.make_context(), request
        )
        self.fake_lxd.virtual_machines.create.assert_called_once_with(
            definition, wait=True
        )
        self.assertEqual(sentinel.discovered_machine, discovered_machine)

    @inlineCallbacks
    def test_compose_with_maas_profile(self):
        request = make_requested_machine()
        self.fake_lxd.profiles.exists.return_value = True
        mock_storage_pools = Mock()
        self.fake_lxd.storage_pools.all.return_value = mock_storage_pools
        mock_get_usable_storage_pool = self.patch(
            self.driver, "_get_usable_storage_pool"
        )
        usable_pool = Mock()
        usable_pool.name = factory.make_name("pool")
        mock_get_usable_storage_pool.return_value = usable_pool
        mock_machine = Mock()
        self.fake_lxd.virtual_machines.create.return_value = mock_machine
        mock_get_discovered_machine = self.patch(
            self.driver, "_get_discovered_machine"
        )
        mock_get_discovered_machine.return_value = sentinel.discovered_machine
        definition = {
            "name": request.hostname,
            "architecture": debian_to_kernel_architecture(
                request.architecture
            ),
            "config": {
                "limits.cpu": str(request.cores),
                "limits.memory": str(request.memory * 1024**2),
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

        discovered_machine, empty_hints = yield self.driver.compose(
            None, self.make_context(), request
        )
        self.fake_lxd.virtual_machines.create.assert_called_once_with(
            definition, wait=True
        )
        self.fake_lxd.profiles.exists.assert_called_once_with("maas")

    @inlineCallbacks
    def test_decompose(self):
        devices = {
            "root": {
                "path": "/",
                "type": "disk",
                "pool": "default",
            },
        }
        mock_machine = Mock(devices=devices)
        self.fake_lxd.virtual_machines.get.return_value = mock_machine
        empty_hints = yield self.driver.decompose(None, self.make_context())

        mock_machine.stop.assert_called_once_with(force=True, wait=True)
        mock_machine.delete.assert_called_once_with(wait=True)
        self.assertIsInstance(empty_hints, DiscoveredPodHints)
        self.assertEqual(empty_hints.cores, -1)
        self.assertEqual(empty_hints.cpu_speed, -1)
        self.assertEqual(empty_hints.memory, -1)
        self.assertEqual(empty_hints.local_storage, -1)

    @inlineCallbacks
    def test_decompose_extra_volumes_warn_if_delete_fails(self):
        pod_id = factory.make_name("pod_id")
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
        mock_machine = Mock(
            devices=devices, client=self.fake_lxd.make_client()
        )
        self.fake_lxd.virtual_machines.get.return_value = mock_machine
        pool = Mock()
        self.fake_lxd.storage_pools.get.return_value = pool
        pool.volumes.get.return_value = None  # volume not found
        mock_log = self.patch(lxd_module, "maaslog")
        yield self.driver.decompose(pod_id, self.make_context())
        mock_log.warning.assert_called_with(
            f"Pod {pod_id}: failed to delete volume vol in pool default"
        )

    @inlineCallbacks
    def test_decompose_removes_extra_volumes(self):
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
        mock_machine = Mock(
            devices=devices, client=self.fake_lxd.make_client()
        )
        self.fake_lxd.virtual_machines.get.return_value = mock_machine
        pool = self.fake_lxd.storage_pools.get.return_value
        volume = pool.volumes.get.return_value
        yield self.driver.decompose(None, self.make_context())
        pool.volumes.get.assert_called_once_with("custom", "vol")
        volume.delete.assert_called_once()

    @inlineCallbacks
    def test_decompose_on_stopped_instance(self):
        pod_id = factory.make_name("pod_id")
        context = self.make_context()
        devices = {
            "root": {
                "path": "/",
                "type": "disk",
                "pool": "default",
            },
        }
        mock_machine = Mock(devices=devices)
        # Simulate the case where the VM is already stopped
        mock_machine.status_code = 102
        self.fake_lxd.virtual_machines.get.return_value = mock_machine
        yield self.driver.decompose(pod_id, context)

        mock_machine.stop.assert_not_called()
        mock_machine.delete.assert_called_once_with(wait=True)

    @inlineCallbacks
    def test_decompose_missing_vm(self):
        pod_id = factory.make_name("pod_id")
        context = self.make_context()
        mock_log = self.patch(lxd_module, "maaslog")
        self.fake_lxd.virtual_machines.get.return_value = None
        yield self.driver.decompose(pod_id, context)
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
