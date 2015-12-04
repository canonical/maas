# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test utilities for URL handling."""

__all__ = []

from random import randint

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.utils.url import compose_URL


class TestComposeURL(MAASTestCase):

    def make_path(self):
        """Return an arbitrary URL path part."""
        return '%s/%s' % (factory.make_name('root'), factory.make_name('sub'))

    def make_network_interface(self):
        return 'eth%d' % randint(0, 100)

    def test__inserts_IPv4(self):
        ip = factory.make_ipv4_address()
        path = self.make_path()
        self.assertEqual(
            'http://%s/%s' % (ip, path),
            compose_URL('http:///%s' % path, ip))

    def test__inserts_IPv6_with_brackets(self):
        ip = factory.make_ipv6_address()
        path = self.make_path()
        self.assertEqual(
            'http://[%s]/%s' % (ip, path),
            compose_URL('http:///%s' % path, ip))

    def test__escapes_IPv6_zone_index(self):
        ip = factory.make_ipv6_address()
        zone = self.make_network_interface()
        hostname = '%s%%%s' % (ip, zone)
        path = self.make_path()
        self.assertEqual(
            'http://[%s%%25%s]/%s' % (ip, zone, path),
            compose_URL('http:///%s' % path, hostname))

    def test__inserts_bracketed_IPv6_unchanged(self):
        ip = factory.make_ipv6_address()
        hostname = '[%s]' % ip
        path = self.make_path()
        self.assertEqual(
            'http://%s/%s' % (hostname, path),
            compose_URL('http:///%s' % path, hostname))

    def test__does_not_escape_bracketed_IPv6_zone_index(self):
        ip = factory.make_ipv6_address()
        zone = self.make_network_interface()
        path = self.make_path()
        hostname = '[%s%%25%s]' % (ip, zone)
        self.assertEqual(
            'http://%s/%s' % (hostname, path),
            compose_URL('http:///%s' % path, hostname))

    def test__inserts_hostname(self):
        hostname = factory.make_name('host')
        path = self.make_path()
        self.assertEqual(
            'http://%s/%s' % (hostname, path),
            compose_URL('http:///%s' % path, hostname))

    def test__preserves_query(self):
        ip = factory.make_ipv4_address()
        key = factory.make_name('key')
        value = factory.make_name('value')
        self.assertEqual(
            'https://%s?%s=%s' % (ip, key, value),
            compose_URL('https://?%s=%s' % (key, value), ip))

    def test__preserves_port_with_IPv4(self):
        ip = factory.make_ipv4_address()
        port = factory.pick_port()
        self.assertEqual(
            'https://%s:%s/' % (ip, port),
            compose_URL('https://:%s/' % port, ip))

    def test__preserves_port_with_IPv6(self):
        ip = factory.make_ipv6_address()
        port = factory.pick_port()
        self.assertEqual(
            'https://[%s]:%s/' % (ip, port),
            compose_URL('https://:%s/' % port, ip))

    def test__preserves_port_with_hostname(self):
        hostname = factory.make_name('host')
        port = factory.pick_port()
        self.assertEqual(
            'https://%s:%s/' % (hostname, port),
            compose_URL('https://:%s/' % port, hostname))
