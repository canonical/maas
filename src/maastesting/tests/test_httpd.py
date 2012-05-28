# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maastesting.httpd`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from contextlib import closing
from os.path import relpath
from socket import (
    gethostbyname,
    gethostname,
    )
from urllib2 import urlopen
from urlparse import urljoin

from maastesting.httpd import (
    HTTPServerFixture,
    ThreadingHTTPServer,
    )
from maastesting.testcase import TestCase
from testtools.matchers import FileExists


class TestHTTPServerFixture(TestCase):

    def test_init(self):
        host = gethostname()
        fixture = HTTPServerFixture(host=host)
        self.assertIsInstance(fixture.server, ThreadingHTTPServer)
        expected_url = "http://%s:%d/" % (
            gethostbyname(host), fixture.server.server_port)
        self.assertEqual(expected_url, fixture.url)

    def test_use(self):
        filename = relpath(__file__)
        self.assertThat(filename, FileExists())
        with HTTPServerFixture() as httpd:
            url = urljoin(httpd.url, filename)
            with closing(urlopen(url)) as http_in:
                http_data_in = http_in.read()
        with open(filename, "rb") as file_in:
            file_data_in = file_in.read()
        self.assertEqual(
            file_data_in, http_data_in,
            "The content of %s differs from %s." % (url, filename))
