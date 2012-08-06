# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the server_address module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from django.conf import settings
from maasserver import server_address
from maasserver.server_address import get_maas_facing_server_address
from maastesting.factory import factory
from maastesting.fakemethod import FakeMethod
from maastesting.testcase import TestCase
from netaddr import IPNetwork


class TestServerAddress(TestCase):

    def make_hostname(self):
        return '%s.example.com' % factory.make_name('host').lower()

    def set_DEFAULT_MAAS_URL(self, hostname=None, with_port=False):
        """Patch DEFAULT_MAAS_URL to be a (partly) random URL."""
        if hostname is None:
            hostname = self.make_hostname()
        if with_port:
            location = "%s:%d" % (hostname, factory.getRandomPort())
        else:
            location = hostname
        url = 'http://%s/%s' % (location, factory.make_name("path"))
        self.patch(settings, 'DEFAULT_MAAS_URL', url)

    def test_get_maas_facing_server_host_returns_host_name(self):
        hostname = self.make_hostname()
        self.set_DEFAULT_MAAS_URL(hostname)
        self.assertEqual(
            hostname, server_address.get_maas_facing_server_host())

    def test_get_maas_facing_server_host_returns_ip_if_ip_configured(self):
        ip = factory.getRandomIPAddress()
        self.set_DEFAULT_MAAS_URL(ip)
        self.assertEqual(ip, server_address.get_maas_facing_server_host())

    def test_get_maas_facing_server_host_strips_out_port(self):
        hostname = self.make_hostname()
        self.set_DEFAULT_MAAS_URL(hostname, with_port=True)
        self.assertEqual(
            hostname, server_address.get_maas_facing_server_host())

    def test_get_maas_facing_server_address_returns_IP(self):
        ip = factory.getRandomIPAddress()
        self.set_DEFAULT_MAAS_URL(hostname=ip)
        self.assertEqual(ip, get_maas_facing_server_address())

    def test_get_maas_facing_server_address_returns_local_IP(self):
        ip = factory.getRandomIPInNetwork(IPNetwork('127.0.0.0/8'))
        self.set_DEFAULT_MAAS_URL(hostname=ip)
        self.assertEqual(ip, get_maas_facing_server_address())

    def test_get_maas_facing_server_address_resolves_hostname(self):
        ip = factory.getRandomIPAddress()
        resolver = FakeMethod(result=ip)
        self.patch(server_address, 'gethostbyname', resolver)
        hostname = self.make_hostname()
        self.set_DEFAULT_MAAS_URL(hostname=hostname)
        self.assertEqual(
            (ip, [(hostname, )]),
            (get_maas_facing_server_address(), resolver.extract_args()))
