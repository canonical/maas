# Copyright 2016-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from django.utils import timezone

from maasserver.enum import IPADDRESS_TYPE
from maasserver.models import DNSPublication
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import post_commit_hooks

"""
Test the behaviour of staticipaddress signals.

Tests for sharing IP addresses between BMCs and machines are in:
    src/maasserver/models/tests/test_bmc.py

Tests related to DNS resources are in:
    src/maasserver/models/tests/test_dnsresource.py
"""


class TestUpdateStaticIPAddressSignal(MAASServerTestCase):
    def test_update_staticipaddress_creates_dnspublication_if_domain_authoritative(
        self,
    ):
        domain = factory.make_Domain("example.com", authoritative=True)
        node = factory.make_Node(domain=domain, interface=True)
        static_ip = factory.make_StaticIPAddress(
            interface=node.get_boot_interface(),
            ip="192.168.1.1",
            alloc_type=IPADDRESS_TYPE.STICKY,
        )
        static_ip.ip = "192.168.1.2"
        static_ip.temp_expires_on = timezone.now()
        static_ip.alloc_type = IPADDRESS_TYPE.USER_RESERVED
        with post_commit_hooks:
            static_ip.save()

        dnspublication = DNSPublication.objects.get_most_recent()
        self.assertIn(
            "ip 192.168.1.1 changed to 192.168.1.2", dnspublication.source
        )
        self.assertIn("temp_expires_on changed to", dnspublication.source)
        self.assertIn("alloc_type changed to", dnspublication.source)

    def test_update_staticipaddress_does_not_create_dnspublication_if_domain_is_not_authoritative(
        self,
    ):
        domain = factory.make_Domain("example.com", authoritative=False)
        node = factory.make_Node(domain=domain, interface=True)
        static_ip = factory.make_StaticIPAddress(
            interface=node.get_boot_interface(),
            ip="192.168.1.1",
            alloc_type=IPADDRESS_TYPE.STICKY,
        )
        static_ip.ip = "192.168.1.2"
        with post_commit_hooks:
            static_ip.save()

        dnspublication = DNSPublication.objects.get_most_recent()
        self.assertNotIn(
            "ip 192.168.1.1 changed to 192.168.1.2", dnspublication.source
        )
