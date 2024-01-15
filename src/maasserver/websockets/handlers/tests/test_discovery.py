# Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.discovery`"""


from datetime import datetime, timedelta
import time

from maasserver.models import MDNS
from maasserver.models.discovery import Discovery
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.base import (
    dehydrate_datetime,
    HandlerPermissionError,
)
from maasserver.websockets.handlers.discovery import DiscoveryHandler


class TestDiscoveryHandler(MAASServerTestCase):
    def dehydrate_discovery(self, discovery: Discovery, for_list=False):
        data = {
            "discovery_id": discovery.discovery_id,
            "fabric": discovery.fabric_id,
            "fabric_name": discovery.fabric_name,
            "hostname": discovery.hostname,
            "id": discovery.id,
            "ip": discovery.ip,
            "is_external_dhcp": discovery.is_external_dhcp,
            "mdns": discovery.mdns_id,
            "mac_address": discovery.mac_address,
            "mac_organization": discovery.mac_organization,
            "neighbour": discovery.neighbour_id,
            "observer": discovery.observer_id,
            "observer_hostname": discovery.observer_hostname,
            "observer_interface": discovery.observer_interface_id,
            "observer_interface_name": discovery.observer_interface_name,
            "observer_system_id": discovery.observer_system_id,
            "subnet": discovery.subnet_id,
            "subnet_cidr": discovery.subnet_cidr,
            "vid": discovery.vid,
            "vlan": discovery.vlan_id,
            "first_seen": str(
                time.mktime(discovery.first_seen.timetuple())
                + discovery.first_seen.microsecond / 1e6
            ),
            "last_seen": dehydrate_datetime(discovery.last_seen),
        }
        return data

    def test_get(self):
        user = factory.make_User()
        handler = DiscoveryHandler(user, {}, None)
        discovery = factory.make_Discovery()
        self.assertEqual(
            self.dehydrate_discovery(discovery),
            handler.get({"discovery_id": discovery.discovery_id}),
        )

    def test_list(self):
        user = factory.make_User()
        handler = DiscoveryHandler(user, {}, None)
        factory.make_Discovery()
        factory.make_Discovery()
        expected_discoveries = [
            self.dehydrate_discovery(discovery, for_list=True)
            for discovery in Discovery.objects.all()
        ]
        self.assertCountEqual(expected_discoveries, handler.list({}))

    def test_list_orders_by_creation_date(self):
        user = factory.make_User()
        handler = DiscoveryHandler(user, {}, None)
        now = datetime.now()
        d0 = factory.make_Discovery(created=now)
        d4 = factory.make_Discovery(created=(now + timedelta(days=4)))
        d3 = factory.make_Discovery(created=(now + timedelta(days=3)))
        d1 = factory.make_Discovery(created=(now + timedelta(days=1)))
        d2 = factory.make_Discovery(created=(now + timedelta(days=2)))
        # Test for the expected order independent of how the database
        # decided to sort.
        expected_discoveries = [
            self.dehydrate_discovery(discovery, for_list=True)
            for discovery in [d0, d1, d2, d3, d4]
        ]
        self.assertEqual(expected_discoveries, handler.list({}))

    def test_list_starts_after_first_seen(self):
        user = factory.make_User()
        handler = DiscoveryHandler(user, {}, None)
        now = datetime.now()
        factory.make_Discovery(created=now)
        d4 = factory.make_Discovery(created=(now + timedelta(days=4)))
        d3 = factory.make_Discovery(created=(now + timedelta(days=3)))
        factory.make_Discovery(created=(now + timedelta(days=1)))
        factory.make_Discovery(created=(now + timedelta(days=2)))
        first_seen = now + timedelta(days=2)
        first_seen = str(
            time.mktime(first_seen.timetuple()) + first_seen.microsecond / 1e6
        )
        # Test for the expected order independent of how the database
        # decided to sort.
        expected_discoveries = [
            self.dehydrate_discovery(discovery, for_list=True)
            for discovery in [d3, d4]
        ]
        self.assertEqual(
            expected_discoveries, handler.list({"start": first_seen})
        )


class TestDiscoveryHandlerClear(MAASServerTestCase):
    def test_raises_if_not_admin(self):
        user = factory.make_User()
        handler = DiscoveryHandler(user, {}, None)
        factory.make_Discovery()
        num_discoveries = Discovery.objects.count()
        self.assertEqual(1, num_discoveries)
        self.assertRaises(HandlerPermissionError, handler.clear)

    def test_clears_all_by_default(self):
        user = factory.make_admin()
        handler = DiscoveryHandler(user, {}, None)
        factory.make_Discovery()
        num_discoveries = Discovery.objects.count()
        self.assertEqual(1, num_discoveries)
        handler.clear()
        num_discoveries = Discovery.objects.count()
        self.assertEqual(0, num_discoveries)

    def test_clears_mdns_only_upon_request(self):
        user = factory.make_admin()
        handler = DiscoveryHandler(user, {}, None)
        factory.make_Discovery(hostname="useful-towel")
        num_discoveries = Discovery.objects.count()
        num_mdns = MDNS.objects.count()
        self.assertEqual(1, num_discoveries)
        self.assertEqual(1, num_mdns)
        handler.clear({"mdns": True})
        num_discoveries = Discovery.objects.count()
        num_mdns = MDNS.objects.count()
        self.assertEqual(1, num_discoveries)
        self.assertEqual(0, num_mdns)


class TestDiscoveryHandlerDeleteByMACAndIP(MAASServerTestCase):
    def test_raises_if_not_admin(self):
        user = factory.make_User()
        handler = DiscoveryHandler(user, {}, None)
        disco = factory.make_Discovery()
        num_discoveries = Discovery.objects.count()
        self.assertEqual(1, num_discoveries)
        self.assertRaises(
            HandlerPermissionError,
            handler.delete_by_mac_and_ip,
            dict(ip=disco.ip, mac=disco.mac_address),
        )

    def test_raises_if_missing_ip(self):
        user = factory.make_User()
        handler = DiscoveryHandler(user, {}, None)
        disco = factory.make_Discovery()
        num_discoveries = Discovery.objects.count()
        self.assertEqual(1, num_discoveries)
        self.assertRaises(
            HandlerPermissionError,
            handler.delete_by_mac_and_ip,
            dict(mac=disco.mac_address),
        )

    def test_raises_if_missing_mac(self):
        user = factory.make_User()
        handler = DiscoveryHandler(user, {}, None)
        disco = factory.make_Discovery()
        num_discoveries = Discovery.objects.count()
        self.assertEqual(1, num_discoveries)
        self.assertRaises(
            HandlerPermissionError,
            handler.delete_by_mac_and_ip,
            dict(ip=disco.ip),
        )

    def test_deletes_discovery_and_returns_number_deleted(self):
        user = factory.make_admin()
        handler = DiscoveryHandler(user, {}, None)
        disco = factory.make_Discovery()
        num_discoveries = Discovery.objects.count()
        self.assertEqual(1, num_discoveries)
        result = handler.delete_by_mac_and_ip(
            dict(ip=disco.ip, mac=disco.mac_address)
        )
        num_discoveries = Discovery.objects.count()
        self.assertEqual(0, num_discoveries)
        self.assertEqual(1, result)
