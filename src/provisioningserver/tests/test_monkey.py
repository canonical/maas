# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test monkey patches."""


from twisted.internet.defer import Deferred, inlineCallbacks
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

    @inlineCallbacks
    def test_functions_returning_Deferreds_from_threads_crash(self):
        with self.assertRaisesRegex(
            TypeError, "Synchronous call returned a Deferred:"
        ):
            yield deferToThread(Deferred)

    @inlineCallbacks
    def test_functions_returning_other_from_threads_are_okay(self):
        res = yield deferToThread(round, 12.34)
        self.assertEqual(res, 12)


class TestPatchedURI(MAASTestCase):
    def test_parses_URL_with_hostname(self):
        hostname = factory.make_name("host")
        path = factory.make_name("path")
        uri = get_patched_URI().fromBytes(
            f"http://{hostname}/{path}".encode("utf-8")
        )
        self.assertEqual(uri.host, hostname.encode("utf-8"))
        self.assertEqual(uri.path, f"/{path}".encode("utf-8"))
        self.assertEqual(uri.port, 80)

    def test_parses_URL_with_hostname_and_port(self):
        hostname = factory.make_name("host")
        port = factory.pick_port()
        path = factory.make_name("path")
        uri = get_patched_URI().fromBytes(
            f"http://{hostname}:{port}/{path}".encode("utf-8")
        )
        self.assertEqual(uri.host, hostname.encode("utf-8"))
        self.assertEqual(uri.path, f"/{path}".encode("utf-8"))
        self.assertEqual(uri.port, port)

    def test_parses_URL_with_IPv4_address(self):
        ip = factory.make_ipv4_address()
        path = factory.make_name("path").encode("ascii")
        uri = get_patched_URI().fromBytes(
            f"http://{ip}/{path}".encode("utf-8")
        )
        self.assertEqual(uri.host, ip.encode("utf-8"))
        self.assertEqual(uri.path, f"/{path}".encode("utf-8"))
        self.assertEqual(uri.port, 80)

    def test_parses_URL_with_IPv4_address_and_port(self):
        ip = factory.make_ipv4_address()
        port = factory.pick_port()
        path = factory.make_name("path")
        uri = get_patched_URI().fromBytes(
            f"http://{ip}:{port}/{path}".encode("utf-8")
        )
        self.assertEqual(uri.host, ip.encode("utf-8"))
        self.assertEqual(uri.path, f"/{path}".encode("utf-8"))
        self.assertEqual(uri.port, port)

    def test_parses_URL_with_IPv6_address(self):
        ip = factory.make_ipv6_address()
        path = factory.make_name("path")
        uri = get_patched_URI().fromBytes(f"http://[{ip}]/{path}".encode())
        self.assertEqual(uri.host, ip.encode("utf-8"))
        self.assertEqual(uri.path, f"/{path}".encode("utf-8"))
        self.assertEqual(uri.port, 80)

    def test_parses_URL_with_IPv6_address_and_port(self):
        ip = factory.make_ipv6_address()
        port = factory.pick_port()
        path = factory.make_name("path")
        uri = get_patched_URI().fromBytes(
            f"http://[{ip}]:{port}/{path}".encode()
        )
        self.assertEqual(uri.host, ip.encode("utf-8"))
        self.assertEqual(uri.path, f"/{path}".encode("utf-8"))
        self.assertEqual(uri.port, port)
