# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for IP addresses API."""

__all__ = []

import http.client

from django.conf import settings
from django.core.urlresolvers import reverse
from maasserver.enum import (
    INTERFACE_LINK_TYPE,
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
)
from maasserver.models import (
    Interface,
    interface as interface_module,
    StaticIPAddress,
)
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.utils.converters import json_load_bytes
from maastesting.matchers import MockCalledOnceWith
from netaddr import IPAddress
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from testtools.matchers import (
    Equals,
    HasLength,
    Is,
    Not,
)
from twisted.python.failure import Failure


class TestIPAddressesAPI(APITestCase):

    def make_interface(self, status=NODEGROUP_STATUS.ENABLED, **kwargs):
        cluster = factory.make_NodeGroup(status=status, **kwargs)
        return factory.make_NodeGroupInterface(
            cluster, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)

    def post_reservation_request(
            self, net=None, requested_address=None, mac=None, hostname=None):
        params = {
            'op': 'reserve',
        }
        if requested_address is not None:
            params["requested_address"] = requested_address
        if net is not None:
            params["network"] = str(net)
        if mac is not None:
            params["mac"] = mac
        if hostname is not None:
            params["hostname"] = hostname
        return self.client.post(reverse('ipaddresses_handler'), params)

    def post_release_request(self, ip, mac=None):
        params = {
            'op': 'release',
            'ip': ip,
        }
        if mac is not None:
            params["mac"] = mac
        return self.client.post(reverse('ipaddresses_handler'), params)

    def assertNoMatchingNetworkError(self, response, net):
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content)
        expected = (
            "No network found matching %s; you may be requesting an IP "
            "on a network with no static IP range defined." % str(net))
        self.assertEqual(
            expected.encode(settings.DEFAULT_CHARSET),
            response.content)

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/ipaddresses/', reverse('ipaddresses_handler'))

    def test_POST_reserve_creates_ipaddress(self):
        interface = self.make_interface()
        net = interface.network
        response = self.post_reservation_request(net)
        self.assertEqual(http.client.OK, response.status_code)
        returned_address = json_load_bytes(response.content)
        [staticipaddress] = StaticIPAddress.objects.all()
        # We don't need to test the value of the 'created' datetime
        # field. By removing it, we also test for its presence.
        del returned_address['created']
        expected = dict(
            alloc_type=staticipaddress.alloc_type,
            ip=staticipaddress.ip,
            resource_uri=reverse('ipaddresses_handler'),
            )
        self.assertEqual(expected, returned_address)
        self.assertEqual(
            IPADDRESS_TYPE.USER_RESERVED, staticipaddress.alloc_type)
        self.assertEqual(self.logged_in_user, staticipaddress.user)

    def test_POST_reserve_with_MAC_links_MAC_to_ip_address(self):
        update_host_maps = self.patch(interface_module, 'update_host_maps')
        interface = self.make_interface()
        net = interface.network
        mac = factory.make_mac_address()

        response = self.post_reservation_request(net=net, mac=mac)
        self.assertEqual(http.client.OK, response.status_code)
        returned_address = json_load_bytes(response.content)
        [staticipaddress] = StaticIPAddress.objects.all()
        self.expectThat(
            staticipaddress.interface_set.first().mac_address,
            Equals(mac))

        # DHCP Host maps have been updated.
        self.expectThat(
            update_host_maps,
            MockCalledOnceWith(
                {interface.nodegroup: {returned_address['ip']: mac}}))

    def test_POST_reserve_with_MAC_returns_503_if_hostmap_update_fails(self):
        update_host_maps = self.patch(interface_module, 'update_host_maps')
        # We a specific exception here because update_host_maps() will
        # fail with RPC-specific errors.
        update_host_maps.return_value = [
            Failure(
                NoConnectionsAvailable(
                    "Are you sure you're not Elvis?"))
            ]
        interface = self.make_interface()
        net = interface.network
        mac = factory.make_mac_address()

        response = self.post_reservation_request(net=net, mac=mac)
        self.expectThat(
            response.status_code, Equals(http.client.SERVICE_UNAVAILABLE))
        # No static IP has been created.
        self.expectThat(
            StaticIPAddress.objects.all(), HasLength(0))
        # No Interface has been created, either.
        self.expectThat(
            Interface.objects.all(), HasLength(0))

    def test_POST_returns_error_when_static_ip_for_MAC_already_exists(self):
        self.patch(interface_module, 'update_host_maps')
        interface = self.make_interface()
        nic = factory.make_Interface(cluster_interface=interface)
        nic.link_subnet(INTERFACE_LINK_TYPE.STATIC, interface.subnet)
        net = interface.network

        response = self.post_reservation_request(net=net, mac=nic.mac_address)
        self.assertEqual(
            http.client.CONFLICT, response.status_code, response.content)
        self.expectThat(
            StaticIPAddress.objects.all().count(),
            Equals(1))

    def test_POST_allows_claiming_of_new_static_ips_for_existing_MAC(self):
        self.patch(interface_module, 'update_host_maps')

        interface = self.make_interface()
        net = interface.network
        nic = factory.make_Interface(
            INTERFACE_TYPE.UNKNOWN, cluster_interface=interface)

        response = self.post_reservation_request(net=net, mac=nic.mac_address)
        self.expectThat(response.status_code, Equals(http.client.OK))
        [staticipaddress] = nic.ip_addresses.all()
        self.assertEqual(
            staticipaddress.interface_set.first().mac_address,
            nic.mac_address)

    def test_POST_reserve_errors_for_no_matching_interface(self):
        interface = self.make_interface()
        net = factory.make_ipv4_network(but_not=[interface.network])
        response = self.post_reservation_request(net=net)
        self.assertNoMatchingNetworkError(response, net)

    def test_POST_reserve_errors_for_interface_with_no_IP_range(self):
        interface = self.make_interface()
        net = interface.network
        interface.static_ip_range_low = None
        interface.static_ip_range_high = None
        interface.save()
        response = self.post_reservation_request(net)
        self.assertNoMatchingNetworkError(response, net)

    def test_POST_reserve_errors_for_invalid_network(self):
        net = factory.make_string()
        response = self.post_reservation_request(net=net)
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content)
        self.assertEqual(
            ("Invalid network parameter: %s" % net).encode(
                settings.DEFAULT_CHARSET),
            response.content)

    def test_POST_reserve_creates_requested_address(self):
        interface = self.make_interface()
        net = interface.network
        ip_in_network = interface.static_ip_range_low
        response = self.post_reservation_request(
            net=net, requested_address=ip_in_network)
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        returned_address = json_load_bytes(response.content)
        [staticipaddress] = StaticIPAddress.objects.all()
        self.expectThat(
            returned_address["alloc_type"],
            Equals(IPADDRESS_TYPE.USER_RESERVED))
        self.expectThat(returned_address["ip"], Equals(ip_in_network))
        self.expectThat(staticipaddress.ip, Equals(ip_in_network))

    def test_POST_reserve_creates_address_outside_of_static_range(self):
        interface = self.make_interface()
        interface.ip_range_high = str(
            IPAddress(interface.ip_range_high) - 1)
        interface.save()
        net = interface.network
        ip_in_network = str(
            IPAddress(interface.ip_range_high) + 1)
        response = self.post_reservation_request(
            net=net, requested_address=ip_in_network)
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        returned_address = json_load_bytes(response.content)
        [staticipaddress] = StaticIPAddress.objects.all()
        self.expectThat(
            returned_address["alloc_type"],
            Equals(IPADDRESS_TYPE.USER_RESERVED))
        self.expectThat(returned_address["ip"], Equals(ip_in_network))
        self.expectThat(staticipaddress.ip, Equals(ip_in_network))

    def test_POST_reserve_requested_address_detects_in_use_address(self):
        interface = self.make_interface()
        net = interface.network
        ip_in_network = interface.static_ip_range_low
        response = self.post_reservation_request(net, ip_in_network)
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        # Do same request again and check it is rejected.
        response = self.post_reservation_request(
            net=net, requested_address=ip_in_network)
        self.expectThat(response.status_code, Equals(http.client.NOT_FOUND))
        self.expectThat(
            response.content, Equals((
                "The IP address %s is already in use." % ip_in_network).encode(
                settings.DEFAULT_CHARSET)))

    def test_POST_reserve_requested_address_rejects_ip_in_dynamic_range(self):
        interface = self.make_interface()
        net = interface.network
        ip_in_network = interface.ip_range_low
        response = self.post_reservation_request(net, ip_in_network)
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content)

    def test_POST_reserve_with_hostname_creates_ip_with_hostname(self):
        from maasserver.dns import config as dns_config_module
        dns_update_zones = self.patch(dns_config_module, 'dns_update_zones')
        interface = self.make_interface()
        net = interface.network
        hostname = factory.make_hostname()
        response = self.post_reservation_request(net=net, hostname=hostname)
        self.assertEqual(http.client.OK, response.status_code)
        [staticipaddress] = StaticIPAddress.objects.all()
        self.expectThat(staticipaddress.hostname, Equals(hostname))
        self.expectThat(dns_update_zones.call_count, Equals(1))

    def test_POST_reserve_with_hostname_and_ip_creates_ip_with_hostname(self):
        from maasserver.dns import config as dns_config_module
        dns_update_zones = self.patch(dns_config_module, 'dns_update_zones')
        interface = self.make_interface()
        net = interface.network
        hostname = factory.make_hostname()
        ip_in_network = interface.static_ip_range_low
        response = self.post_reservation_request(
            net=net, requested_address=ip_in_network, hostname=hostname)
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        returned_address = json_load_bytes(response.content)
        [staticipaddress] = StaticIPAddress.objects.all()
        self.expectThat(
            returned_address["alloc_type"],
            Equals(IPADDRESS_TYPE.USER_RESERVED))
        self.expectThat(returned_address["ip"], Equals(ip_in_network))
        self.expectThat(staticipaddress.ip, Equals(ip_in_network))
        self.expectThat(staticipaddress.hostname, Equals(hostname))
        self.expectThat(dns_update_zones.call_count, Equals(1))

    def test_POST_reserve_with_no_parameters_fails_with_bad_request(self):
        response = self.post_reservation_request()
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content)

    def test_POST_reserve_rejects_invalid_ip(self):
        response = self.post_reservation_request(
            requested_address="1690.254.0.1")
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertEqual(
            dict(requested_address=["Enter a valid IPv4 or IPv6 address."]),
            json_load_bytes(response.content))

    def test_POST_release_rejects_invalid_ip(self):
        response = self.post_release_request("1690.254.0.1")
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertEqual(
            dict(ip=["Enter a valid IPv4 or IPv6 address."]),
            json_load_bytes(response.content))

    def test_GET_returns_ipaddresses(self):
        original_ipaddress = factory.make_StaticIPAddress(
            user=self.logged_in_user)
        response = self.client.get(reverse('ipaddresses_handler'))
        self.assertEqual(
            http.client.OK, response.status_code, response.content)

        parsed_result = json_load_bytes(response.content)
        self.assertEqual(1, len(parsed_result), response.content)
        [returned_address] = parsed_result
        fields = {'alloc_type', 'ip'}
        self.assertEqual(
            fields.union({'resource_uri', 'created'}),
            set(returned_address.keys()))
        expected_values = {
            field: getattr(original_ipaddress, field)
            for field in fields
            if field not in ('resource_uri', 'created')
        }
        # We don't need to test the value of the 'created' datetime
        # field.
        del returned_address['created']
        expected_values['resource_uri'] = reverse('ipaddresses_handler')
        self.assertEqual(expected_values, returned_address)

    def test_GET_returns_empty_if_no_ipaddresses(self):
        response = self.client.get(reverse('ipaddresses_handler'))
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        self.assertEqual([], json_load_bytes(response.content))

    def test_GET_only_returns_request_users_addresses(self):
        ipaddress = factory.make_StaticIPAddress(user=self.logged_in_user)
        factory.make_StaticIPAddress(user=factory.make_User())
        response = self.client.get(reverse('ipaddresses_handler'))
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed_result = json_load_bytes(response.content)
        [returned_address] = parsed_result
        self.assertEqual(ipaddress.ip, returned_address['ip'])

    def test_GET_sorts_by_id(self):
        addrs = []
        for _ in range(3):
            addrs.append(
                factory.make_StaticIPAddress(user=self.logged_in_user))
        response = self.client.get(reverse('ipaddresses_handler'))
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed_result = json_load_bytes(response.content)
        expected = [
            addr.ip for addr in
            sorted(addrs, key=lambda addr: getattr(addr, "id"))]
        observed = [result['ip'] for result in parsed_result]
        self.assertEqual(expected, observed)

    def test_POST_release_deallocates_address(self):
        ipaddress = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, user=self.logged_in_user)
        response = self.post_release_request(ipaddress.ip)
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        self.assertIsNone(reload_object(ipaddress))

    def test_POST_release_deletes_unknown_interface(self):
        self.patch(interface_module, "update_host_maps")
        self.patch(interface_module, "remove_host_maps")

        interface = self.make_interface()
        unknown_nic = factory.make_Interface(
            INTERFACE_TYPE.UNKNOWN, cluster_interface=interface)
        ipaddress = unknown_nic.link_subnet(
            INTERFACE_LINK_TYPE.STATIC, interface.subnet,
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, user=self.logged_in_user)

        self.post_release_request(ipaddress.ip)
        self.assertIsNone(reload_object(unknown_nic))

    def test_POST_release_does_not_delete_interfaces_linked_to_nodes(self):
        self.patch(interface_module, "update_host_maps")
        self.patch(interface_module, "remove_host_maps")

        interface = self.make_interface()
        node = factory.make_Node(nodegroup=interface.nodegroup)
        attached_nic = factory.make_Interface(
            node=node, cluster_interface=interface)
        ipaddress = attached_nic.link_subnet(
            INTERFACE_LINK_TYPE.STATIC, interface.subnet,
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, user=self.logged_in_user)

        self.post_release_request(ipaddress.ip)
        self.assertEqual(attached_nic, reload_object(attached_nic))

    def test_POST_release_raises_503_if_removing_host_maps_errors(self):
        self.patch(interface_module, "update_host_maps")
        remove_host_maps = self.patch(interface_module, "remove_host_maps")
        # Failures in remove_host_maps() will be RPC-related exceptions,
        # so we use one of those explicitly.
        remove_host_maps.return_value = [
            Failure(
                NoConnectionsAvailable(
                    "The wizard's staff has a knob on the end."))
            ]

        interface = self.make_interface()
        floating_nic = factory.make_Interface(cluster_interface=interface)
        ipaddress = floating_nic.link_subnet(
            INTERFACE_LINK_TYPE.STATIC, interface.subnet,
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, user=self.logged_in_user)

        response = self.post_release_request(ipaddress.ip)
        self.expectThat(
            response.status_code, Equals(http.client.SERVICE_UNAVAILABLE))

        # The static IP hasn't been deleted.
        self.expectThat(
            reload_object(ipaddress), Not(Is(None)))

        # Neither has the DHCPHost.
        self.expectThat(
            reload_object(floating_nic), Not(Is(None)))

    def test_POST_release_does_not_delete_IP_that_I_dont_own(self):
        ipaddress = factory.make_StaticIPAddress(user=factory.make_User())
        response = self.post_release_request(ipaddress.ip)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content)

    def test_POST_release_does_not_delete_other_IPs_I_own(self):
        ipaddress = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, user=self.logged_in_user)
        other_address = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, user=self.logged_in_user)
        response = self.post_release_request(ipaddress.ip)
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        self.assertIsNotNone(reload_object(other_address))
