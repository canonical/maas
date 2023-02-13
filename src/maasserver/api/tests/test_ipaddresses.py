# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for IP addresses API."""


import http.client

from django.conf import settings
from django.urls import reverse
from netaddr import IPAddress
from testtools.matchers import Equals, HasLength

from maasserver.enum import INTERFACE_LINK_TYPE, INTERFACE_TYPE, IPADDRESS_TYPE
from maasserver.models import DNSResource, StaticIPAddress
from maasserver.testing.api import APITestCase, APITransactionTestCase
from maasserver.testing.factory import factory
from maasserver.utils.converters import json_load_bytes
from maasserver.utils.orm import reload_object, transactional
from maastesting.matchers import DocTestMatches


class TestIPAddressesAPI(APITestCase.ForUserAndAdmin):
    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/ipaddresses/", reverse("ipaddresses_handler")
        )

    def test_GET_returns_ipaddresses(self):
        original_ipaddress = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, user=self.user
        )
        response = self.client.get(reverse("ipaddresses_handler"))
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )

        parsed_result = json_load_bytes(response.content)
        self.assertEqual(1, len(parsed_result), response.content)
        [returned_address] = parsed_result
        fields = {"alloc_type", "alloc_type_name", "ip"}
        self.assertEqual(
            fields.union(
                {"resource_uri", "created", "subnet", "interface_set", "owner"}
            ),
            set(returned_address.keys()),
        )
        expected_values = {
            field: getattr(original_ipaddress, field)
            for field in fields
            if field not in ("resource_uri", "created")
        }
        # Test that these exist, but not for exact values.
        del returned_address["created"]
        del returned_address["subnet"]
        del returned_address["owner"]
        del returned_address["interface_set"]
        expected_values["resource_uri"] = reverse("ipaddresses_handler")
        self.assertEqual(expected_values, returned_address)

    def test_GET_returns_empty_if_no_ipaddresses(self):
        response = self.client.get(reverse("ipaddresses_handler"))
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertEqual([], json_load_bytes(response.content))

    def test_GET_only_returns_request_users_addresses(self):
        ipaddress = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, user=self.user
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, user=factory.make_User()
        )
        response = self.client.get(reverse("ipaddresses_handler"))
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_result = json_load_bytes(response.content)
        [returned_address] = parsed_result
        self.assertEqual(ipaddress.ip, returned_address["ip"])

    def test_GET_returns_all_addresses_if_admin_and_all_specified(self):
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, user=self.user
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, user=factory.make_User()
        )
        response = self.client.get(
            reverse("ipaddresses_handler"), {"all": "1"}
        )
        if self.user.is_superuser:
            self.assertEqual(
                http.client.OK, response.status_code, response.content
            )
            parsed_result = json_load_bytes(response.content)
            self.assertThat(parsed_result, HasLength(2))
        else:
            self.assertEqual(
                http.client.FORBIDDEN, response.status_code, response.content
            )
            self.assertEqual(
                "Listing all IP addresses requires admin privileges.",
                response.content.decode("utf-8"),
            )

    def test_GET_returns_other_user_addresses_if_admin_and_user_specified(
        self,
    ):
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, user=self.user
        )
        user2 = factory.make_User()
        ipaddress2 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, user=user2
        )
        response = self.client.get(
            reverse("ipaddresses_handler"), {"owner": user2.username}
        )
        if self.user.is_superuser:
            self.assertEqual(
                http.client.OK, response.status_code, response.content
            )
            parsed_result = json_load_bytes(response.content)
            self.assertThat(parsed_result, HasLength(1))
            self.assertEqual(ipaddress2.ip, parsed_result[0]["ip"])
        else:
            self.assertEqual(
                http.client.FORBIDDEN, response.status_code, response.content
            )
            self.assertEqual(
                "Listing another user's IP addresses requires admin privileges.",
                response.content.decode("utf-8"),
            )

    def test_GET_returns_other_users_ip_address_for_admin_with_all_with_ip(
        self,
    ):
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, user=self.user
        )
        user2 = factory.make_User()
        ipaddress2 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, user=user2
        )
        response = self.client.get(
            reverse("ipaddresses_handler"),
            {"ip": str(ipaddress2.ip), "all": "true"},
        )
        if self.user.is_superuser:
            self.assertEqual(
                http.client.OK, response.status_code, response.content
            )
            parsed_result = json_load_bytes(response.content)
            self.assertThat(parsed_result, HasLength(1))
            self.assertEqual(ipaddress2.ip, parsed_result[0]["ip"])
        else:
            self.assertEqual(
                http.client.FORBIDDEN, response.status_code, response.content
            )
            self.assertEqual(
                "Listing all IP addresses requires admin privileges.",
                response.content.decode("utf-8"),
            )

    def test_GET_with_all_for_admin_returns_non_user_reserved_types(self):
        factory.make_StaticIPAddress(alloc_type=IPADDRESS_TYPE.STICKY)
        factory.make_StaticIPAddress(alloc_type=IPADDRESS_TYPE.USER_RESERVED)
        response = self.client.get(
            reverse("ipaddresses_handler"), {"all": "true"}
        )
        if self.user.is_superuser:
            self.assertEqual(
                http.client.OK, response.status_code, response.content
            )
            parsed_result = json_load_bytes(response.content)
            self.assertThat(parsed_result, HasLength(2))
        else:
            self.assertEqual(
                http.client.FORBIDDEN, response.status_code, response.content
            )
            self.assertEqual(
                "Listing all IP addresses requires admin privileges.",
                response.content.decode("utf-8"),
            )

    def test_GET_returns_own_ip_address_with_ip(self):
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, user=self.user
        )
        ipaddress2 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, user=self.user
        )
        response = self.client.get(
            reverse("ipaddresses_handler"), {"ip": str(ipaddress2.ip)}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_result = json_load_bytes(response.content)
        self.assertThat(parsed_result, HasLength(1))
        self.assertEqual(ipaddress2.ip, parsed_result[0]["ip"])

    def test_GET_sorts_by_id(self):
        addrs = []
        for _ in range(3):
            addrs.append(
                factory.make_StaticIPAddress(
                    alloc_type=IPADDRESS_TYPE.USER_RESERVED, user=self.user
                )
            )
        response = self.client.get(reverse("ipaddresses_handler"))
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_result = json_load_bytes(response.content)
        expected = [
            addr.ip
            for addr in sorted(addrs, key=lambda addr: getattr(addr, "id"))
        ]
        observed = [result["ip"] for result in parsed_result]
        self.assertEqual(expected, observed)


class TestIPAddressesReleaseAPI(APITransactionTestCase.ForUserAndAdmin):
    scenarios = (
        ("normal", {"force": None}),
        ("without_force", {"force": False}),
        ("with_force", {"force": True}),
    )

    @property
    def force_should_work(self):
        # The 'force' parameter should only work if (1) the user-under-test
        # is a superuser, and (2) force=true was specified.
        return self.user.is_superuser and self.force is True

    @property
    def expect_forbidden(self):
        # The 'force' parameter should only work if (1) the user-under-test
        # is a superuser, and (2) force=true was specified.
        return not self.user.is_superuser and self.force is True

    def expected_status(self, status):
        # Non-administrators always get a FORBIDDEN (403) when requesting
        # a forced delete.
        if self.force and not self.user.is_superuser:
            return http.client.FORBIDDEN
        else:
            return status

    def post_release_request(self, ip, mac=None, discovered=None):
        params = {"op": "release", "ip": ip}
        if mac is not None:
            params["mac"] = mac
        if self.force is not None:
            params["force"] = str(self.force)
        if discovered is not None:
            params["discovered"] = str(discovered)
        return self.client.post(reverse("ipaddresses_handler"), params)

    @transactional
    def test_POST_release_rejects_invalid_ip(self):
        response = self.post_release_request("1690.254.0.1")
        expected_status = self.expected_status(http.client.BAD_REQUEST)
        self.assertEqual(expected_status, response.status_code)
        if expected_status != http.client.FORBIDDEN:
            self.assertEqual(
                dict(ip=["Enter a valid IPv4 or IPv6 address."]),
                json_load_bytes(response.content),
            )
        else:
            self.assertEqual(
                "Force-releasing an IP address requires admin privileges.",
                response.content.decode("utf-8"),
            )

    @transactional
    def test_POST_release_allows_admin_to_release_other_users_ip(self):
        factory.make_StaticIPAddress(
            user=factory.make_User(),
            alloc_type=IPADDRESS_TYPE.USER_RESERVED,
            ip="192.168.0.1",
        )
        response = self.post_release_request("192.168.0.1")
        if self.expect_forbidden:
            self.assertEqual(http.client.FORBIDDEN, response.status_code)
            self.assertEqual(
                "Force-releasing an IP address requires admin privileges.",
                response.content.decode("utf-8"),
            )
        elif not self.force:
            self.assertEqual(http.client.BAD_REQUEST, response.status_code)
            self.assertThat(
                response.content.decode("utf-8"),
                DocTestMatches("...does not belong to the requesting user..."),
            )
        else:
            self.assertEqual(http.client.NO_CONTENT, response.status_code)
            self.assertEqual("", response.content.decode("utf-8"))

    @transactional
    def test_POST_release_allows_admin_to_release_sticky_ip(self):
        # Make an "orphaned" IP address, like the one in bug #1630034.
        static_ip = factory.make_StaticIPAddress(
            user=factory.make_User(), alloc_type=IPADDRESS_TYPE.STICKY
        )
        response = self.post_release_request(str(static_ip.ip))
        if self.expect_forbidden:
            self.assertEqual(http.client.FORBIDDEN, response.status_code)
            self.assertEqual(
                "Force-releasing an IP address requires admin privileges.",
                response.content.decode("utf-8"),
            )
        elif not self.force:
            self.assertEqual(http.client.BAD_REQUEST, response.status_code)
            self.assertThat(
                response.content.decode("utf-8"),
                DocTestMatches("...does not belong to the requesting user..."),
            )
        else:
            self.assertEqual(http.client.NO_CONTENT, response.status_code)
            self.assertEqual("", response.content.decode("utf-8"))

    @transactional
    def test_POST_release_allows_admin_to_release_discovered_ip(self):
        # Make an "orphaned" IP address, like the one in bug #1630034.
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED
        )
        response = self.post_release_request(
            str(static_ip.ip), discovered=True
        )
        if self.expect_forbidden:
            self.assertEqual(http.client.FORBIDDEN, response.status_code)
            self.assertEqual(
                "Force-releasing an IP address requires admin privileges.",
                response.content.decode("utf-8"),
            )
        elif not self.force:
            self.assertEqual(http.client.BAD_REQUEST, response.status_code)
            self.assertThat(
                response.content.decode("utf-8"),
                DocTestMatches("...does not belong to the requesting user..."),
            )
        else:
            self.assertEqual(http.client.NO_CONTENT, response.status_code)
            self.assertEqual("", response.content.decode("utf-8"))

    @transactional
    def test_POST_release_allows_admin_to_release_discovered_ip_with_interface(
        self,
    ):
        # Make an "orphaned" IP address, like the one in bug #1898122.
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED
        )
        interface = factory.make_Interface()
        interface.ip_addresses.add(static_ip)

        response = self.post_release_request(
            str(static_ip.ip), discovered=True
        )
        if self.expect_forbidden:
            self.assertEqual(http.client.FORBIDDEN, response.status_code)
            self.assertEqual(
                "Force-releasing an IP address requires admin privileges.",
                response.content.decode("utf-8"),
            )
        elif not self.force:
            self.assertEqual(http.client.BAD_REQUEST, response.status_code)
            self.assertThat(
                response.content.decode("utf-8"),
                DocTestMatches("...does not belong to the requesting user..."),
            )
        else:
            self.assertEqual(http.client.NO_CONTENT, response.status_code)
            self.assertEqual("", response.content.decode("utf-8"))

    @transactional
    def test_POST_release_deallocates_address(self):
        ipaddress = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, user=self.user
        )
        response = self.post_release_request(ipaddress.ip)
        self.assertEqual(
            self.expected_status(http.client.NO_CONTENT),
            response.status_code,
            response.content,
        )
        if not self.expect_forbidden:
            self.assertIsNone(reload_object(ipaddress))

    @transactional
    def test_POST_release_deletes_unknown_interface(self):
        subnet = factory.make_Subnet()
        unknown_nic = factory.make_Interface(INTERFACE_TYPE.UNKNOWN)
        ipaddress = unknown_nic.link_subnet(
            INTERFACE_LINK_TYPE.STATIC,
            subnet,
            alloc_type=IPADDRESS_TYPE.USER_RESERVED,
            user=self.user,
        )
        response = self.post_release_request(ipaddress.ip)
        self.assertEqual(
            self.expected_status(http.client.NO_CONTENT),
            response.status_code,
            response.content,
        )
        if not self.expect_forbidden:
            self.assertIsNone(reload_object(unknown_nic))

    @transactional
    def test_POST_release_does_not_delete_interfaces_linked_to_nodes(self):
        node = factory.make_Node()
        attached_nic = factory.make_Interface(node=node)
        subnet = factory.make_Subnet()
        ipaddress = attached_nic.link_subnet(
            INTERFACE_LINK_TYPE.STATIC,
            subnet,
            alloc_type=IPADDRESS_TYPE.USER_RESERVED,
            user=self.user,
        )

        self.post_release_request(ipaddress.ip)
        self.assertEqual(attached_nic, reload_object(attached_nic))

    @transactional
    def test_POST_release_does_not_delete_other_IPs_I_own(self):
        ipaddress = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, user=self.user
        )
        other_address = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, user=self.user
        )
        response = self.post_release_request(ipaddress.ip)
        self.assertEqual(
            self.expected_status(http.client.NO_CONTENT),
            response.status_code,
            response.content,
        )
        self.assertIsNotNone(reload_object(other_address))


class TestIPAddressesReserveAPI(APITransactionTestCase.ForUser):
    scenarios = (
        ("with_ip_param", {"ip_param": "ip"}),
        ("with_ip_address_param", {"ip_param": "ip_address"}),
    )

    def post_reservation_request(
        self,
        subnet=None,
        ip_address=None,
        network=None,
        mac=None,
        hostname=None,
    ):
        params = {"op": "reserve"}
        if ip_address is not None:
            params[self.ip_param] = ip_address
        if subnet is not None:
            params["subnet"] = subnet.cidr
        if network is not None and subnet is None:
            params["subnet"] = str(network)
        if mac is not None:
            params["mac"] = mac
        if hostname is not None:
            params["hostname"] = hostname
        return self.client.post(reverse("ipaddresses_handler"), params)

    def assertNoMatchingNetworkError(self, response, net):
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        expected = "Unable to identify subnet: %s." % str(net)
        self.assertEqual(
            expected.encode(settings.DEFAULT_CHARSET), response.content
        )

    def test_POST_reserve_creates_ipaddress(self):
        subnet = factory.make_Subnet()
        response = self.post_reservation_request(subnet)
        self.assertEqual(http.client.OK, response.status_code)
        returned_address = json_load_bytes(response.content)
        [staticipaddress] = StaticIPAddress.objects.all()
        # Test that these fields exist, but don't test for exact values.
        del returned_address["created"]
        del returned_address["subnet"]
        del returned_address["interface_set"]
        del returned_address["owner"]
        expected = dict(
            alloc_type=staticipaddress.alloc_type,
            alloc_type_name=staticipaddress.alloc_type_name,
            ip=staticipaddress.ip,
            resource_uri=reverse("ipaddresses_handler"),
        )
        self.assertEqual(expected, returned_address)
        self.assertEqual(
            IPADDRESS_TYPE.USER_RESERVED, staticipaddress.alloc_type
        )
        self.assertEqual(self.user, staticipaddress.user)

    def test_POST_reserve_creates_dnsresource(self):
        # The api doesn't autocreate the domain, so create one now.
        domain = factory.make_Domain()
        hostname = factory.make_name("host")
        fqdn = f"{hostname}.{domain.name}"
        subnet = factory.make_Subnet()
        response = self.post_reservation_request(subnet, hostname=fqdn)
        self.assertEqual(http.client.OK, response.status_code)
        returned_address = json_load_bytes(response.content)
        [staticipaddress] = StaticIPAddress.objects.all()
        # We don't need to test the value of the 'created' datetime
        # field. By removing it, we also test for its presence.
        del returned_address["created"]
        del returned_address["subnet"]
        del returned_address["interface_set"]
        del returned_address["owner"]
        expected = dict(
            alloc_type=staticipaddress.alloc_type,
            alloc_type_name=staticipaddress.alloc_type_name,
            ip=staticipaddress.ip,
            resource_uri=reverse("ipaddresses_handler"),
        )
        self.assertEqual(expected, returned_address)
        self.assertEqual(
            IPADDRESS_TYPE.USER_RESERVED, staticipaddress.alloc_type
        )
        self.assertEqual(self.user, staticipaddress.user)
        dnsrr = DNSResource.objects.get(name=hostname, domain=domain)
        self.assertCountEqual(dnsrr.ip_addresses.all(), [staticipaddress])

    def test_POST_reserve_with_MAC_links_MAC_to_ip_address(self):
        subnet = factory.make_Subnet()
        mac = factory.make_mac_address()

        response = self.post_reservation_request(subnet=subnet, mac=mac)
        self.assertEqual(http.client.OK, response.status_code)
        [staticipaddress] = StaticIPAddress.objects.all()
        self.expectThat(
            staticipaddress.interface_set.first().mac_address, Equals(mac)
        )

    def test_POST_returns_error_when_MAC_exists_on_node(self):
        subnet = factory.make_Subnet()
        nic = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, vlan=subnet.vlan)

        response = self.post_reservation_request(
            subnet=subnet, mac=nic.mac_address
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_POST_allows_claiming_of_new_static_ips_for_existing_MAC(self):
        subnet = factory.make_Subnet()
        nic = factory.make_Interface(INTERFACE_TYPE.UNKNOWN)

        response = self.post_reservation_request(
            subnet=subnet, mac=nic.mac_address
        )
        self.expectThat(response.status_code, Equals(http.client.OK))
        [staticipaddress] = nic.ip_addresses.all()
        self.assertEqual(
            staticipaddress.interface_set.first().mac_address, nic.mac_address
        )

    def test_POST_reserve_errors_for_no_matching_subnet(self):
        network = factory.make_ipv4_network()
        factory.make_Subnet(cidr=str(network.cidr))
        other_net = factory.make_ipv4_network(but_not=[network])
        response = self.post_reservation_request(network=other_net)
        self.assertNoMatchingNetworkError(response, other_net)

    def test_POST_reserve_creates_ip_address(self):
        subnet = factory.make_Subnet()
        ip_in_network = factory.pick_ip_in_Subnet(subnet)
        response = self.post_reservation_request(ip_address=ip_in_network)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        returned_address = json_load_bytes(response.content)
        [staticipaddress] = StaticIPAddress.objects.all()
        self.expectThat(
            returned_address["alloc_type"],
            Equals(IPADDRESS_TYPE.USER_RESERVED),
        )
        self.expectThat(returned_address["ip"], Equals(ip_in_network))
        self.expectThat(staticipaddress.ip, Equals(ip_in_network))

    def test_POST_reserve_ip_address_detects_in_use_address(self):
        subnet = factory.make_Subnet()
        ip_in_network = factory.pick_ip_in_Subnet(subnet)
        response = self.post_reservation_request(subnet, ip_in_network)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        # Do same request again and check it is rejected.
        response = self.post_reservation_request(subnet, ip_in_network)
        self.expectThat(response.status_code, Equals(http.client.NOT_FOUND))
        self.expectThat(
            response.content,
            Equals(
                (
                    "The IP address %s is already in use." % ip_in_network
                ).encode(settings.DEFAULT_CHARSET)
            ),
        )

    def test_POST_reserve_ip_address_rejects_ip_in_dynamic_range(self):
        subnet = factory.make_ipv4_Subnet_with_IPRanges()
        ip = str(IPAddress(subnet.get_dynamic_maasipset().first))
        response = self.post_reservation_request(subnet, ip)
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_POST_reserve_without_hostname_creates_ip_without_hostname(self):
        subnet = factory.make_Subnet()
        response = self.post_reservation_request(subnet=subnet)
        self.assertEqual(http.client.OK, response.status_code)
        [staticipaddress] = StaticIPAddress.objects.all()
        self.expectThat(
            staticipaddress.dnsresource_set.all().count(), Equals(0)
        )

    def test_POST_reserve_with_bad_fqdn_fails(self):
        subnet = factory.make_Subnet()
        hostname = factory.make_hostname()
        domainname = factory.make_name("domain")
        fqdn = f"{hostname}.{domainname}"
        response = self.post_reservation_request(subnet=subnet, hostname=fqdn)
        self.assertEqual(http.client.NOT_FOUND, response.status_code)

    def test_POST_reserve_with_hostname_creates_ip_with_hostname(self):
        subnet = factory.make_Subnet()
        hostname = factory.make_hostname()
        response = self.post_reservation_request(
            subnet=subnet, hostname=hostname
        )
        self.assertEqual(http.client.OK, response.status_code)
        [staticipaddress] = StaticIPAddress.objects.all()
        self.expectThat(
            staticipaddress.dnsresource_set.first().name, Equals(hostname)
        )

    def test_POST_reserve_with_hostname_and_ip_creates_ip_with_hostname(self):
        subnet = factory.make_Subnet()
        hostname = factory.make_hostname()
        ip_in_network = factory.pick_ip_in_Subnet(subnet)
        response = self.post_reservation_request(
            subnet=subnet, ip_address=ip_in_network, hostname=hostname
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        returned_address = json_load_bytes(response.content)
        [staticipaddress] = StaticIPAddress.objects.all()
        self.expectThat(
            returned_address["alloc_type"],
            Equals(IPADDRESS_TYPE.USER_RESERVED),
        )
        self.expectThat(returned_address["ip"], Equals(ip_in_network))
        self.expectThat(staticipaddress.ip, Equals(ip_in_network))
        self.expectThat(
            staticipaddress.dnsresource_set.first().name, Equals(hostname)
        )

    def test_POST_reserve_with_fqdn_creates_ip_with_hostname(self):
        subnet = factory.make_Subnet()
        hostname = factory.make_hostname()
        domainname = factory.make_Domain().name
        fqdn = f"{hostname}.{domainname}"
        response = self.post_reservation_request(
            subnet=subnet, hostname=f"{hostname}.{domainname}"
        )
        self.assertEqual(http.client.OK, response.status_code)
        [staticipaddress] = StaticIPAddress.objects.all()
        self.expectThat(
            staticipaddress.dnsresource_set.first().name, Equals(hostname)
        )
        self.expectThat(
            staticipaddress.dnsresource_set.first().fqdn, Equals(fqdn)
        )

    def test_POST_reserve_with_fqdn_and_ip_creates_ip_with_hostname(self):
        subnet = factory.make_Subnet()
        hostname = factory.make_hostname()
        domainname = factory.make_Domain().name
        fqdn = f"{hostname}.{domainname}"
        ip_in_network = factory.pick_ip_in_Subnet(subnet)
        response = self.post_reservation_request(
            subnet=subnet,
            ip_address=ip_in_network,
            hostname=f"{hostname}.{domainname}",
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        returned_address = json_load_bytes(response.content)
        [staticipaddress] = StaticIPAddress.objects.all()
        self.expectThat(
            returned_address["alloc_type"],
            Equals(IPADDRESS_TYPE.USER_RESERVED),
        )
        self.expectThat(returned_address["ip"], Equals(ip_in_network))
        self.expectThat(staticipaddress.ip, Equals(ip_in_network))
        self.expectThat(
            staticipaddress.dnsresource_set.first().fqdn, Equals(fqdn)
        )

    def test_POST_reserve_with_no_parameters_fails_with_bad_request(self):
        response = self.post_reservation_request()
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_POST_reserve_rejects_invalid_ip(self):
        response = self.post_reservation_request(ip_address="1690.254.0.1")
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertEqual(
            dict(ip_address=["Enter a valid IPv4 or IPv6 address."]),
            json_load_bytes(response.content),
        )
