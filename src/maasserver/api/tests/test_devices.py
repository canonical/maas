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

from collections import defaultdict
import httplib
import json
import random

from django.core.urlresolvers import reverse
from django.db import transaction
from maasserver.dns import config as dns_config
from maasserver.enum import (
    IPADDRESS_TYPE,
    NODE_STATUS,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
)
from maasserver.models import (
    MACAddress,
    Node,
    node as node_module,
    NodeGroup,
    StaticIPAddress,
)
from maasserver.testing.api import (
    APITestCase,
    APITransactionTestCase,
)
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maastesting.matchers import MockCalledOnceWith
from testtools.matchers import (
    HasLength,
    Not,
)


class TestDevicesAPI(APITestCase):

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/devices/', reverse('devices_handler'))

    def test_new_creates_device(self):
        hostname = factory.make_name('host')
        macs = {
            factory.make_mac_address()
            for _ in range(random.randint(1, 2))
        }
        response = self.client.post(
            reverse('devices_handler'),
            {
                'op': 'new',
                'hostname': hostname,
                'mac_addresses': macs,
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        system_id = json.loads(response.content)['system_id']
        device = Node.devices.get(system_id=system_id)
        self.assertEquals(hostname, device.hostname)
        self.assertIsNone(device.parent)
        self.assertFalse(device.installable)
        self.assertEquals(NodeGroup.objects.ensure_master(), device.nodegroup)
        self.assertEquals(self.logged_in_user, device.owner)
        self.assertEquals(
            macs,
            {mac.mac_address for mac in device.macaddress_set.all()})

    def test_new_creates_device_with_parent(self):
        parent = factory.make_Node()
        hostname = factory.make_name('host')
        macs = {
            factory.make_mac_address()
            for _ in range(random.randint(1, 2))
        }
        response = self.client.post(
            reverse('devices_handler'),
            {
                'op': 'new',
                'hostname': hostname,
                'mac_addresses': macs,
                'parent': parent.system_id,
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        system_id = json.loads(response.content)['system_id']
        device = Node.devices.get(system_id=system_id)
        self.assertEquals(hostname, device.hostname)
        self.assertEquals(parent, device.parent)
        self.assertFalse(device.installable)

    def test_POST_returns_limited_fields(self):
        response = self.client.post(
            reverse('devices_handler'),
            {
                'op': 'new',
                'hostname': factory.make_string(),
                'mac_addresses': ['aa:bb:cc:dd:ee:ff'],
            })
        parsed_result = json.loads(response.content)
        self.assertItemsEqual(
            [
                'hostname',
                'owner',
                'system_id',
                'macaddress_set',
                'parent',
                'tag_names',
                'ip_addresses',
                'resource_uri',
                'zone',
            ],
            list(parsed_result))

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

    def test_list_returns_limited_fields(self):
        self.create_devices(owner=self.logged_in_user)
        response = self.client.get(reverse('devices_handler'), {'op': 'list'})
        parsed_result = json.loads(response.content)
        self.assertItemsEqual(
            [
                'hostname',
                'owner',
                'system_id',
                'macaddress_set',
                'parent',
                'tag_names',
                'ip_addresses',
                'resource_uri',
                'zone',
            ],
            list(parsed_result[0]))


def get_device_uri(device):
    """Return a device's URI on the API."""
    return reverse('device_handler', args=[device.system_id])


class TestDeviceAPI(APITestCase):

    def test_handler_path(self):
        system_id = factory.make_name('system-id')
        self.assertEqual(
            '/api/1.0/devices/%s/' % system_id,
            reverse('device_handler', args=[system_id]))

    def test_POST_method_doesnt_exist(self):
        device = factory.make_Node(
            installable=False, owner=self.logged_in_user)

        response = self.client.post(get_device_uri(device))
        self.assertEqual(
            httplib.BAD_REQUEST, response.status_code, response.content)

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

        response = self.client.put(
            get_device_uri(device), {'hostname': new_hostname})
        self.assertEqual(httplib.OK, response.status_code, response.content)

        device = reload_object(device)
        self.assertEqual(new_hostname, device.hostname)

    def test_PUT_updates_device_parent(self):
        parent = factory.make_Node()
        device = factory.make_Node(
            installable=False, owner=self.logged_in_user, parent=parent)
        new_parent = factory.make_Node()

        response = self.client.put(
            get_device_uri(device), {'parent': new_parent.system_id})
        self.assertEqual(httplib.OK, response.status_code, response.content)

        device = reload_object(device)
        self.assertEqual(new_parent, device.parent)

    def test_PUT_rejects_edit_if_not_permitted(self):
        device = factory.make_Node(
            installable=False, owner=factory.make_User())
        old_hostname = device.hostname

        response = self.client.put(
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


class TestClaimStickyIpAddressAPI(APITestCase):
    """Tests for /api/1.0/devices/?op=claim_sticky_ip_address."""

    def test__claims_ip_address_from_cluster_interface(self):
        parent = factory.make_Node_with_MACAddress_and_NodeGroupInterface()
        device = factory.make_Node(
            installable=False, parent=parent, mac=True, disable_ipv4=False,
            owner=self.logged_in_user)
        # Silence 'update_host_maps'.
        self.patch(Node.update_host_maps)
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

    def test__creates_host_DHCP_and_DNS_mappings_with_implicit_ip(self):
        parent = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        device = factory.make_Node(
            installable=False, parent=parent, mac=True, disable_ipv4=False,
            owner=self.logged_in_user, nodegroup=parent.nodegroup)
        dns_update_zones = self.patch(dns_config.dns_update_zones)
        update_host_maps = self.patch(Node.update_host_maps)
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

    def test__rejected_if_not_permitted(self):
        parent = factory.make_Node_with_MACAddress_and_NodeGroupInterface()
        device = factory.make_Node(
            installable=False, parent=parent, mac=True, disable_ipv4=False,
            owner=factory.make_User())
        self.patch(Node.update_host_maps)
        response = self.client.post(
            get_device_uri(device), {'op': 'claim_sticky_ip_address'})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)
        self.assertItemsEqual([], StaticIPAddress.objects.all())

    def test_creates_ip_with_random_ip(self):
        requested_address = factory.make_ip_address()
        device = factory.make_Node(
            installable=False, mac=True, disable_ipv4=False,
            owner=self.logged_in_user)
        # Silence 'update_host_maps'.
        self.patch(Node.update_host_maps)
        response = self.client.post(
            get_device_uri(device),
            {
                'op': 'claim_sticky_ip_address',
                'requested_address': requested_address,
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_device = json.loads(response.content)
        [returned_ip] = parsed_device["ip_addresses"]
        [given_ip] = StaticIPAddress.objects.all()
        self.assertEqual(
            (given_ip.ip, requested_address, IPADDRESS_TYPE.STICKY),
            (returned_ip, returned_ip, given_ip.alloc_type)
        )
        self.assertItemsEqual(
            [device.get_primary_mac()], given_ip.macaddress_set.all())

    def test_creates_ip_for_specific_mac(self):
        requested_address = factory.make_ip_address()
        device = factory.make_Node(
            installable=False, mac=True, disable_ipv4=False,
            owner=self.logged_in_user)
        second_mac = factory.make_MACAddress(node=device)
        # Silence 'update_host_maps'.
        self.patch(Node.update_host_maps)
        response = self.client.post(
            get_device_uri(device),
            {
                'op': 'claim_sticky_ip_address',
                'requested_address': requested_address,
                'mac_address': second_mac.mac_address,
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_device = json.loads(response.content)
        [returned_ip] = parsed_device["ip_addresses"]
        [given_ip] = StaticIPAddress.objects.all()
        self.assertEqual(
            (given_ip.ip, requested_address, IPADDRESS_TYPE.STICKY),
            (returned_ip, returned_ip, given_ip.alloc_type)
        )
        self.assertItemsEqual([second_mac], given_ip.macaddress_set.all())

    def test_creates_host_DHCP_and_DNS_mappings_with_given_ip(self):
        dns_update_zones = self.patch(dns_config.dns_update_zones)
        update_host_maps = self.patch(Node.update_host_maps)
        # Create a nodegroup for which we manage DHCP.
        factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ENABLED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        # Create a nodegroup for which we don't manage DHCP.
        factory.make_NodeGroup(
            NODEGROUP_STATUS.ENABLED,
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        device = factory.make_Node(
            installable=False, mac=True, disable_ipv4=False,
            owner=self.logged_in_user)
        update_host_maps.return_value = []  # No failures.
        requested_address = factory.make_ip_address()
        response = self.client.post(
            get_device_uri(device),
            {
                'op': 'claim_sticky_ip_address',
                'requested_address': requested_address,
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)

        # Host maps are updated on all the clusters for which DHCP is managed.
        static_mappings = defaultdict(dict)
        dhcp_managed_clusters = [
            cluster for cluster in NodeGroup.objects.all()
            if cluster.manages_dhcp()
        ]
        for cluster in dhcp_managed_clusters:
            static_mappings[cluster] = {
                requested_address: device.get_primary_mac().mac_address
            }
        self.assertThat(
            update_host_maps, MockCalledOnceWith(static_mappings))
        # DNS has been updated.
        self.assertThat(
            dns_update_zones,
            MockCalledOnceWith([NodeGroup.objects.ensure_master()]))

    def test_rejects_invalid_ip(self):
        requested_address = factory.make_name('bogus')
        device = factory.make_Node(
            installable=False, mac=True, disable_ipv4=False,
            owner=self.logged_in_user)
        mac = device.macaddress_set.all()[0]
        response = self.client.post(
            get_device_uri(device),
            {
                'op': 'claim_sticky_ip_address',
                'requested_address': requested_address,
                'mac_address': mac.mac_address
            })
        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertEqual(
            dict(requested_address=["Enter a valid IPv4 or IPv6 address."]),
            json.loads(response.content))

    def test_rejects_invalid_mac(self):
        mac_address = factory.make_name('bogus')
        requested_address = factory.make_ip_address()
        device = factory.make_Node(
            installable=False, mac=True, disable_ipv4=False,
            owner=self.logged_in_user)
        response = self.client.post(
            get_device_uri(device),
            {
                'op': 'claim_sticky_ip_address',
                'requested_address': requested_address,
                'mac_address': mac_address
            })
        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertEqual(
            dict(
                mac_address=[
                    "'%s' is not a valid MAC address." % mac_address]),
            json.loads(response.content))

    def test_rejects_unrelated_mac(self):
        # Create an other device.
        other_device = factory.make_Node(
            installable=False, mac=True, disable_ipv4=False,
            owner=factory.make_User())
        other_mac = other_device.macaddress_set.all()[0]

        requested_address = factory.make_ip_address()
        device = factory.make_Node(
            installable=False, mac=True, disable_ipv4=False,
            owner=self.logged_in_user)
        # Silence 'update_host_maps'.
        self.patch(Node.update_host_maps)
        response = self.client.post(
            get_device_uri(device),
            {
                'op': 'claim_sticky_ip_address',
                'requested_address': requested_address,
                'mac_address': other_mac.mac_address
            })
        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertItemsEqual([], StaticIPAddress.objects.all())


class TestDeviceReleaseStickyIpAddressAPI(APITestCase):
    """Tests for /api/1.0/devices/?op=release_sticky_ip_address."""

    def test__releases_ip_address(self):
        parent = factory.make_Node_with_MACAddress_and_NodeGroupInterface()
        device = factory.make_Node(
            installable=False, parent=parent, mac=True, disable_ipv4=False,
            owner=self.logged_in_user)
        # Silence 'update_host_maps' and 'remove_host_maps'
        self.patch(Node.update_host_maps)
        self.patch(node_module, node_module.remove_host_maps.__name__)
        response = self.client.post(
            get_device_uri(device), {'op': 'claim_sticky_ip_address'})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_device = json.loads(response.content)
        self.expectThat(parsed_device["ip_addresses"], Not(HasLength(0)))

        response = self.client.post(
            get_device_uri(device), {'op': 'release_sticky_ip_address'})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_device = json.loads(response.content)
        self.expectThat(parsed_device["ip_addresses"], HasLength(0))

    def test__rejects_invalid_ip(self):
        device = factory.make_Node(
            installable=False, mac=True, disable_ipv4=False,
            owner=self.logged_in_user)
        response = self.client.post(
            get_device_uri(device),
            {
                'op': 'release_sticky_ip_address',
                'address': factory.make_name('bogus'),
            })
        self.assertEqual(
            httplib.BAD_REQUEST, response.status_code, response.content)
        self.assertEqual(
            dict(address=["Enter a valid IPv4 or IPv6 address."]),
            json.loads(response.content))

    def test__rejects_empty_ip(self):
        device = factory.make_Node(
            installable=False, mac=True, disable_ipv4=False,
            owner=self.logged_in_user)
        response = self.client.post(
            get_device_uri(device),
            {
                'op': 'release_sticky_ip_address',
                'address': '',
            })
        self.assertEqual(
            httplib.BAD_REQUEST, response.status_code, response.content)


class TestDeviceReleaseStickyIpAddressAPITransactional(APITransactionTestCase):
    '''The following TestDeviceReleaseStickyIpAddressAPI tests require
        APITransactionTestCase, and thus, have been separated
        from the TestDeviceReleaseStickyIpAddressAPI above.
    '''
    def test__releases_all_ip_addresses(self):
        network = factory._make_random_network(slash=24)
        device = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            installable=False, mac_count=5, network=network,
            disable_ipv4=False, owner=self.logged_in_user)
        # Silence 'update_host_maps' and 'remove_host_maps'
        self.patch(Node.update_host_maps)
        self.patch(node_module, node_module.remove_host_maps.__name__)
        self.assertThat(MACAddress.objects.all(), HasLength(5))
        for mac in MACAddress.objects.all():
            with transaction.atomic():
                allocated = device.claim_static_ip_addresses(
                    alloc_type=IPADDRESS_TYPE.STICKY, mac=mac)
            self.expectThat(allocated, HasLength(1))
        response = self.client.post(
            get_device_uri(device), {'op': 'release_sticky_ip_address'})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_device = json.loads(response.content)
        self.expectThat(parsed_device["ip_addresses"], HasLength(0))

    def test__releases_specific_address(self):
        network = factory._make_random_network(slash=24)
        device = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            installable=False, mac_count=2, network=network,
            disable_ipv4=False, owner=self.logged_in_user)
        # Silence 'update_host_maps' and 'remove_host_maps'
        self.patch(Node.update_host_maps)
        self.patch(node_module, node_module.remove_host_maps.__name__)
        self.assertThat(MACAddress.objects.all(), HasLength(2))
        ips = []
        for mac in MACAddress.objects.all():
            with transaction.atomic():
                allocated = device.claim_static_ip_addresses(
                    alloc_type=IPADDRESS_TYPE.STICKY, mac=mac)
            self.expectThat(allocated, HasLength(1))
            # Note: 'allocated' is a list of (ip,mac) tuples
            ips.append(allocated[0][0])
        response = self.client.post(
            get_device_uri(device),
            {
                'op': 'release_sticky_ip_address',
                'address': ips[0]
            })
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_device = json.loads(response.content)
        self.expectThat(parsed_device["ip_addresses"], HasLength(1))

    def test__rejected_if_not_permitted(self):
        parent = factory.make_Node_with_MACAddress_and_NodeGroupInterface()
        device = factory.make_Node(
            installable=False, parent=parent, mac=True, disable_ipv4=False,
            owner=factory.make_User())
        # Silence 'update_host_maps' and 'remove_host_maps'
        self.patch(Node.update_host_maps)
        self.patch(node_module, "remove_host_maps")
        with transaction.atomic():
            device.claim_static_ip_addresses(alloc_type=IPADDRESS_TYPE.STICKY)
        self.assertThat(StaticIPAddress.objects.all(), HasLength(1))
        response = self.client.post(
            get_device_uri(device), {'op': 'release_sticky_ip_address'})
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)
        self.assertThat(StaticIPAddress.objects.all(), HasLength(1))
