# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maastesting.httpd`."""


from contextlib import closing
import gzip
from io import BytesIO
import os.path
from socket import gethostbyname, gethostname
from unittest import skip
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from maastesting.fixtures import ProxiesDisabledFixture
from maastesting.httpd import HTTPServerFixture, ThreadingHTTPServer
from maastesting.testcase import MAASTestCase


class TestHTTPServerFixture(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.useFixture(ProxiesDisabledFixture())

    @skip("XXX: bigjools 2013-09-13 bug=1224837: Causes intermittent failures")
    def test_init(self):
        host = gethostname()
        fixture = HTTPServerFixture(host=host)
        self.assertIsInstance(fixture.server, ThreadingHTTPServer)
        expected_url = "http://%s:%d/" % (
            gethostbyname(host),
            fixture.server.server_port,
        )
        self.assertEqual(expected_url, fixture.url)

    def test_use(self):
        filename = os.path.relpath(__file__)
        self.assertTrue(os.path.isfile(filename))
        with HTTPServerFixture() as httpd:
            url = urljoin(httpd.url, filename)
            with closing(urlopen(url)) as http_in:
                http_data_in = http_in.read()
        with open(filename, "rb") as file_in:
            file_data_in = file_in.read()
        self.assertEqual(
            file_data_in,
            http_data_in,
            f"The content of {url} differs from {filename}.",
        )

    def ungzip(self, content):
        gz = gzip.GzipFile(fileobj=BytesIO(content))
        return gz.read()

    def test_supports_gzip(self):
        filename = os.path.relpath(__file__)
        with HTTPServerFixture() as httpd:
            url = urljoin(httpd.url, filename)
            headers = {"Accept-Encoding": "gzip, deflate"}
            request = Request(url, None, headers=headers)
            with closing(urlopen(request)) as http_in:
                http_headers = http_in.info()
                http_data_in = http_in.read()
        self.assertEqual("gzip", http_headers["Content-Encoding"])
        with open(filename, "rb") as file_in:
            file_data_in = file_in.read()
        http_data_decompressed = self.ungzip(http_data_in)
        self.assertEqual(
            file_data_in,
            http_data_decompressed,
            f"The content of {url} differs from {filename}.",
        )
