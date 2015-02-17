# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for devices API."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import httplib
import json
import random

from django.core.urlresolvers import reverse
from maasserver.api import devices as api_devices
from maasserver.enum import (
    IPADDRESS_TYPE,
    NODE_STATUS,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.models import (
    Node,
    node as node_module,
    StaticIPAddress,
    )
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maastesting.matchers import MockCalledOnceWith


class TestDevicesAPI(APITestCase):

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/devices/', reverse('devices_handler'))

    def test_new_creates_device(self):
        cluster = factory.make_NodeGroup()
        hostname = factory.make_name('host')
        macs = {
            factory.make_mac_address()
            for _ in range(random.randint(1, 2))
            }
        response = self.client.post(
            reverse('devices_handler'),
            {
                'op': 'new',
                'nodegroup': cluster.id,
                'hostname': hostname,
                'mac_addresses': macs,
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        system_id = json.loads(response.content)['system_id']
        device = Node.devices.get(system_id=system_id)
        self.assertEquals(hostname, device.hostname)
        self.assertFalse(device.installable)
        self.assertEquals(self.logged_in_user, device.owner)
        self.assertEquals(
            macs,
            {mac.mac_address for mac in device.macaddress_set.all()})

    def create_devices(self, owner, nodegroup=None, nb=3):
        return [
            factory.make_Node(
                nodegroup=nodegroup, mac=True, installable=False,
                owner=owner)
            for _ in range(nb)
        ]

    def test_list_lists_devices(self):
        # The api allows for fetching the list of devices.
        devices = self.create_devices(owner=self.logged_in_user)
        factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.logged_in_user)
        response = self.client.get(reverse('devices_handler'), {'op': 'list'})
        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.OK, response.status_code)
        self.assertItemsEqual(
            [device.system_id for device in devices],
            [device.get('system_id') for device in parsed_result])

    def test_list_ignores_nodes(self):
        factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.logged_in_user)
        response = self.client.get(reverse('devices_handler'), {'op': 'list'})
        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.OK, response.status_code)
        self.assertEquals(
            [],
            [device.get('system_id') for device in parsed_result])

    def test_list_with_id_returns_matching_devices(self):
        # The "list" operation takes optional "id" parameters.  Only
        # devices with matching ids will be returned.
        devices = self.create_devices(owner=self.logged_in_user)
        ids = [device.system_id for device in devices]
        matching_id = ids[0]
        response = self.client.get(reverse('devices_handler'), {
            'op': 'list',
            'id': [matching_id],
        })
        parsed_result = json.loads(response.content)
        self.assertItemsEqual(
            [matching_id],
            [device.get('system_id') for device in parsed_result])


def get_device_uri(device):
    """Return a device's URI on the API."""
    return reverse('device_handler', args=[device.system_id])


class TestDeviceAPI(APITestCase):

    def test_handler_path(self):
        system_id = factory.make_name('system-id')
        self.assertEqual(
            '/api/1.0/devices/%s/' % system_id,
            reverse('device_handler', args=[system_id]))

    def test_GET_reads_device(self):
        device = factory.make_Node(
            installable=False, owner=self.logged_in_user)

        response = self.client.get(get_device_uri(device))
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_device = json.loads(response.content)
        self.assertEqual(device.system_id, parsed_device["system_id"])

    def test_PUT_updates_device_hostname(self):
        device = factory.make_Node(
            installable=False, owner=self.logged_in_user)
        new_hostname = factory.make_name('hostname')

        response = self.client_put(
            get_device_uri(device), {'hostname': new_hostname})
        self.assertEqual(httplib.OK, response.status_code, response.content)

        device = reload_object(device)
        self.assertEqual(new_hostname, device.hostname)

    def test_PUT_updates_device_parent(self):
        parent = factory.make_Node()
        device = factory.make_Node(
            installable=False, owner=self.logged_in_user, parent=parent)
        new_parent = factory.make_Node()

        response = self.client_put(
            get_device_uri(device), {'parent': new_parent.system_id})
        self.assertEqual(httplib.OK, response.status_code, response.content)

        device = reload_object(device)
        self.assertEqual(new_parent, device.parent)

    def test_PUT_rejects_edit_if_not_permitted(self):
        device = factory.make_Node(
            installable=False, owner=factory.make_User())
        old_hostname = device.hostname

        response = self.client_put(
            get_device_uri(device),
            {'hostname': factory.make_name('hostname')})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)
        self.assertEquals(old_hostname, reload_object(device).hostname)

    def test_DELETE_removes_device(self):
        device = factory.make_Node(
            installable=False, owner=self.logged_in_user)
        response = self.client.delete(get_device_uri(device))
        self.assertEqual(
            httplib.NO_CONTENT, response.status_code, response.content)
        self.assertIsNone(reload_object(device))

    def test_DELETE_rejects_deletion_if_not_permitted(self):
        device = factory.make_Node(
            installable=False, owner=factory.make_User())
        response = self.client.delete(get_device_uri(device))
        self.assertEqual(httplib.FORBIDDEN, response.status_code)
        self.assertEquals(device, reload_object(device))

    def test_claim_ip_address_claims_ip_address(self):
        parent = factory.make_node_with_mac_attached_to_nodegroupinterface()
        device = factory.make_Node(
            installable=False, parent=parent, mac=True, disable_ipv4=False,
            owner=self.logged_in_user)
        # Silence 'update_host_maps'.
        self.patch(node_module, "update_host_maps")
        response = self.client.post(
            get_device_uri(device), {'op': 'claim_sticky_ip_address'})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_device = json.loads(response.content)
        [returned_ip] = parsed_device["ip_addresses"]
        [given_ip] = StaticIPAddress.objects.all()
        self.assertEqual(
            (given_ip.ip, IPADDRESS_TYPE.STICKY),
            (returned_ip, given_ip.alloc_type)
            )

    def test_claim_ip_address_creates_host_DHCP_and_DNS_mappings(self):
        parent = factory.make_node_with_mac_attached_to_nodegroupinterface(
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        device = factory.make_Node(
            installable=False, parent=parent, mac=True, disable_ipv4=False,
            owner=self.logged_in_user, nodegroup=parent.nodegroup)
        dns_update_zones = self.patch(api_devices, 'dns_update_zones')
        update_host_maps = self.patch(node_module, "update_host_maps")
        update_host_maps.return_value = []  # No failures.
        response = self.client.post(
            get_device_uri(device), {'op': 'claim_sticky_ip_address'})
        self.assertEqual(httplib.OK, response.status_code, response.content)

        self.assertItemsEqual(
            [device.get_primary_mac()],
            device.mac_addresses_on_managed_interfaces())
        # Host maps are updated.
        self.assertThat(
            update_host_maps, MockCalledOnceWith({
                device.nodegroup: {
                    ip_address.ip: mac.mac_address
                    for ip_address in mac.ip_addresses.all()
                }
                for mac in device.mac_addresses_on_managed_interfaces()
            }))
        # DNS has been updated.
        self.assertThat(
            dns_update_zones, MockCalledOnceWith([device.nodegroup]))

    def test_claim_ip_address_rejected_if_not_permitted(self):
        parent = factory.make_node_with_mac_attached_to_nodegroupinterface()
        device = factory.make_Node(
            installable=False, parent=parent, mac=True, disable_ipv4=False,
            owner=factory.make_User())
        self.patch(node_module, "update_host_maps")
        response = self.client.post(
            get_device_uri(device), {'op': 'claim_sticky_ip_address'})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)
        self.assertItemsEqual([], StaticIPAddress.objects.all())

    def test_connect_mac_to_cluster_interface_connects_mac(self):
        cluster = factory.make_NodeGroup(status=NODEGROUP_STATUS.ACCEPTED)
        interface = factory.make_NodeGroupInterface(
            cluster, network=None,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        device = factory.make_Node(
            installable=False, mac=True, disable_ipv4=False,
            owner=self.logged_in_user)
        mac = device.macaddress_set.all()[0]
        response = self.client.post(
            get_device_uri(device),
            {
                'op': 'connect_mac_to_cluster_interface',
                'mac_address': (
                    mac.mac_address.get_raw()),
                'cluster_uuid': cluster.uuid,
                'cluster_interface': interface.name,
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        self.assertEqual(interface, reload_object(mac).cluster_interface)

    def test_connect_mac_to_cluster_interface_checks_permission(self):
        cluster = factory.make_NodeGroup(status=NODEGROUP_STATUS.ACCEPTED)
        interface = factory.make_NodeGroupInterface(
            cluster, network=None,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        device = factory.make_Node(
            installable=False, mac=True, disable_ipv4=False,
            owner=factory.make_User())
        mac = device.macaddress_set.all()[0]
        response = self.client.post(
            get_device_uri(device),
            {
                'op': 'connect_mac_to_cluster_interface',
                'mac_address': (
                    mac.mac_address.get_raw()),
                'cluster_uuid': cluster.uuid,
                'cluster_interface': interface.name,
            })
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_connect_mac_to_cluster_interface_rejects_unknown_mac(self):
        cluster = factory.make_NodeGroup(status=NODEGROUP_STATUS.ACCEPTED)
        interface = factory.make_NodeGroupInterface(
            cluster, network=None,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        device = factory.make_Node(
            installable=False, mac=True, disable_ipv4=False,
            owner=self.logged_in_user)
        response = self.client.post(
            get_device_uri(device),
            {
                'op': 'connect_mac_to_cluster_interface',
                'mac_address': (
                    factory.make_MAC()),
                'cluster_uuid': cluster.uuid,
                'cluster_interface': interface.name,
            })
        self.assertEqual(
            httplib.BAD_REQUEST, response.status_code, response.content)
