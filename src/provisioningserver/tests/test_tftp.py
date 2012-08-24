# Copyright 2005-2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the maastftp Twisted plugin."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

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
from maastesting.testcase import TestCase
import mock
from provisioningserver.pxe.tftppath import compose_config_path
from provisioningserver.tests.test_kernel_opts import make_kernel_parameters
from provisioningserver.tftp import (
    BytesReader,
    TFTPBackend,
    )
from testtools.deferredruntest import AsynchronousDeferredRunTest
from tftp.backend import IReader
from twisted.internet.defer import (
    inlineCallbacks,
    succeed,
    )
from zope.interface.verify import verifyObject


class TestBytesReader(TestCase):
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


class TestTFTPBackendRegex(TestCase):
    """Tests for `provisioningserver.tftp.TFTPBackend.re_config_file`."""

    @staticmethod
    def get_example_path_and_components():
        """Return a plausible path and its components.

        The path is intended to match `re_config_file`, and the components are
        the expected groups from a match.
        """
        components = {
            "bootpath": b"maas",  # Static.
            "mac": factory.getRandomMACAddress(b"-"),
            }
        config_path = compose_config_path(components["mac"])
        return config_path, components

    def test_re_config_file(self):
        # The regular expression for extracting components of the file path is
        # compatible with the PXE config path generator.
        regex = TFTPBackend.re_config_file
        for iteration in range(10):
            config_path, args = self.get_example_path_and_components()
            match = regex.match(config_path)
            self.assertIsNotNone(match, config_path)
            self.assertEqual(args, match.groupdict())

    def test_re_config_file_with_leading_slash(self):
        # The regular expression for extracting components of the file path
        # doesn't care if there's a leading forward slash; the TFTP server is
        # easy on this point, so it makes sense to be also.
        config_path, args = self.get_example_path_and_components()
        # Ensure there's a leading slash.
        config_path = "/" + config_path.lstrip("/")
        match = TFTPBackend.re_config_file.match(config_path)
        self.assertIsNotNone(match, config_path)
        self.assertEqual(args, match.groupdict())

    def test_re_config_file_without_leading_slash(self):
        # The regular expression for extracting components of the file path
        # doesn't care if there's no leading forward slash; the TFTP server is
        # easy on this point, so it makes sense to be also.
        config_path, args = self.get_example_path_and_components()
        # Ensure there's no leading slash.
        config_path = config_path.lstrip("/")
        match = TFTPBackend.re_config_file.match(config_path)
        self.assertIsNotNone(match, config_path)
        self.assertEqual(args, match.groupdict())


class TestTFTPBackend(TestCase):
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
        bootpath = factory.make_name("bootpath")
        mac = factory.getRandomMACAddress(b"-")
        dummy = factory.make_name("dummy").encode("ascii")
        backend_url = b"http://example.com/?" + urlencode({b"dummy": dummy})
        backend = TFTPBackend(self.make_dir(), backend_url)
        # params is an example of the parameters obtained from a request.
        params = {"bootpath": bootpath, "mac": mac}
        generator_url = urlparse(backend.get_generator_url(params))
        self.assertEqual("example.com", generator_url.hostname)
        query = parse_qsl(generator_url.query)
        query_expected = [
            ("bootpath", bootpath),
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
    def test_get_reader_config_file(self):
        # For paths matching re_config_file, TFTPBackend.get_reader() returns
        # a Deferred that will yield a BytesReader.
        mac = factory.getRandomMACAddress(b"-")
        config_path = compose_config_path(mac)
        backend = TFTPBackend(self.make_dir(), b"http://example.com/")

        @partial(self.patch, backend, "get_config_reader")
        def get_config_reader(params):
            params_json = json.dumps(params)
            params_json_reader = BytesReader(params_json)
            return succeed(params_json_reader)

        reader = yield backend.get_reader(config_path)
        output = reader.read(10000)
        # The expected parameters include bootpath; this is extracted from the
        # file path by re_config_file.
        expected_params = dict(mac=mac, bootpath="maas")
        observed_params = json.loads(output)
        self.assertEqual(expected_params, observed_params)

    @inlineCallbacks
    def test_get_config_reader_returns_rendered_params(self):
        # get_config_reader() takes a dict() of parameters and returns an
        # `IReader` of a PXE configuration, rendered by `render_pxe_config`.
        backend = TFTPBackend(self.make_dir(), b"http://example.com/")
        # Fake configuration parameters, as discovered from the file path.
        fake_params = {
            "bootpath": "maas",
            "mac": factory.getRandomMACAddress(b"-"),
            }
        # Fake kernel configuration parameters, as returned from the API call.
        fake_kernel_params = make_kernel_parameters()

        # Stub get_page to return the fake API configuration parameters.
        fake_get_page_result = json.dumps(fake_kernel_params._asdict())
        get_page_patch = self.patch(backend, "get_page")
        get_page_patch.return_value = succeed(fake_get_page_result)

        # Stub render_pxe_config to return the render parameters.
        fake_render_result = factory.make_name("render")
        render_patch = self.patch(backend, "render_pxe_config")
        render_patch.return_value = fake_render_result

        # Get the rendered configuration, which will actually be a JSON dump
        # of the render-time parameters.
        reader = yield backend.get_config_reader(fake_params)
        self.addCleanup(reader.finish)
        self.assertIsInstance(reader, BytesReader)
        output = reader.read(10000)

        # The kernel parameters were fetched using `backend.get_page`.
        backend.get_page.assert_called_once()

        # The result has been rendered by `backend.render_pxe_config`.
        self.assertEqual(fake_render_result.encode("utf-8"), output)
        backend.render_pxe_config.assert_called_once_with(
            kernel_params=fake_kernel_params, **fake_params)
