# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.discovery`"""

__all__ = []

from maasserver.dbviews import register_view
from maasserver.models.discovery import Discovery
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.base import dehydrate_datetime
from maasserver.websockets.handlers.discovery import DiscoveryHandler


class TestDiscoveryHandler(MAASServerTestCase):

    def setUp(self):
        super().setUp()
        register_view("maasserver_discovery")

    def dehydrate_discovery(self, discovery, for_list=False):
        data = {
            "discovery_id": discovery.discovery_id,
            "fabric": discovery.fabric_id,
            "fabric_name": discovery.fabric_name,
            "hostname": discovery.hostname,
            "id": discovery.id,
            "ip": discovery.ip,
            "mdns": discovery.mdns_id,
            "mac_address": discovery.mac_address,
            "mac_organization": discovery.mac_organization,
            "neighbour": discovery.neighbour_id,
            "observer": discovery.observer_id,
            "observer_hostname": discovery.observer_hostname,
            "observer_interface": discovery.observer_interface_id,
            "observer_interface_name": discovery.observer_interface_name,
            "observer_system_id": discovery.observer_system_id,
            "vid": discovery.vid,
            "vlan": discovery.vlan_id,
            "last_seen": dehydrate_datetime(discovery.last_seen)
        }
        return data

    def test_get(self):
        user = factory.make_User()
        handler = DiscoveryHandler(user, {})
        discovery = factory.make_Discovery()
        self.assertEqual(
            self.dehydrate_discovery(discovery),
            handler.get({"discovery_id": discovery.discovery_id}))

    def test_list(self):
        user = factory.make_User()
        handler = DiscoveryHandler(user, {})
        factory.make_Discovery()
        factory.make_Discovery()
        expected_discoveries = [
            self.dehydrate_discovery(discovery, for_list=True)
            for discovery in Discovery.objects.all()
            ]
        self.assertItemsEqual(
            expected_discoveries,
            handler.list({}))
