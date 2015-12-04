# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for devices API."""

__all__ = []

import http.client
import random

from django.core.urlresolvers import reverse
from django.db import transaction
from maasserver.enum import (
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_STATUS,
)
from maasserver.models import (
    interface as interface_module,
    Node,
    NodeGroup,
    StaticIPAddress,
)
from maasserver.testing.api import (
    APITestCase,
    APITransactionTestCase,
)
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.utils.converters import json_load_bytes
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
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        system_id = json_load_bytes(response.content)['system_id']
        device = Node.devices.get(system_id=system_id)
        self.assertEqual(hostname, device.hostname)
        self.assertIsNone(device.parent)
        self.assertFalse(device.installable)
        self.assertEqual(NodeGroup.objects.ensure_master(), device.nodegroup)
        self.assertEqual(self.logged_in_user, device.owner)
        self.assertEqual(
            macs,
            {nic.mac_address for nic in device.interface_set.all()})

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
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        system_id = json_load_bytes(response.content)['system_id']
        device = Node.devices.get(system_id=system_id)
        self.assertEqual(hostname, device.hostname)
        self.assertEqual(parent, device.parent)
        self.assertFalse(device.installable)

    def test_POST_returns_limited_fields(self):
        response = self.client.post(
            reverse('devices_handler'),
            {
                'op': 'new',
                'hostname': factory.make_string(),
                'mac_addresses': ['aa:bb:cc:dd:ee:ff'],
            })
        parsed_result = json_load_bytes(response.content)
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
                nodegroup=nodegroup, interface=True, installable=False,
                owner=owner)
            for _ in range(nb)
        ]

    def test_list_lists_devices(self):
        # The api allows for fetching the list of devices.
        devices = self.create_devices(owner=self.logged_in_user)
        factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.logged_in_user)
        response = self.client.get(reverse('devices_handler'), {'op': 'list'})
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.OK, response.status_code)
        self.assertItemsEqual(
            [device.system_id for device in devices],
            [device.get('system_id') for device in parsed_result])

    def test_list_ignores_nodes(self):
        factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.logged_in_user)
        response = self.client.get(reverse('devices_handler'), {'op': 'list'})
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
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
        parsed_result = json_load_bytes(response.content)
        self.assertItemsEqual(
            [matching_id],
            [device.get('system_id') for device in parsed_result])

    def test_list_with_macaddress_returns_matching_devices(self):
        # The "list" operation takes optional "mac_address" parameters.  Only
        # devices with matching MAC addresses will be returned.
        devices = self.create_devices(owner=self.logged_in_user)
        matching_device = devices[0]
        matching_mac = matching_device.get_boot_interface().mac_address
        response = self.client.get(reverse('devices_handler'), {
            'op': 'list',
            'mac_address': [matching_mac],
        })
        parsed_result = json_load_bytes(response.content)
        self.assertItemsEqual(
            [matching_device.system_id],
            [device.get('system_id') for device in parsed_result])

    def test_list_returns_limited_fields(self):
        self.create_devices(owner=self.logged_in_user)
        response = self.client.get(reverse('devices_handler'), {'op': 'list'})
        parsed_result = json_load_bytes(response.content)
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
            http.client.BAD_REQUEST, response.status_code, response.content)

    def test_GET_reads_device(self):
        device = factory.make_Node(
            installable=False, owner=self.logged_in_user)

        response = self.client.get(get_device_uri(device))
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed_device = json_load_bytes(response.content)
        self.assertEqual(device.system_id, parsed_device["system_id"])

    def test_PUT_updates_device_hostname(self):
        device = factory.make_Node(
            installable=False, owner=self.logged_in_user)
        new_hostname = factory.make_name('hostname')

        response = self.client.put(
            get_device_uri(device), {'hostname': new_hostname})
        self.assertEqual(
            http.client.OK, response.status_code, response.content)

        device = reload_object(device)
        self.assertEqual(new_hostname, device.hostname)

    def test_PUT_updates_device_parent(self):
        parent = factory.make_Node()
        device = factory.make_Node(
            installable=False, owner=self.logged_in_user, parent=parent)
        new_parent = factory.make_Node()

        response = self.client.put(
            get_device_uri(device), {'parent': new_parent.system_id})
        self.assertEqual(
            http.client.OK, response.status_code, response.content)

        device = reload_object(device)
        self.assertEqual(new_parent, device.parent)

    def test_PUT_rejects_edit_if_not_permitted(self):
        device = factory.make_Node(
            installable=False, owner=factory.make_User())
        old_hostname = device.hostname

        response = self.client.put(
            get_device_uri(device),
            {'hostname': factory.make_name('hostname')})
        self.assertEqual(http.client.FORBIDDEN, response.status_code)
        self.assertEqual(old_hostname, reload_object(device).hostname)

    def test_DELETE_removes_device(self):
        device = factory.make_Node(
            installable=False, owner=self.logged_in_user)
        response = self.client.delete(get_device_uri(device))
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content)
        self.assertIsNone(reload_object(device))

    def test_DELETE_rejects_deletion_if_not_permitted(self):
        device = factory.make_Node(
            installable=False, owner=factory.make_User())
        response = self.client.delete(get_device_uri(device))
        self.assertEqual(http.client.FORBIDDEN, response.status_code)
        self.assertEqual(device, reload_object(device))


class TestClaimStickyIpAddressAPI(APITestCase):
    """Tests for /api/1.0/devices/?op=claim_sticky_ip_address."""

    def test__claims_ip_address_from_cluster_interface(self):
        parent = factory.make_Node_with_Interface_on_Subnet()
        device = factory.make_Node(
            installable=False, parent=parent, interface=True,
            disable_ipv4=False, owner=self.logged_in_user)
        # Silence 'update_host_maps'.
        self.patch_autospec(interface_module, "update_host_maps")
        response = self.client.post(
            get_device_uri(device), {'op': 'claim_sticky_ip_address'})
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed_device = json_load_bytes(response.content)
        [returned_ip] = parsed_device["ip_addresses"]
        static_ip = StaticIPAddress.objects.filter(ip=returned_ip).first()
        self.assertIsNotNone(static_ip)
        self.assertEqual(IPADDRESS_TYPE.STICKY, static_ip.alloc_type)

    def test__rejected_if_not_permitted(self):
        parent = factory.make_Node_with_Interface_on_Subnet()
        device = factory.make_Node(
            installable=False, parent=parent, interface=True,
            disable_ipv4=False, owner=factory.make_User())
        self.patch_autospec(interface_module, "update_host_maps")
        response = self.client.post(
            get_device_uri(device), {'op': 'claim_sticky_ip_address'})
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_creates_ip_with_random_ip(self):
        requested_address = factory.make_ip_address()
        device = factory.make_Node(
            installable=False, interface=True, disable_ipv4=False,
            owner=self.logged_in_user)
        # Silence 'update_host_maps'.
        self.patch_autospec(interface_module, "update_host_maps")
        response = self.client.post(
            get_device_uri(device),
            {
                'op': 'claim_sticky_ip_address',
                'requested_address': requested_address,
            })
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed_device = json_load_bytes(response.content)
        [returned_ip] = parsed_device["ip_addresses"]
        [given_ip] = StaticIPAddress.objects.all()
        self.assertEqual(
            (given_ip.ip, requested_address, IPADDRESS_TYPE.STICKY),
            (returned_ip, returned_ip, given_ip.alloc_type)
        )

    def test_creates_ip_for_specific_mac(self):
        requested_address = factory.make_ip_address()
        device = factory.make_Node(
            installable=False, interface=True, disable_ipv4=False,
            owner=self.logged_in_user)
        second_nic = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=device)
        # Silence 'update_host_maps'.
        self.patch_autospec(interface_module, "update_host_maps")
        response = self.client.post(
            get_device_uri(device),
            {
                'op': 'claim_sticky_ip_address',
                'requested_address': requested_address,
                'mac_address': str(second_nic.mac_address),
            })
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed_device = json_load_bytes(response.content)
        [returned_ip] = parsed_device["ip_addresses"]
        [given_ip] = StaticIPAddress.objects.all()
        self.assertEqual(
            (given_ip.ip, requested_address, IPADDRESS_TYPE.STICKY),
            (returned_ip, returned_ip, given_ip.alloc_type)
        )

    def test_rejects_invalid_ip(self):
        requested_address = factory.make_name('bogus')
        device = factory.make_Node(
            installable=False, interface=True, disable_ipv4=False,
            owner=self.logged_in_user)
        interface = device.interface_set.all()[0]
        response = self.client.post(
            get_device_uri(device),
            {
                'op': 'claim_sticky_ip_address',
                'requested_address': requested_address,
                'mac_address': interface.mac_address
            })
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertEqual(
            dict(requested_address=["Enter a valid IPv4 or IPv6 address."]),
            json_load_bytes(response.content))

    def test_rejects_invalid_mac(self):
        mac_address = factory.make_name('bogus')
        requested_address = factory.make_ip_address()
        device = factory.make_Node(
            installable=False, interface=True, disable_ipv4=False,
            owner=self.logged_in_user)
        response = self.client.post(
            get_device_uri(device),
            {
                'op': 'claim_sticky_ip_address',
                'requested_address': requested_address,
                'mac_address': mac_address
            })
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertEqual(
            dict(
                mac_address=[
                    "'%s' is not a valid MAC address." % mac_address]),
            json_load_bytes(response.content))

    def test_rejects_unrelated_mac(self):
        # Create an other device.
        other_device = factory.make_Node(
            installable=False, interface=True, disable_ipv4=False,
            owner=factory.make_User())
        other_nic = other_device.interface_set.all()[0]

        requested_address = factory.make_ip_address()
        device = factory.make_Node(
            installable=False, interface=True, disable_ipv4=False,
            owner=self.logged_in_user)
        # Silence 'update_host_maps'.
        self.patch_autospec(interface_module, "update_host_maps")
        response = self.client.post(
            get_device_uri(device),
            {
                'op': 'claim_sticky_ip_address',
                'requested_address': requested_address,
                'mac_address': other_nic.mac_address
            })
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertItemsEqual([], StaticIPAddress.objects.all())


class TestDeviceReleaseStickyIpAddressAPI(APITestCase):
    """Tests for /api/1.0/devices/?op=release_sticky_ip_address."""

    def test__releases_ip_address(self):
        parent = factory.make_Node_with_Interface_on_Subnet()
        device = factory.make_Node(
            installable=False, parent=parent, interface=True,
            disable_ipv4=False, owner=self.logged_in_user)
        # Silence 'update_host_maps' and 'remove_host_maps'
        self.patch_autospec(interface_module, "update_host_maps")
        self.patch_autospec(interface_module, "remove_host_maps")
        response = self.client.post(
            get_device_uri(device), {'op': 'claim_sticky_ip_address'})
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed_device = json_load_bytes(response.content)
        self.expectThat(parsed_device["ip_addresses"], Not(HasLength(0)))

        response = self.client.post(
            get_device_uri(device), {'op': 'release_sticky_ip_address'})
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed_device = json_load_bytes(response.content)
        self.expectThat(parsed_device["ip_addresses"], HasLength(0))

    def test__rejects_invalid_ip(self):
        device = factory.make_Node(
            installable=False, interface=True, disable_ipv4=False,
            owner=self.logged_in_user)
        response = self.client.post(
            get_device_uri(device),
            {
                'op': 'release_sticky_ip_address',
                'address': factory.make_name('bogus'),
            })
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content)
        self.assertEqual(
            dict(address=["Enter a valid IPv4 or IPv6 address."]),
            json_load_bytes(response.content))

    def test__rejects_empty_ip(self):
        device = factory.make_Node(
            installable=False, interface=True, disable_ipv4=False,
            owner=self.logged_in_user)
        response = self.client.post(
            get_device_uri(device),
            {
                'op': 'release_sticky_ip_address',
                'address': '',
            })
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content)


class TestDeviceReleaseStickyIpAddressAPITransactional(APITransactionTestCase):
    '''The following TestDeviceReleaseStickyIpAddressAPI tests require
        APITransactionTestCase, and thus, have been separated
        from the TestDeviceReleaseStickyIpAddressAPI above.
    '''
    def test__releases_all_ip_addresses(self):
        network = factory._make_random_network(slash=24)
        subnet = factory.make_Subnet(cidr=str(network.cidr))
        device = factory.make_Node_with_Interface_on_Subnet(
            installable=False, subnet=subnet,
            disable_ipv4=False, owner=self.logged_in_user)
        for _ in range(4):
            extra_nic = factory.make_Interface(
                INTERFACE_TYPE.PHYSICAL, node=device)
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.DISCOVERED, ip="",
                interface=extra_nic, subnet=subnet)
        # Silence 'update_host_maps' and 'remove_host_maps'
        self.patch_autospec(interface_module, "update_host_maps")
        self.patch_autospec(interface_module, "remove_host_maps")
        self.assertThat(device.interface_set.all(), HasLength(5))
        for interface in device.interface_set.all():
            with transaction.atomic():
                allocated = interface.claim_static_ips()
            self.expectThat(allocated, HasLength(1))
        response = self.client.post(
            get_device_uri(device), {'op': 'release_sticky_ip_address'})
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed_device = json_load_bytes(response.content)
        self.expectThat(parsed_device["ip_addresses"], HasLength(0))

    def test__releases_specific_address(self):
        network = factory._make_random_network(slash=24)
        subnet = factory.make_Subnet(cidr=str(network.cidr))
        device = factory.make_Node_with_Interface_on_Subnet(
            installable=False, subnet=subnet,
            disable_ipv4=False, owner=self.logged_in_user)
        extra_nic = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=device)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip="",
            interface=extra_nic, subnet=subnet)
        # Silence 'update_host_maps' and 'remove_host_maps'
        self.patch_autospec(interface_module, "update_host_maps")
        self.patch_autospec(interface_module, "remove_host_maps")
        self.assertThat(device.interface_set.all(), HasLength(2))
        ips = []
        for interface in device.interface_set.all():
            with transaction.atomic():
                allocated = interface.claim_static_ips()
            self.expectThat(allocated, HasLength(1))
            # Note: 'allocated' is a list of (ip,mac) tuples
            ips.append(allocated[0])
        response = self.client.post(
            get_device_uri(device),
            {
                'op': 'release_sticky_ip_address',
                'address': str(ips[0].ip)
            })
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed_device = json_load_bytes(response.content)
        self.expectThat(parsed_device["ip_addresses"], HasLength(1))

    def test__rejected_if_not_permitted(self):
        parent = factory.make_Node_with_Interface_on_Subnet()
        device = factory.make_Node(
            installable=False, parent=parent, interface=True,
            disable_ipv4=False, owner=factory.make_User())
        # Silence 'update_host_maps' and 'remove_host_maps'
        self.patch_autospec(interface_module, "update_host_maps")
        self.patch_autospec(interface_module, "remove_host_maps")
        with transaction.atomic():
            device.get_boot_interface().claim_static_ips()
        self.assertThat(
            StaticIPAddress.objects.filter(alloc_type=IPADDRESS_TYPE.STICKY),
            HasLength(1))
        response = self.client.post(
            get_device_uri(device), {'op': 'release_sticky_ip_address'})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content)
        self.assertThat(
            StaticIPAddress.objects.filter(alloc_type=IPADDRESS_TYPE.STICKY),
            HasLength(1))
