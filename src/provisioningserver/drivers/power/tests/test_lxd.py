# Copyright 2020-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import dataclasses
from functools import lru_cache
from os import environ, path
from pathlib import Path
import tempfile
from typing import Optional, Tuple
from unittest.mock import MagicMock, Mock

from fixtures import EnvironmentVariable, TempDir
from pylxd.exceptions import ClientConnectionFailed, LXDAPIException, NotFound
from requests import Session
from twisted.internet.defer import inlineCallbacks

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
import provisioningserver.drivers.power as power_module
from provisioningserver.drivers.power import lxd as lxd_module
from provisioningserver.drivers.power import PowerError
from provisioningserver.testing.certificates import (
    get_sample_cert,
    SampleCertificateFixture,
)

twisted_test_factory = MAASTwistedRunTest.make_factory(
    timeout=environ.get("MAAS_WAIT_FOR_REACTOR", 60.0)
)


class FakeErrorResponse:
    def __init__(self, error, status_code=500):
        self.status_code = status_code
        self._error = error

    def json(self):
        return {"error": self._error}


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

    def __init__(self, name="lxd-server"):
        # global details
        self.host_info = {
            "api_extensions": [],
            "environment": {
                "architectures": ["x86_64", "i686"],
                "kernel_architecture": "x86_64",
                "server_name": name,
                "server_version": "4.1",
                "server_clustered": False,
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
                raise Exception("Requested more clients than expected")  # noqa: B904
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


def _make_maas_certs(test_case):
    tempdir = Path(test_case.useFixture(TempDir()).path)
    test_case.useFixture(EnvironmentVariable("SNAP_COMMON", str(tempdir)))
    test_case.certs_dir = tempdir / "certificates"
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


class TestLXDPowerDriver(MAASTestCase):
    run_tests_with = twisted_test_factory

    def setUp(self):
        super().setUp()
        self.fake_lxd = FakeLXD()
        self.driver = lxd_module.LXDPowerDriver()
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

    def test_chassis_for_bmc_deduplication(self):
        # VMs on the same host share a single BMC (the hypervisor), so the
        # driver must be a chassis for BMC deduplication to work.
        self.assertTrue(self.driver.chassis)
        self.assertTrue(self.driver.can_probe)

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
        system_id = factory.make_name("system_id")
        error_msg = f"{system_id}: No certificates available"
        with self.assertRaisesRegex(lxd_module.LXDPowerDriverError, error_msg):
            with self.driver._get_client(system_id, context):
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
        system_id = factory.make_name("system_id")
        error_msg = f"{system_id}: Invalid PEM material"
        with self.assertRaisesRegex(lxd_module.LXDPowerDriverError, error_msg):
            with self.driver._get_client(system_id, context):
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
        system_id = factory.make_name("system_id")
        error_msg = (
            f"{system_id}: Certificate is not trusted and no password "
            "was given"
        )
        with self.assertRaisesRegex(lxd_module.LXDPowerDriverError, error_msg):
            with self.driver._get_client(system_id, context) as client:
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
        system_id = factory.make_name("system_id")
        error_msg = (
            f"{system_id}: Certificate is not trusted and no password "
            "was given"
        )
        with self.assertRaisesRegex(lxd_module.LXDPowerDriverError, error_msg):
            with self.driver._get_client(system_id, context):
                self.fail("should not get here")

    def test_get_client_raises_error_when_cannot_connect(self):
        self.fake_lxd.add_client_behavior(fail_connect=True)
        system_id = factory.make_name("system_id")
        error_msg = f"{system_id}: Failed to connect to the LXD REST API"
        with self.assertRaisesRegex(lxd_module.LXDPowerDriverError, error_msg):
            with self.driver._get_client(system_id, self.make_context()):
                self.fail("should not get here")

    def test_get_client_raises_error_when_authenticate_fails(self):
        self.fake_lxd.add_client_behavior(fail_auth=True)
        system_id = factory.make_name("system_id")
        error_msg = f"{system_id}: Password authentication failed: auth failed"
        with self.assertRaisesRegex(lxd_module.LXDPowerDriverError, error_msg):
            with self.driver._get_client(system_id, self.make_context()):
                self.fail("should not get here")

    def test_get_machine(self):
        fake_machine = self.fake_lxd.virtual_machines.get.return_value
        with self.driver._get_machine(None, self.make_context()) as machine:
            self.assertIs(machine, fake_machine)

    def test_get_machine_not_found(self):
        context = self.make_context()
        self.fake_lxd.virtual_machines.get.side_effect = NotFound("not found")
        instance_name = context.get("instance_name")
        system_id = factory.make_name("system_id")
        error_msg = f"{system_id}: LXD VM {instance_name} not found."
        with self.assertRaisesRegex(lxd_module.LXDPowerDriverError, error_msg):
            with self.driver._get_machine(system_id, context):
                self.fail("should not get here")

    @inlineCallbacks
    def test_power_on(self):
        system_id = factory.make_name("system_id")
        machine = self.fake_lxd.virtual_machines.get.return_value
        machine.status_code = 110
        mock_log = self.patch(lxd_module, "maaslog")
        yield self.driver.power_on(system_id, self.make_context())
        machine.start.assert_called_once_with()
        mock_log.debug.assert_called_once_with(f"power_on: {system_id} is off")

    @inlineCallbacks
    def test_power_on_noop_if_on(self):
        system_id = factory.make_name("system_id")
        machine = self.fake_lxd.virtual_machines.get.return_value
        machine.status_code = 103
        mock_log = self.patch(lxd_module, "maaslog")
        yield self.driver.power_on(system_id, self.make_context())
        machine.start.assert_not_called()
        mock_log.debug.assert_called_once_with(f"power_on: {system_id} is on")

    @inlineCallbacks
    def test_perform_power_timeouts(self):
        system_id = factory.make_name("system_id")
        machine = self.fake_lxd.virtual_machines.get_return_value
        machine.status_code = 110
        mock_pause = self.patch(power_module, "pause")
        mock_power_on = Mock()
        mock_deferToThread = self.patch(power_module, "deferToThread")
        mock_deferToThread.side_effect = PowerError
        errors = self.driver.perform_power(
            mock_power_on, "on", system_id, self.make_context()
        )
        try:
            yield errors
        except PowerError:
            pass
        except Exception:
            self.fail("perform_power did not raise PowerError")
        expected_pause_calls = [
            waiting_time for waiting_time in self.driver.wait_time
        ]
        actual_pause_calls = [
            call.args[0] for call in mock_pause.call_args_list
        ]
        self.assertEqual(expected_pause_calls, actual_pause_calls)
        self.assertEqual(
            actual_pause_calls[-1], lxd_module.LXD_WAITING_POLICY[-1]
        )

    @inlineCallbacks
    def test_power_off(self):
        system_id = factory.make_name("system_id")
        machine = self.fake_lxd.virtual_machines.get.return_value
        machine.status_code = 103
        mock_log = self.patch(lxd_module, "maaslog")
        yield self.driver.power_off(system_id, self.make_context())
        machine.stop.assert_called_once_with()
        mock_log.debug.assert_called_once_with(f"power_off: {system_id} is on")

    @inlineCallbacks
    def test_power_off_noop_if_off(self):
        system_id = factory.make_name("system_id")
        machine = self.fake_lxd.virtual_machines.get.return_value
        machine.status_code = 110
        mock_log = self.patch(lxd_module, "maaslog")
        yield self.driver.power_off(system_id, self.make_context())
        machine.stop.assert_not_called()
        mock_log.debug.assert_called_once_with(
            f"power_off: {system_id} is off"
        )

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
        system_id = factory.make_name("system_id")
        error_msg = f"{system_id}: Unknown power status code: 106"
        with self.assertRaisesRegex(lxd_module.LXDPowerDriverError, error_msg):
            yield self.driver.power_query(system_id, self.make_context())

    @inlineCallbacks
    def test_power_reset_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            yield self.driver.power_reset(
                factory.make_name("system_id"), self.make_context()
            )
