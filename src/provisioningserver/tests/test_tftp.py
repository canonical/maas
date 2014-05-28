# Copyright 2005-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the maastftp Twisted plugin."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from functools import partial
import json
from os import path
from urllib import urlencode
from urlparse import (
    parse_qsl,
    urlparse,
    )

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
import mock
from provisioningserver import tftp as tftp_module
from provisioningserver.boot import BytesReader
from provisioningserver.boot.pxe import PXEBootMethod
from provisioningserver.boot.tests.test_pxe import compose_config_path
from provisioningserver.tests.test_kernel_opts import make_kernel_parameters
from provisioningserver.tftp import (
    TFTPBackend,
    TFTPService,
    )
from testtools.deferredruntest import AsynchronousDeferredRunTest
from testtools.matchers import (
    AfterPreprocessing,
    AllMatch,
    Equals,
    IsInstance,
    MatchesAll,
    MatchesStructure,
    )
from tftp.backend import IReader
from tftp.protocol import TFTP
from twisted.application import internet
from twisted.application.service import MultiService
from twisted.internet import reactor
from twisted.internet.defer import (
    inlineCallbacks,
    succeed,
    )
from twisted.python import context
from zope.interface.verify import verifyObject


class TestBytesReader(MAASTestCase):
    """Tests for `provisioningserver.tftp.BytesReader`."""

    def test_interfaces(self):
        reader = BytesReader(b"")
        self.addCleanup(reader.finish)
        verifyObject(IReader, reader)

    def test_read(self):
        data = factory.getRandomString(size=10).encode("ascii")
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
    """Tests for `provisioningserver.tftp.TFTPBackend`."""

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    def test_init(self):
        temp_dir = self.make_dir()
        generator_url = "http://%s.example.com/%s" % (
            factory.make_name("domain"), factory.make_name("path"))
        backend = TFTPBackend(temp_dir, generator_url)
        self.assertEqual((True, False), (backend.can_read, backend.can_write))
        self.assertEqual(temp_dir, backend.base.path)
        self.assertEqual(generator_url, backend.generator_url.geturl())

    def test_get_generator_url(self):
        # get_generator_url() merges the parameters obtained from the request
        # file path (arch, subarch, name) into the configured generator URL.
        mac = factory.getRandomMACAddress("-")
        dummy = factory.make_name("dummy").encode("ascii")
        backend_url = b"http://example.com/?" + urlencode({b"dummy": dummy})
        backend = TFTPBackend(self.make_dir(), backend_url)
        # params is an example of the parameters obtained from a request.
        params = {"mac": mac}
        generator_url = urlparse(backend.get_generator_url(params))
        self.assertEqual("example.com", generator_url.hostname)
        query = parse_qsl(generator_url.query)
        query_expected = [
            ("dummy", dummy),
            ("mac", mac),
            ]
        self.assertItemsEqual(query_expected, query)

    @inlineCallbacks
    def test_get_reader_regular_file(self):
        # TFTPBackend.get_reader() returns a regular FilesystemReader for
        # paths not matching re_config_file.
        data = factory.getRandomString().encode("ascii")
        temp_file = self.make_file(name="example", contents=data)
        temp_dir = path.dirname(temp_file)
        backend = TFTPBackend(temp_dir, "http://nowhere.example.com/")
        reader = yield backend.get_reader("example")
        self.addCleanup(reader.finish)
        self.assertEqual(len(data), reader.size)
        self.assertEqual(data, reader.read(len(data)))
        self.assertEqual(b"", reader.read(1))

    @inlineCallbacks
    def test_get_render_file(self):
        # For paths matching PXEBootMethod.match_path, TFTPBackend.get_reader()
        # returns a Deferred that will yield a BytesReader.
        cluster_uuid = factory.getRandomUUID()
        self.patch(tftp_module, 'get_cluster_uuid').return_value = (
            cluster_uuid)
        mac = factory.getRandomMACAddress("-")
        config_path = compose_config_path(mac)
        backend = TFTPBackend(self.make_dir(), b"http://example.com/")
        # python-tx-tftp sets up call context so that backends can discover
        # more about the environment in which they're running.
        call_context = {
            "local": (
                factory.getRandomIPAddress(),
                factory.getRandomPort()),
            "remote": (
                factory.getRandomIPAddress(),
                factory.getRandomPort()),
            }

        @partial(self.patch, backend, "get_boot_method_reader")
        def get_boot_method_reader(boot_method, params):
            params_json = json.dumps(params)
            params_json_reader = BytesReader(params_json)
            return succeed(params_json_reader)

        reader = yield context.call(
            call_context, backend.get_reader, config_path)
        output = reader.read(10000)
        # The addresses provided by python-tx-tftp in the call context are
        # passed over the wire as address:port strings.
        expected_params = {
            "mac": mac,
            "local": call_context["local"][0],  # address only.
            "remote": call_context["remote"][0],  # address only.
            "cluster_uuid": cluster_uuid,
            }
        observed_params = json.loads(output)
        self.assertEqual(expected_params, observed_params)

    @inlineCallbacks
    def test_get_boot_method_reader_returns_rendered_params(self):
        # get_boot_method_reader() takes a dict() of parameters and returns an
        # `IReader` of a PXE configuration, rendered by
        # `PXEBootMethod.get_reader`.
        backend = TFTPBackend(self.make_dir(), b"http://example.com/")
        # Fake configuration parameters, as discovered from the file path.
        fake_params = {"mac": factory.getRandomMACAddress("-")}
        # Fake kernel configuration parameters, as returned from the API call.
        fake_kernel_params = make_kernel_parameters()

        # Stub get_page to return the fake API configuration parameters.
        fake_get_page_result = json.dumps(fake_kernel_params._asdict())
        get_page_patch = self.patch(backend, "get_page")
        get_page_patch.return_value = succeed(fake_get_page_result)

        # Stub get_reader to return the render parameters.
        method = PXEBootMethod()
        fake_render_result = factory.make_name("render").encode("utf-8")
        render_patch = self.patch(method, "get_reader")
        render_patch.return_value = BytesReader(fake_render_result)

        # Get the rendered configuration, which will actually be a JSON dump
        # of the render-time parameters.
        reader = yield backend.get_boot_method_reader(method, fake_params)
        self.addCleanup(reader.finish)
        self.assertIsInstance(reader, BytesReader)
        output = reader.read(10000)

        # The kernel parameters were fetched using `backend.get_page`.
        self.assertThat(backend.get_page, MockCalledOnceWith(mock.ANY))

        # The result has been rendered by `method.get_reader`.
        self.assertEqual(fake_render_result.encode("utf-8"), output)
        self.assertThat(method.get_reader, MockCalledOnceWith(
            backend, kernel_params=fake_kernel_params, **fake_params))

    @inlineCallbacks
    def test_get_boot_method_render_substitutes_armhf_in_params(self):
        # get_config_reader() should substitute "arm" for "armhf" in the
        # arch field of the parameters (mapping from pxe to maas
        # namespace).
        cluster_uuid = factory.getRandomUUID()
        self.patch(tftp_module, 'get_cluster_uuid').return_value = (
            cluster_uuid)
        config_path = "pxelinux.cfg/default-arm"
        backend = TFTPBackend(self.make_dir(), b"http://example.com/")
        # python-tx-tftp sets up call context so that backends can discover
        # more about the environment in which they're running.
        call_context = {
            "local": (
                factory.getRandomIPAddress(),
                factory.getRandomPort()),
            "remote": (
                factory.getRandomIPAddress(),
                factory.getRandomPort()),
            }

        @partial(self.patch, backend, "get_boot_method_reader")
        def get_boot_method_reader(boot_method, params):
            params_json = json.dumps(params)
            params_json_reader = BytesReader(params_json)
            return succeed(params_json_reader)

        reader = yield context.call(
            call_context, backend.get_reader, config_path)
        output = reader.read(10000)
        observed_params = json.loads(output)
        self.assertEqual("armhf", observed_params["arch"])


class TestTFTPService(MAASTestCase):

    def test_tftp_service(self):
        # A TFTP service is configured and added to the top-level service.
        interfaces = [
            factory.getRandomIPAddress(),
            factory.getRandomIPAddress(),
            ]
        self.patch(
            tftp_module, "get_all_interface_addresses",
            lambda: interfaces)
        example_root = self.make_dir()
        example_generator = "http://example.com/generator"
        example_port = factory.getRandomPort()
        tftp_service = TFTPService(
            resource_root=example_root, generator=example_generator,
            port=example_port)
        tftp_service.updateServers()
        # The "tftp" service is a multi-service containing UDP servers for
        # each interface defined by get_all_interface_addresses().
        self.assertIsInstance(tftp_service, MultiService)
        # There's also a TimerService that updates the servers every 45s.
        self.assertThat(
            tftp_service.refresher, MatchesStructure.byEquality(
                step=45, parent=tftp_service, name="refresher",
                call=(tftp_service.updateServers, (), {}),
            ))
        expected_backend = MatchesAll(
            IsInstance(TFTPBackend),
            AfterPreprocessing(
                lambda backend: backend.base.path,
                Equals(example_root)),
            AfterPreprocessing(
                lambda backend: backend.generator_url.geturl(),
                Equals(example_generator)))
        expected_protocol = MatchesAll(
            IsInstance(TFTP),
            AfterPreprocessing(
                lambda protocol: protocol.backend,
                expected_backend))
        expected_server = MatchesAll(
            IsInstance(internet.UDPServer),
            AfterPreprocessing(
                lambda service: len(service.args),
                Equals(2)),
            AfterPreprocessing(
                lambda service: service.args[0],  # port
                Equals(example_port)),
            AfterPreprocessing(
                lambda service: service.args[1],  # protocol
                expected_protocol))
        self.assertThat(
            tftp_service.getServers(),
            AllMatch(expected_server))
        # Only the interface used for each service differs.
        self.assertItemsEqual(
            [svc.kwargs for svc in tftp_service.getServers()],
            [{"interface": interface} for interface in interfaces])

    def test_tftp_service_rebinds_on_HUP(self):
        # Initial set of interfaces to bind to.
        interfaces = {"1.1.1.1", "2.2.2.2"}
        self.patch(
            tftp_module, "get_all_interface_addresses",
            lambda: interfaces)

        tftp_service = TFTPService(
            resource_root=self.make_dir(), generator="http://mighty/wind",
            port=factory.getRandomPort())
        tftp_service.updateServers()

        # The child services of tftp_services are named after the
        # interface they bind to.
        self.assertEqual(interfaces, {
            server.name for server in tftp_service.getServers()
        })

        # Update the set of interfaces to bind to.
        interfaces.add("3.3.3.3")
        interfaces.remove("1.1.1.1")

        # Ask the TFTP service to update its set of servers.
        tftp_service.updateServers()

        # We're in the reactor thread but we want to move the reactor
        # forwards, hence we need to get all explicit about it.
        reactor.runUntilCurrent()

        # The interfaces now bound match the updated interfaces set.
        self.assertEqual(interfaces, {
            server.name for server in tftp_service.getServers()
        })
