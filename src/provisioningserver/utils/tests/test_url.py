# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test utilities for URL handling."""


from random import randint

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.utils.url import compose_URL, get_domain, splithost


class TestComposeURL(MAASTestCase):
    def make_path(self):
        """Return an arbitrary URL path part."""
        return "{}/{}".format(
            factory.make_name("root"), factory.make_name("sub")
        )

    def make_network_interface(self):
        return "eth%d" % randint(0, 100)

    def test_inserts_IPv4(self):
        ip = factory.make_ipv4_address()
        path = self.make_path()
        self.assertEqual(
            f"http://{ip}/{path}", compose_URL("http:///%s" % path, ip)
        )

    def test_inserts_IPv6_with_brackets(self):
        ip = factory.make_ipv6_address()
        path = self.make_path()
        self.assertEqual(
            f"http://[{ip}]/{path}", compose_URL("http:///%s" % path, ip)
        )

    def test_escapes_IPv6_zone_index(self):
        ip = factory.make_ipv6_address()
        zone = self.make_network_interface()
        hostname = f"{ip}%{zone}"
        path = self.make_path()
        self.assertEqual(
            f"http://[{ip}%25{zone}]/{path}",
            compose_URL("http:///%s" % path, hostname),
        )

    def test_inserts_bracketed_IPv6_unchanged(self):
        ip = factory.make_ipv6_address()
        hostname = "[%s]" % ip
        path = self.make_path()
        self.assertEqual(
            f"http://{hostname}/{path}",
            compose_URL("http:///%s" % path, hostname),
        )

    def test_does_not_escape_bracketed_IPv6_zone_index(self):
        ip = factory.make_ipv6_address()
        zone = self.make_network_interface()
        path = self.make_path()
        hostname = f"[{ip}%25{zone}]"
        self.assertEqual(
            f"http://{hostname}/{path}",
            compose_URL("http:///%s" % path, hostname),
        )

    def test_inserts_hostname(self):
        hostname = factory.make_name("host")
        path = self.make_path()
        self.assertEqual(
            f"http://{hostname}/{path}",
            compose_URL("http:///%s" % path, hostname),
        )

    def test_preserves_query(self):
        ip = factory.make_ipv4_address()
        key = factory.make_name("key")
        value = factory.make_name("value")
        self.assertEqual(
            f"https://{ip}?{key}={value}",
            compose_URL(f"https://?{key}={value}", ip),
        )

    def test_preserves_port_with_IPv4(self):
        ip = factory.make_ipv4_address()
        port = factory.pick_port()
        self.assertEqual(
            f"https://{ip}:{port}/",
            compose_URL("https://:%s/" % port, ip),
        )

    def test_preserves_port_with_IPv6(self):
        ip = factory.make_ipv6_address()
        port = factory.pick_port()
        self.assertEqual(
            f"https://[{ip}]:{port}/",
            compose_URL("https://:%s/" % port, ip),
        )

    def test_preserves_port_with_hostname(self):
        hostname = factory.make_name("host")
        port = factory.pick_port()
        self.assertEqual(
            f"https://{hostname}:{port}/",
            compose_URL("https://:%s/" % port, hostname),
        )


class TestSplithost(MAASTestCase):
    scenarios = (
        ("ipv4", {"host": "192.168.1.1:21", "result": ("192.168.1.1", 21)}),
        ("ipv6", {"host": "[::f]:21", "result": ("[::f]", 21)}),
        (
            "ipv4_no_port",
            {"host": "192.168.1.1", "result": ("192.168.1.1", None)},
        ),
        ("ipv6_no_port", {"host": "[::f]", "result": ("[::f]", None)}),
        ("ipv6_no_bracket", {"host": "::ffff", "result": ("[::ffff]", None)}),
    )

    def test_result(self):
        self.assertEqual(self.result, splithost(self.host))


class TestGetDomain(MAASTestCase):
    def test_get_domain(self):
        domain = factory.make_hostname()
        url = "%s://%s:%d/%s/%s/%s" % (
            factory.make_name("proto"),
            domain,
            randint(1, 65535),
            factory.make_name(),
            factory.make_name(),
            factory.make_name(),
        )
        self.assertEqual(domain, get_domain(url))

    def test_get_domain_fqdn(self):
        domain = factory.make_hostname()
        url = "%s://%s.example.com:%d/%s/%s/%s" % (
            factory.make_name("proto"),
            domain,
            randint(1, 65535),
            factory.make_name(),
            factory.make_name(),
            factory.make_name(),
        )
        self.assertEqual("%s.example.com" % domain, get_domain(url))
