# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test monkey patches."""

__all__ = []

from unittest.mock import sentinel

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver.monkey import (
    add_patches_to_txtftp,
    augment_twisted_deferToThreadPool,
    get_patched_URI,
)
from testtools.deferredruntest import assert_fails_with
from testtools.matchers import Equals
import tftp.datagram
from twisted.internet.defer import Deferred
from twisted.internet.threads import deferToThread


class TestAddTermErrorCodeToTFTP(MAASTestCase):
    def test_adds_error_code_8(self):
        self.patch(tftp.datagram, "errors", {})
        add_patches_to_txtftp()
        self.assertIn(8, tftp.datagram.errors)
        self.assertEqual(
            "Terminate transfer due to option negotiation",
            tftp.datagram.errors.get(8),
        )

    def test_skips_adding_error_code_if_already_present(self):
        self.patch(tftp.datagram, "errors", {8: sentinel.error_8})
        add_patches_to_txtftp()
        self.assertEqual(sentinel.error_8, tftp.datagram.errors.get(8))


class TestAugmentDeferToThreadPool(MAASTestCase):
    """Tests for `augment_twisted_deferToThreadPool`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def setUp(self):
        super(TestAugmentDeferToThreadPool, self).setUp()
        augment_twisted_deferToThreadPool()

    def test_functions_returning_Deferreds_from_threads_crash(self):
        return assert_fails_with(deferToThread(Deferred), TypeError)

    def test_functions_returning_other_from_threads_are_okay(self):
        return deferToThread(round, 12.34).addCallback(self.assertEqual, 12)


class TestPatchedURI(MAASTestCase):
    def test__parses_URL_with_hostname(self):
        hostname = factory.make_name("host").encode("ascii")
        path = factory.make_name("path").encode("ascii")
        uri = get_patched_URI().fromBytes(b"http://%s/%s" % (hostname, path))
        self.expectThat(uri.host, Equals(hostname))
        self.expectThat(uri.path, Equals(b"/%s" % path))
        self.expectThat(uri.port, Equals(80))

    def test__parses_URL_with_hostname_and_port(self):
        hostname = factory.make_name("host").encode("ascii")
        port = factory.pick_port()
        path = factory.make_name("path").encode("ascii")
        uri = get_patched_URI().fromBytes(
            b"http://%s:%d/%s" % (hostname, port, path)
        )
        self.expectThat(uri.host, Equals(hostname))
        self.expectThat(uri.path, Equals(b"/%s" % path))
        self.expectThat(uri.port, Equals(port))

    def test__parses_URL_with_IPv4_address(self):
        ip = factory.make_ipv4_address().encode("ascii")
        path = factory.make_name("path").encode("ascii")
        uri = get_patched_URI().fromBytes(b"http://%s/%s" % (ip, path))
        self.expectThat(uri.host, Equals(ip))
        self.expectThat(uri.path, Equals(b"/%s" % path))
        self.expectThat(uri.port, Equals(80))

    def test__parses_URL_with_IPv4_address_and_port(self):
        ip = factory.make_ipv4_address().encode("ascii")
        port = factory.pick_port()
        path = factory.make_name("path").encode("ascii")
        uri = get_patched_URI().fromBytes(
            b"http://%s:%d/%s" % (ip, port, path)
        )
        self.expectThat(uri.host, Equals(ip))
        self.expectThat(uri.path, Equals(b"/%s" % path))
        self.expectThat(uri.port, Equals(port))

    def test__parses_URL_with_IPv6_address(self):
        ip = factory.make_ipv6_address().encode("ascii")
        path = factory.make_name("path").encode("ascii")
        uri = get_patched_URI().fromBytes(b"http://[%s]/%s" % (ip, path))
        self.expectThat(uri.host, Equals(b"%s" % ip))
        self.expectThat(uri.path, Equals(b"/%s" % path))
        self.expectThat(uri.port, Equals(80))

    def test__parses_URL_with_IPv6_address_and_port(self):
        ip = factory.make_ipv6_address().encode("ascii")
        port = factory.pick_port()
        path = factory.make_name("path").encode("ascii")
        uri = get_patched_URI().fromBytes(
            b"http://[%s]:%d/%s" % (ip, port, path)
        )
        self.expectThat(uri.host, Equals(b"%s" % ip))
        self.expectThat(uri.path, Equals(b"/%s" % path))
        self.expectThat(uri.port, Equals(port))
