# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test monkey patches."""


from testtools.deferredruntest import assert_fails_with
from testtools.matchers import Equals
from twisted.internet.defer import Deferred
from twisted.internet.threads import deferToThread

from maastesting import get_testing_timeout
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver.monkey import (
    augment_twisted_deferToThreadPool,
    get_patched_URI,
)


class TestAugmentDeferToThreadPool(MAASTestCase):
    """Tests for `augment_twisted_deferToThreadPool`."""

    run_tests_with = MAASTwistedRunTest.make_factory(
        timeout=get_testing_timeout()
    )

    def setUp(self):
        super().setUp()
        augment_twisted_deferToThreadPool()

    def test_functions_returning_Deferreds_from_threads_crash(self):
        return assert_fails_with(deferToThread(Deferred), TypeError)

    def test_functions_returning_other_from_threads_are_okay(self):
        return deferToThread(round, 12.34).addCallback(self.assertEqual, 12)


class TestPatchedURI(MAASTestCase):
    def test_parses_URL_with_hostname(self):
        hostname = factory.make_name("host").encode("ascii")
        path = factory.make_name("path").encode("ascii")
        uri = get_patched_URI().fromBytes(b"http://%s/%s" % (hostname, path))
        self.expectThat(uri.host, Equals(hostname))
        self.expectThat(uri.path, Equals(b"/%s" % path))
        self.expectThat(uri.port, Equals(80))

    def test_parses_URL_with_hostname_and_port(self):
        hostname = factory.make_name("host").encode("ascii")
        port = factory.pick_port()
        path = factory.make_name("path").encode("ascii")
        uri = get_patched_URI().fromBytes(
            b"http://%s:%d/%s" % (hostname, port, path)
        )
        self.expectThat(uri.host, Equals(hostname))
        self.expectThat(uri.path, Equals(b"/%s" % path))
        self.expectThat(uri.port, Equals(port))

    def test_parses_URL_with_IPv4_address(self):
        ip = factory.make_ipv4_address().encode("ascii")
        path = factory.make_name("path").encode("ascii")
        uri = get_patched_URI().fromBytes(b"http://%s/%s" % (ip, path))
        self.expectThat(uri.host, Equals(ip))
        self.expectThat(uri.path, Equals(b"/%s" % path))
        self.expectThat(uri.port, Equals(80))

    def test_parses_URL_with_IPv4_address_and_port(self):
        ip = factory.make_ipv4_address().encode("ascii")
        port = factory.pick_port()
        path = factory.make_name("path").encode("ascii")
        uri = get_patched_URI().fromBytes(
            b"http://%s:%d/%s" % (ip, port, path)
        )
        self.expectThat(uri.host, Equals(ip))
        self.expectThat(uri.path, Equals(b"/%s" % path))
        self.expectThat(uri.port, Equals(port))

    def test_parses_URL_with_IPv6_address(self):
        ip = factory.make_ipv6_address().encode("ascii")
        path = factory.make_name("path").encode("ascii")
        uri = get_patched_URI().fromBytes(b"http://[%s]/%s" % (ip, path))
        self.expectThat(uri.host, Equals(b"%s" % ip))
        self.expectThat(uri.path, Equals(b"/%s" % path))
        self.expectThat(uri.port, Equals(80))

    def test_parses_URL_with_IPv6_address_and_port(self):
        ip = factory.make_ipv6_address().encode("ascii")
        port = factory.pick_port()
        path = factory.make_name("path").encode("ascii")
        uri = get_patched_URI().fromBytes(
            b"http://[%s]:%d/%s" % (ip, port, path)
        )
        self.expectThat(uri.host, Equals(b"%s" % ip))
        self.expectThat(uri.path, Equals(b"/%s" % path))
        self.expectThat(uri.port, Equals(port))
