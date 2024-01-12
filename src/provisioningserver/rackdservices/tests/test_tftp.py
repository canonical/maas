# Copyright 2012-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the maastftp Twisted plugin."""


from functools import partial
import json
import os
import random
import re
from socket import AF_INET, AF_INET6
import time
from unittest.mock import Mock, sentinel

from netaddr import IPNetwork
from netaddr.ip import IPV4_LINK_LOCAL, IPV6_LINK_LOCAL
import prometheus_client
from tftp.backend import IReader
from tftp.datagram import RQDatagram
from tftp.errors import BackendError, FileNotFound
import tftp.protocol
from tftp.protocol import TFTP
from twisted.application import internet
from twisted.application.service import MultiService
from twisted.internet import reactor
from twisted.internet.address import IPv4Address, IPv6Address
from twisted.internet.defer import fail, inlineCallbacks, succeed
from twisted.internet.protocol import Protocol
from twisted.internet.task import Clock
from twisted.python import context
from zope.interface.verify import verifyObject

from maastesting import get_testing_timeout
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from maastesting.twisted import TwistedLoggerFixture
from provisioningserver import boot
from provisioningserver.boot import BytesReader
from provisioningserver.boot.pxe import PXEBootMethod
from provisioningserver.boot.tests.test_pxe import compose_config_path
from provisioningserver.events import EVENT_TYPES
from provisioningserver.prometheus.metrics import METRICS_DEFINITIONS
from provisioningserver.prometheus.utils import create_metrics
from provisioningserver.rackdservices import tftp as tftp_module
from provisioningserver.rackdservices.tftp import (
    log_request,
    Port,
    TFTPBackend,
    TFTPService,
    track_tftp_latency,
    TransferTimeTrackingTFTP,
    UDPServer,
)
from provisioningserver.rpc.exceptions import BootConfigNoResponse
from provisioningserver.rpc.region import GetBootConfig
from provisioningserver.testing.config import ClusterConfigurationFixture
from provisioningserver.tests.test_kernel_opts import make_kernel_parameters

TIMEOUT = get_testing_timeout()


class TestBytesReader(MAASTestCase):
    """Tests for `BytesReader`."""

    def test_interfaces(self):
        reader = BytesReader(b"")
        self.addCleanup(reader.finish)
        verifyObject(IReader, reader)

    def test_read(self):
        data = factory.make_string(size=10).encode("ascii")
        reader = BytesReader(data)
        self.addCleanup(reader.finish)
        self.assertEqual(data[:7], reader.read(7))
        self.assertEqual(data[7:], reader.read(7))
        self.assertEqual(b"", reader.read(7))

    def test_finish(self):
        reader = BytesReader(b"1234")
        reader.finish()
        self.assertRaises(ValueError, reader.read, 1)


class TestTFTPBackend(MAASTestCase):
    """Tests for `TFTPBackend`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def setUp(self):
        super().setUp()
        self.useFixture(ClusterConfigurationFixture())
        self.patch(boot, "find_mac_via_arp")
        self.patch(tftp_module, "log_request")

    def test_init(self):
        temp_dir = self.make_dir()
        client_service = Mock()
        backend = TFTPBackend(temp_dir, client_service)
        self.assertEqual((True, False), (backend.can_read, backend.can_write))
        self.assertEqual(temp_dir, backend.base.path)
        self.assertEqual(client_service, backend.client_service)

    def get_reader(self, data):
        temp_file = self.make_file(name="example", contents=data)
        temp_dir = os.path.dirname(temp_file)
        backend = TFTPBackend(temp_dir, Mock())
        return backend.get_reader(b"example")

    @inlineCallbacks
    def test_get_reader_regular_file(self):
        # TFTPBackend.get_reader() returns a regular FilesystemReader for
        # paths not matching re_config_file.
        data = factory.make_string().encode("ascii")
        reader = yield self.get_reader(data)
        self.addCleanup(reader.finish)
        self.assertEqual(len(data), reader.size)
        self.assertEqual(data, reader.read(len(data)))
        self.assertEqual(b"", reader.read(1))

    @inlineCallbacks
    def test_get_reader_handles_backslashes_in_path(self):
        data = factory.make_string().encode("ascii")
        temp_dir = self.make_dir()
        subdir = factory.make_name("subdir")
        filename = factory.make_name("file")
        os.mkdir(os.path.join(temp_dir, subdir))
        factory.make_file(os.path.join(temp_dir, subdir), filename, data)

        path = (f"\\{subdir}\\{filename}").encode("ascii")
        backend = TFTPBackend(temp_dir, "http://nowhere.example.com/")
        reader = yield backend.get_reader(path)

        self.addCleanup(reader.finish)
        self.assertEqual(len(data), reader.size)
        self.assertEqual(data, reader.read(len(data)))
        self.assertEqual(b"", reader.read(1))

    @inlineCallbacks
    def test_get_reader_logs_node_event(self):
        data = factory.make_string().encode("ascii")
        reader = yield self.get_reader(data)
        self.addCleanup(reader.finish)
        tftp_module.log_request.assert_called_once_with(b"example")

    @inlineCallbacks
    def test_get_reader_converts_BootConfigNoResponse_to_FileNotFound(self):
        client = Mock()
        client.localIdent = factory.make_name("system_id")
        client.return_value = fail(BootConfigNoResponse())
        client_service = Mock()
        client_service.getClientNow.return_value = succeed(client)
        backend = TFTPBackend(self.make_dir(), client_service)

        with self.assertRaisesRegex(FileNotFound, r"pxelinux\.cfg/default"):
            yield backend.get_reader(b"pxelinux.cfg/default")

    @inlineCallbacks
    def test_get_reader_converts_other_exceptions_to_tftp_error(self):
        exception_type = factory.make_exception_type()
        exception_message = factory.make_string()
        client = Mock()
        client.localIdent = factory.make_name("system_id")
        client.return_value = fail(exception_type(exception_message))
        client_service = Mock()
        client_service.getClientNow.return_value = succeed(client)
        backend = TFTPBackend(self.make_dir(), client_service)

        with TwistedLoggerFixture() as logger:
            with self.assertRaisesRegex(
                BackendError, re.escape(exception_message)
            ):
                yield backend.get_reader(b"pxelinux.cfg/default")

        # The original exception is logged.
        self.assertIn("TFTP back-end failed.", logger.messages)

    @inlineCallbacks
    def _test_get_render_file(self, local, remote):
        # For paths matching PXEBootMethod.match_path, TFTPBackend.get_reader()
        # returns a Deferred that will yield a BytesReader.
        mac = factory.make_mac_address("-")
        config_path = compose_config_path(mac)
        backend = TFTPBackend(self.make_dir(), Mock())
        # python-tx-tftp sets up call context so that backends can discover
        # more about the environment in which they're running.
        call_context = {"local": local, "remote": remote}

        @partial(self.patch, backend, "get_boot_method_reader")
        def get_boot_method_reader(boot_method, params):
            params_json = json.dumps(params).encode("ascii")
            params_json_reader = BytesReader(params_json)
            return succeed(params_json_reader)

        reader = yield context.call(
            call_context, backend.get_reader, config_path
        )
        output = reader.read(10000).decode("ascii")
        # The addresses provided by python-tx-tftp in the call context are
        # passed over the wire as address:port strings.
        expected_params = {
            "mac": mac,
            "local_ip": call_context["local"][0],  # address only.
            "remote_ip": call_context["remote"][0],  # address only.
            "bios_boot_method": "pxe",
            "protocol": "tftp",
        }
        observed_params = json.loads(output)
        self.assertEqual(expected_params, observed_params)

    def test_get_render_file_with_ipv4_hosts(self):
        return self._test_get_render_file(
            local=(factory.make_ipv4_address(), factory.pick_port()),
            remote=(factory.make_ipv4_address(), factory.pick_port()),
        )

    def test_get_render_file_with_ipv6_hosts(self):
        # Some versions of Twisted have the scope and flow info in the remote
        # address tuple. See https://twistedmatrix.com/trac/ticket/6826 (the
        # address is captured by tftp.protocol.TFTP.dataReceived).
        return self._test_get_render_file(
            local=(
                factory.make_ipv6_address(),
                factory.pick_port(),
                random.randint(1, 1000),
                random.randint(1, 1000),
            ),
            remote=(
                factory.make_ipv6_address(),
                factory.pick_port(),
                random.randint(1, 1000),
                random.randint(1, 1000),
            ),
        )

    @inlineCallbacks
    def test_get_boot_method_reader_uses_same_client(self):
        # Fake kernel configuration parameters, as returned from the RPC call.
        fake_kernel_params = make_kernel_parameters()
        fake_params = fake_kernel_params._asdict()

        # Stub RPC call to return the fake configuration parameters.
        clients = []
        for _ in range(10):
            client = Mock()
            client.localIdent = factory.make_name("system_id")
            client.side_effect = lambda *args, **kwargs: (
                succeed(dict(fake_params))
            )
            clients.append(client)
        client_service = Mock()
        client_service.getClientNow.side_effect = [
            succeed(client) for client in clients
        ]
        client_service.getAllClients.return_value = clients

        # get_boot_method_reader() takes a dict() of parameters and returns an
        # `IReader` of a PXE configuration, rendered by
        # `PXEBootMethod.get_reader`.
        backend = TFTPBackend(self.make_dir(), client_service)

        # Stub get_reader to return the render parameters.
        method = PXEBootMethod()
        fake_render_result = factory.make_name("render").encode("utf-8")
        render_patch = self.patch(method, "get_reader")
        render_patch.return_value = BytesReader(fake_render_result)

        # Get the reader once.
        remote_ip = factory.make_ipv4_address()
        params_with_ip = dict(fake_params)
        params_with_ip["remote_ip"] = remote_ip
        reader = yield backend.get_boot_method_reader(method, params_with_ip)
        self.addCleanup(reader.finish)

        # Get the reader twice.
        params_with_ip = dict(fake_params)
        params_with_ip["remote_ip"] = remote_ip
        reader = yield backend.get_boot_method_reader(method, params_with_ip)
        self.addCleanup(reader.finish)

        # Only one client is saved.
        self.assertEqual(clients[0], backend.client_to_remote[remote_ip])

        # Only the first client should have been called twice, and all the
        # other clients should not have been called.
        self.assertEqual(2, clients[0].call_count)
        for idx in range(1, 10):
            clients[idx].assert_not_called()

    @inlineCallbacks
    def test_get_boot_method_reader_uses_different_clients(self):
        # Fake kernel configuration parameters, as returned from the RPC call.
        fake_kernel_params = make_kernel_parameters()
        fake_params = fake_kernel_params._asdict()

        # Stub RPC call to return the fake configuration parameters.
        clients = []
        for _ in range(10):
            client = Mock()
            client.localIdent = factory.make_name("system_id")
            client.side_effect = lambda *args, **kwargs: (
                succeed(dict(fake_params))
            )
            clients.append(client)
        client_service = Mock()
        client_service.getClientNow.side_effect = [
            succeed(client) for client in clients
        ]
        client_service.getAllClients.return_value = clients

        # get_boot_method_reader() takes a dict() of parameters and returns an
        # `IReader` of a PXE configuration, rendered by
        # `PXEBootMethod.get_reader`.
        backend = TFTPBackend(self.make_dir(), client_service)

        # Stub get_reader to return the render parameters.
        method = PXEBootMethod()
        fake_render_result = factory.make_name("render").encode("utf-8")
        render_patch = self.patch(method, "get_reader")
        render_patch.return_value = BytesReader(fake_render_result)

        # Get the reader once.
        remote_ip_one = factory.make_ipv4_address()
        params_with_ip = dict(fake_params)
        params_with_ip["remote_ip"] = remote_ip_one
        reader = yield backend.get_boot_method_reader(method, params_with_ip)
        self.addCleanup(reader.finish)

        # Get the reader twice.
        remote_ip_two = factory.make_ipv4_address()
        params_with_ip = dict(fake_params)
        params_with_ip["remote_ip"] = remote_ip_two
        reader = yield backend.get_boot_method_reader(method, params_with_ip)
        self.addCleanup(reader.finish)

        # The both clients are saved.
        self.assertEqual(clients[0], backend.client_to_remote[remote_ip_one])
        self.assertEqual(clients[1], backend.client_to_remote[remote_ip_two])

        # Only the first and second client should have been called once, and
        # all the other clients should not have been called.
        self.assertEqual(1, clients[0].call_count)
        self.assertEqual(1, clients[1].call_count)
        for idx in range(2, 10):
            clients[idx].assert_not_called()

    @inlineCallbacks
    def test_get_boot_method_reader_grabs_new_client_on_lost_conn(self):
        # Fake kernel configuration parameters, as returned from the RPC call.
        fake_kernel_params = make_kernel_parameters()
        fake_params = fake_kernel_params._asdict()

        # Stub RPC call to return the fake configuration parameters.
        clients = []
        for _ in range(10):
            client = Mock()
            client.localIdent = factory.make_name("system_id")
            client.side_effect = lambda *args, **kwargs: (
                succeed(dict(fake_params))
            )
            clients.append(client)
        client_service = Mock()
        client_service.getClientNow.side_effect = [
            succeed(client) for client in clients
        ]
        client_service.getAllClients.side_effect = [clients[1:], clients[2:]]

        # get_boot_method_reader() takes a dict() of parameters and returns an
        # `IReader` of a PXE configuration, rendered by
        # `PXEBootMethod.get_reader`.
        backend = TFTPBackend(self.make_dir(), client_service)

        # Stub get_reader to return the render parameters.
        method = PXEBootMethod()
        fake_render_result = factory.make_name("render").encode("utf-8")
        render_patch = self.patch(method, "get_reader")
        render_patch.return_value = BytesReader(fake_render_result)

        # Get the reader once.
        remote_ip = factory.make_ipv4_address()
        params_with_ip = dict(fake_params)
        params_with_ip["remote_ip"] = remote_ip
        reader = yield backend.get_boot_method_reader(method, params_with_ip)
        self.addCleanup(reader.finish)

        # The first client is now saved.
        self.assertEqual(clients[0], backend.client_to_remote[remote_ip])

        # Get the reader twice.
        params_with_ip = dict(fake_params)
        params_with_ip["remote_ip"] = remote_ip
        reader = yield backend.get_boot_method_reader(method, params_with_ip)
        self.addCleanup(reader.finish)

        # The second client is now saved.
        self.assertEqual(clients[1], backend.client_to_remote[remote_ip])

        # Only the first and second client should have been called once, and
        # all the other clients should not have been called.
        self.assertEqual(1, clients[0].call_count)
        self.assertEqual(1, clients[1].call_count)
        for idx in range(2, 10):
            clients[idx].assert_not_called()

    @inlineCallbacks
    def test_get_boot_method_reader_returns_rendered_params(self):
        osystem = factory.make_name("ubuntu")
        release = factory.make_name("focal")
        label = factory.make_name("stable")
        # Fake kernel configuration parameters, as returned from the RPC call.
        fake_kernel_params = make_kernel_parameters(
            osystem=osystem,
            release=release,
            label=label,
            kernel_osystem=osystem,
            kernel_release=release,
            kernel_label=label,
        )
        fake_params = fake_kernel_params._asdict()

        # Stub RPC call to return the fake configuration parameters.
        client = Mock()
        client.localIdent = factory.make_name("system_id")
        client.return_value = succeed(fake_params)
        client_service = Mock()
        client_service.getClientNow.return_value = succeed(client)

        # get_boot_method_reader() takes a dict() of parameters and returns an
        # `IReader` of a PXE configuration, rendered by
        # `PXEBootMethod.get_reader`.
        backend = TFTPBackend(self.make_dir(), client_service)

        # Stub get_reader to return the render parameters.
        method = PXEBootMethod()
        fake_render_result = factory.make_name("render").encode("utf-8")
        render_patch = self.patch(method, "get_reader")
        render_patch.return_value = BytesReader(fake_render_result)

        # Get the rendered configuration, which will actually be a JSON dump
        # of the render-time parameters.
        params_with_ip = dict(fake_params)
        params_with_ip["remote_ip"] = factory.make_ipv4_address()
        reader = yield backend.get_boot_method_reader(method, params_with_ip)
        self.addCleanup(reader.finish)
        self.assertIsInstance(reader, BytesReader)
        output = reader.read(10000)

        # The result has been rendered by `method.get_reader`.
        self.assertEqual(fake_render_result, output)
        method.get_reader.assert_called_once_with(
            backend, kernel_params=fake_kernel_params, **params_with_ip
        )

    @inlineCallbacks
    def test_get_boot_method_reader_returns_rendered_params_for_local(self):
        # Fake kernel configuration parameters, as returned from the RPC call.
        fake_kernel_params = make_kernel_parameters(
            purpose="local",
            label="local",
            kernel_label="local",
            xinstall_path="",
        )
        fake_params = fake_kernel_params._asdict()
        del fake_params["label"]

        # Stub RPC call to return the fake configuration parameters.
        client = Mock()
        client.localIdent = factory.make_name("system_id")
        client.return_value = succeed(fake_params)
        client_service = Mock()
        client_service.getClientNow.return_value = succeed(client)

        # get_boot_method_reader() takes a dict() of parameters and returns an
        # `IReader` of a PXE configuration, rendered by
        # `PXEBootMethod.get_reader`.
        backend = TFTPBackend(self.make_dir(), client_service)

        # Stub get_reader to return the render parameters.
        method = PXEBootMethod()
        fake_render_result = factory.make_name("render").encode("utf-8")
        render_patch = self.patch(method, "get_reader")
        render_patch.return_value = BytesReader(fake_render_result)

        # Get the rendered configuration, which will actually be a JSON dump
        # of the render-time parameters.
        params_with_ip = dict(fake_params)
        params_with_ip["remote_ip"] = factory.make_ipv4_address()
        reader = yield backend.get_boot_method_reader(method, params_with_ip)
        self.addCleanup(reader.finish)
        self.assertIsInstance(reader, BytesReader)
        output = reader.read(10000)

        # The result has been rendered by `method.get_reader`.
        self.assertEqual(fake_render_result, output)
        method.get_reader.assert_called_once_with(
            backend, kernel_params=fake_kernel_params, **params_with_ip
        )

    @inlineCallbacks
    def test_get_boot_method_reader_returns_rendered_params_local_device(self):
        # Fake kernel configuration parameters, as returned from the RPC call.
        fake_kernel_params = make_kernel_parameters(
            purpose="local",
            label="local",
            kernel_label="local",
            xinstall_path="",
        )
        fake_params = fake_kernel_params._asdict()
        del fake_params["label"]

        # Set purpose to `local-device` as this is what will be passed on.
        fake_params["purpose"] = "local-device"

        # Stub RPC call to return the fake configuration parameters.
        client = Mock()
        client.localIdent = factory.make_name("system_id")
        client.return_value = succeed(fake_params)
        client_service = Mock()
        client_service.getClientNow.return_value = succeed(client)

        # get_boot_method_reader() takes a dict() of parameters and returns an
        # `IReader` of a PXE configuration, rendered by
        # `PXEBootMethod.get_reader`.
        backend = TFTPBackend(self.make_dir(), client_service)

        # Stub get_reader to return the render parameters.
        method = PXEBootMethod()
        fake_render_result = factory.make_name("render").encode("utf-8")
        render_patch = self.patch(method, "get_reader")
        render_patch.return_value = BytesReader(fake_render_result)

        # Get the rendered configuration, which will actually be a JSON dump
        # of the render-time parameters.
        params_with_ip = dict(fake_params)
        params_with_ip["remote_ip"] = factory.make_ipv4_address()
        reader = yield backend.get_boot_method_reader(method, params_with_ip)
        self.addCleanup(reader.finish)
        self.assertIsInstance(reader, BytesReader)
        output = reader.read(10000)

        # The result has been rendered by `method.get_reader`.
        self.assertEqual(fake_render_result, output)
        method.get_reader.assert_called_once_with(
            backend, kernel_params=fake_kernel_params, **params_with_ip
        )

    @inlineCallbacks
    def test_get_boot_method_reader_returns_no_image(self):
        # Fake kernel configuration parameters, as returned from the RPC call.
        fake_kernel_params = make_kernel_parameters(
            label="no-such-image", kernel_label="no-such-image"
        )
        fake_params = fake_kernel_params._asdict()

        # Stub RPC call to return the fake configuration parameters.
        client = Mock()
        client.localIdent = factory.make_name("system_id")
        client.return_value = succeed(fake_params)
        client_service = Mock()
        client_service.getClientNow.return_value = succeed(client)

        # get_boot_method_reader() takes a dict() of parameters and returns an
        # `IReader` of a PXE configuration, rendered by
        # `PXEBootMethod.get_reader`.
        backend = TFTPBackend(self.make_dir(), client_service)

        # Stub get_reader to return the render parameters.
        method = PXEBootMethod()
        fake_render_result = factory.make_name("render").encode("utf-8")
        render_patch = self.patch(method, "get_reader")
        render_patch.return_value = BytesReader(fake_render_result)

        # Get the rendered configuration, which will actually be a JSON dump
        # of the render-time parameters.
        params_with_ip = dict(fake_params)
        params_with_ip["remote_ip"] = factory.make_ipv4_address()
        reader = yield backend.get_boot_method_reader(method, params_with_ip)
        self.addCleanup(reader.finish)
        self.assertIsInstance(reader, BytesReader)
        output = reader.read(10000)

        # The result has been rendered by `method.get_reader`.
        self.assertEqual(fake_render_result, output)
        method.get_reader.assert_called_once_with(
            backend, kernel_params=fake_kernel_params, **params_with_ip
        )

    @inlineCallbacks
    def test_get_boot_method_render_substitutes_armhf_in_params(self):
        # get_config_reader() should substitute "arm" for "armhf" in the
        # arch field of the parameters (mapping from pxe to maas
        # namespace).
        config_path = b"pxelinux.cfg/default-arm"
        backend = TFTPBackend(self.make_dir(), "http://example.com/")
        # python-tx-tftp sets up call context so that backends can discover
        # more about the environment in which they're running.
        call_context = {
            "local": (factory.make_ipv4_address(), factory.pick_port()),
            "remote": (factory.make_ipv4_address(), factory.pick_port()),
        }

        @partial(self.patch, backend, "get_boot_method_reader")
        def get_boot_method_reader(boot_method, params):
            params_json = json.dumps(params).encode("ascii")
            params_json_reader = BytesReader(params_json)
            return succeed(params_json_reader)

        reader = yield context.call(
            call_context, backend.get_reader, config_path
        )
        output = reader.read(10000).decode("ascii")
        observed_params = json.loads(output)
        # XXX: GavinPanella 2015-11-25 bug=1519804: get_by_pxealias() on
        # ArchitectureRegistry is not stable, so we permit either here.
        self.assertIn(observed_params["arch"], ["armhf", "arm64"])

    def test_get_kernel_params_filters_out_unnecessary_arguments(self):
        params_okay = {
            name.decode("ascii"): factory.make_name("value")
            for name, _ in GetBootConfig.arguments
        }
        params_other = {
            factory.make_name("name"): factory.make_name("value")
            for _ in range(3)
        }
        params_all = params_okay.copy()
        params_all.update(params_other)

        client = Mock()
        client.localIdent = params_okay["system_id"]
        client_service = Mock()
        client_service.getClientNow.return_value = succeed(client)

        backend = TFTPBackend(self.make_dir(), client_service)
        backend.fetcher = Mock()

        backend.get_kernel_params(params_all)

        backend.fetcher.assert_called_once_with(
            client, GetBootConfig, **params_okay
        )

    def test_get_cache_reader(self):
        params_okay = {
            name.decode("ascii"): factory.make_name("value")
            for name, _ in GetBootConfig.arguments
        }

        client = Mock()
        client.localIdent = params_okay["system_id"]
        client_service = Mock()
        client_service.getClientNow.return_value = succeed(client)

        backend = TFTPBackend(self.make_dir(), client_service)
        backend._cache_proxy = Mock()

        filename = factory.make_name()

        backend.get_cache_reader(f"/grub/{filename}")

        backend._cache_proxy.request.assert_called_once_with(
            b"GET",
            f"http://localhost:5248/images/grub/{filename}".encode("utf-8"),
        )


class TestTFTPService(MAASTestCase):
    def test_tftp_service(self):
        # A TFTP service is configured and added to the top-level service.
        interfaces = [factory.make_ipv4_address(), factory.make_ipv6_address()]
        self.patch(
            tftp_module, "get_all_interface_addresses", lambda: interfaces
        )
        example_root = self.make_dir()
        example_client_service = Mock()
        example_port = factory.pick_port()
        tftp_service = TFTPService(
            resource_root=example_root,
            client_service=example_client_service,
            port=example_port,
        )
        tftp_service.updateServers()
        # The "tftp" service is a multi-service containing UDP servers for
        # each interface defined by get_all_interface_addresses().
        self.assertIsInstance(tftp_service, MultiService)
        # There's also a TimerService that updates the servers every 45s.
        self.assertEqual(tftp_service.refresher.step, 45)
        self.assertEqual(tftp_service.refresher.parent, tftp_service)
        self.assertEqual(tftp_service.refresher.name, "refresher")
        self.assertEqual(
            tftp_service.refresher.call, (tftp_service.updateServers, (), {})
        )

        for server in tftp_service.getServers():
            self.assertIsInstance(server, internet.UDPServer)
            self.assertEqual(len(server.args), 2)
            self.assertEqual(server.args[0], example_port)
            protocol = server.args[1]
            self.assertIsInstance(protocol, TFTP)
            self.assertEqual(protocol.backend.base.path, example_root)
            self.assertEqual(
                protocol.backend.client_service, example_client_service
            )
        # Only the interface used for each service differs.
        self.assertCountEqual(
            [svc.kwargs for svc in tftp_service.getServers()],
            [{"interface": interface} for interface in interfaces],
        )

    def test_tftp_service_rebinds_on_HUP(self):
        # Initial set of interfaces to bind to.
        interfaces = {"1.1.1.1", "2.2.2.2"}
        self.patch(
            tftp_module, "get_all_interface_addresses", lambda: interfaces
        )

        tftp_service = TFTPService(
            resource_root=self.make_dir(),
            client_service=Mock(),
            port=factory.pick_port(),
        )
        tftp_service.updateServers()

        # The child services of tftp_services are named after the
        # interface they bind to.
        self.assertEqual(
            interfaces, {server.name for server in tftp_service.getServers()}
        )

        # Update the set of interfaces to bind to.
        interfaces.add("3.3.3.3")
        interfaces.remove("1.1.1.1")

        # Ask the TFTP service to update its set of servers.
        tftp_service.updateServers()

        # We're in the reactor thread but we want to move the reactor
        # forwards, hence we need to get all explicit about it.
        reactor.runUntilCurrent()

        # The interfaces now bound match the updated interfaces set.
        self.assertEqual(
            interfaces, {server.name for server in tftp_service.getServers()}
        )

    def test_tftp_service_does_not_bind_to_link_local_addresses(self):
        # Initial set of interfaces to bind to.
        ipv4_test_net_3 = IPNetwork("203.0.113.0/24")  # RFC 5737
        normal_addresses = {
            factory.pick_ip_in_network(ipv4_test_net_3),
            factory.make_ipv6_address(),
        }
        link_local_addresses = {
            factory.pick_ip_in_network(IPV4_LINK_LOCAL),
            factory.pick_ip_in_network(IPV6_LINK_LOCAL),
        }
        self.patch(
            tftp_module,
            "get_all_interface_addresses",
            lambda: normal_addresses | link_local_addresses,
        )

        tftp_service = TFTPService(
            resource_root=self.make_dir(),
            client_service=Mock(),
            port=factory.pick_port(),
        )
        tftp_service.updateServers()

        # Only the "normal" addresses have been used.
        self.assertEqual(
            normal_addresses,
            {server.name for server in tftp_service.getServers()},
        )


class FakeStreamSession:
    cancelled = False

    def cancel(self):
        self.cancelled = True


class FakeSession:
    def __init__(self, stream_session):
        self.session = stream_session


class TestTransferTimeTrackingTFTP(MAASTestCase):
    """Tests for `TransferTimeTrackingTFTP`."""

    def clean_filename(self, path):
        datagram = RQDatagram(path, b"octet", {})
        tftp = TransferTimeTrackingTFTP(sentinel.backend)
        return tftp._clean_filename(datagram)

    def test_clean_filename(self):
        self.assertEqual(
            self.clean_filename(b"files/foo.txt"), "files/foo.txt"
        )

    def test_clean_filename_strip_leading_slashes(self):
        self.assertEqual(
            self.clean_filename(b"//files/foo.txt"), "files/foo.txt"
        )

    def test_clean_filename_pxelinux_cfg(self):
        self.assertEqual(
            self.clean_filename(b"pxelinux.cfg/aa-bb-cc-dd-ee-ff"),
            "pxelinux.cfg",
        )

    def test_clean_filename_pxelinux_cfg_arch(self):
        self.assertEqual(
            self.clean_filename(b"s390x/pxelinux.cfg/aa-bb-cc-dd-ee-ff"),
            "pxelinux.cfg",
        )

    def test_clean_filename_grub_cfg(self):
        self.assertEqual(
            self.clean_filename(b"grub/grub.cfg-aa-bb-cc-dd-ee-ff"),
            "grub/grub.cfg",
        )

    def test_clean_filename_windows(self):
        self.assertEqual(
            self.clean_filename(b"\\boot\\winpe.wim"), "boot/winpe.wim"
        )


class TestTransferTimeTrackingTFTPStartSession(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    @inlineCallbacks
    def test_wb_start_session(self):
        prometheus_metrics = create_metrics(
            METRICS_DEFINITIONS, registry=prometheus_client.CollectorRegistry()
        )
        stream_session = FakeStreamSession()
        session = FakeSession(stream_session)
        tftp_mock = self.patch(tftp.protocol.TFTP, "_startSession")
        tftp_mock.return_value = succeed(session)
        tracking_tftp = TransferTimeTrackingTFTP(sentinel.backend)
        datagram = RQDatagram(b"file.txt", b"octet", {})
        result = yield tracking_tftp._startSession(
            datagram,
            "192.168.1.1",
            "read",
            prometheus_metrics=prometheus_metrics,
        )
        result.session.cancel()
        metrics = prometheus_metrics.generate_latest().decode("ascii")
        self.assertIs(result, session)
        self.assertTrue(stream_session.cancelled)
        self.assertIn(
            'maas_tftp_file_transfer_latency_count{filename="file.txt"} 1.0',
            metrics,
        )


class TestTrackTFTPLatency(MAASTestCase):
    def test_track_tftp_latency(self):
        class Thing:
            did_something = False

            def do_something(self):
                self.did_something = True
                return True

        thing = Thing()
        start_time = time.time()
        prometheus_metrics = create_metrics(
            METRICS_DEFINITIONS, registry=prometheus_client.CollectorRegistry()
        )
        thing.do_something = track_tftp_latency(
            thing.do_something,
            start_time=start_time,
            filename="myfile.txt",
            prometheus_metrics=prometheus_metrics,
        )
        time_mock = self.patch(tftp_module, "time")
        time_mock.return_value = start_time + 0.5
        result = thing.do_something()
        self.assertTrue(result)
        self.assertTrue(thing.did_something)

        metrics = prometheus_metrics.generate_latest().decode("ascii")
        self.assertIn(
            'maas_tftp_file_transfer_latency_count{filename="myfile.txt"} 1.0',
            metrics,
        )
        self.assertIn(
            "maas_tftp_file_transfer_latency_bucket"
            '{filename="myfile.txt",le="0.5"} 1.0',
            metrics,
        )
        self.assertIn(
            "maas_tftp_file_transfer_latency_bucket"
            '{filename="myfile.txt",le="0.25"} 0.0',
            metrics,
        )


class DummyProtocol(Protocol):
    def doStop(self):
        pass


class TestPort(MAASTestCase):
    """Tests for :py:class:`Port`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def test_getHost_works_with_IPv4_address(self):
        port = Port(0, DummyProtocol(), "127.0.0.1")
        port.addressFamily = AF_INET
        port.startListening()
        self.addCleanup(port.stopListening)
        self.assertEqual(
            IPv4Address("UDP", "127.0.0.1", port._realPortNumber),
            port.getHost(),
        )

    def test_getHost_works_with_IPv6_address(self):
        port = Port(0, DummyProtocol(), "::1")
        port.addressFamily = AF_INET6
        port.startListening()
        self.addCleanup(port.stopListening)
        self.assertEqual(
            IPv6Address("UDP", "::1", port._realPortNumber), port.getHost()
        )


class TestUDPServer(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def test_getPort_calls__listenUDP_with_args_from_constructor(self):
        server = UDPServer(sentinel.foo, bar=sentinel.bar)
        _listenUDP = self.patch(server, "_listenUDP")
        _listenUDP.return_value = sentinel.port
        self.assertEqual(sentinel.port, server._getPort())
        _listenUDP.assert_called_once_with(sentinel.foo, bar=sentinel.bar)

    def test_listenUDP_with_IPv4_address(self):
        server = UDPServer(0, DummyProtocol(), "127.0.0.1")
        port = server._getPort()
        self.addCleanup(port.stopListening)
        self.assertEqual(AF_INET, port.addressFamily)

    def test_listenUDP_with_IPv6_address(self):
        server = UDPServer(0, DummyProtocol(), "::1")
        port = server._getPort()
        self.addCleanup(port.stopListening)
        self.assertEqual(AF_INET6, port.addressFamily)


class TestLogRequest(MAASTestCase):
    """Tests for `log_request`."""

    def test_defers_log_call_later(self):
        clock = Clock()
        log_request(sentinel.filename, clock)
        self.assertEqual(len(clock.calls), 1)
        [call] = clock.calls
        self.assertEqual(call.getTime(), 0.0)

    def test_sends_event_later(self):
        send_event = self.patch(tftp_module, "send_node_event_ip_address")
        ip = factory.make_ip_address()
        self.patch(tftp_module.tftp, "get_remote_address").return_value = (
            ip,
            sentinel.port,
        )
        clock = Clock()
        log_request(sentinel.filename, clock)
        send_event.assert_not_called()
        clock.advance(0.0)
        send_event.assert_called_once_with(
            ip_address=ip,
            description=sentinel.filename,
            event_type=EVENT_TYPES.NODE_TFTP_REQUEST,
        )

    def test_logs_to_server_log(self):
        self.patch(tftp_module, "send_node_event_ip_address")
        ip = factory.make_ip_address()
        self.patch(tftp_module.tftp, "get_remote_address").return_value = (
            ip,
            sentinel.port,
        )
        clock = Clock()
        file_name = factory.make_name("file")
        with TwistedLoggerFixture() as logger:
            log_request(file_name, clock)
            clock.advance(0.0)  # Don't leave anything in the reactor.
        self.assertEqual(f"{file_name} requested by {ip}", logger.output)

    def test_logs_when_sending_event_errors(self):
        send_event = self.patch(tftp_module, "send_node_event_ip_address")
        send_event.side_effect = factory.make_exception()
        clock = Clock()
        log_request(sentinel.filename, clock)
        send_event.assert_not_called()
        with TwistedLoggerFixture() as logger:
            clock.advance(0.0)
        self.assertIn("Logging TFTP request failed.", logger.messages)
