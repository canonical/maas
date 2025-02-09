# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from random import randint, shuffle
import threading
from unittest import TestCase
from unittest.mock import call, sentinel

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from netaddr import IPAddress
from psycopg2.errorcodes import FOREIGN_KEY_VIOLATION
from twisted.python.failure import Failure

from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_WORKFLOW_NAME,
    ConfigureDHCPParam,
)
from maasserver import locks
from maasserver.enum import (
    INTERFACE_LINK_TYPE,
    INTERFACE_TYPE,
    IPADDRESS_FAMILY,
    IPADDRESS_TYPE,
    IPADDRESS_TYPE_CHOICES_DICT,
    IPRANGE_TYPE,
)
from maasserver.exceptions import (
    StaticIPAddressExhaustion,
    StaticIPAddressOutOfRange,
    StaticIPAddressUnavailable,
)
from maasserver.models import staticipaddress as static_ip_address_module
from maasserver.models.config import Config
from maasserver.models.domain import Domain
from maasserver.models.staticipaddress import (
    HostnameIPMapping,
    StaticIPAddress,
)
from maasserver.models.subnet import Subnet
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils import orm
from maasserver.utils.dns import (
    get_iface_name_based_hostname,
    get_ip_based_hostname,
)
from maasserver.utils.orm import (
    post_commit_hooks,
    reload_object,
    transactional,
)
from maasserver.websockets.base import dehydrate_datetime


class TestStaticIPAddressManager(MAASServerTestCase):
    def test_filter_by_ip_family_ipv4(self):
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(cidr=str(network_v4.cidr))
        ip_v4 = factory.pick_ip_in_network(network_v4)
        ip_v4 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=ip_v4, subnet=subnet_v4
        )
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(cidr=str(network_v6.cidr))
        ip_v6 = factory.pick_ip_in_network(network_v6)
        ip_v6 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=ip_v6, subnet=subnet_v6
        )
        self.assertCountEqual(
            [ip_v4],
            StaticIPAddress.objects.filter_by_ip_family(IPADDRESS_FAMILY.IPv4),
        )

    def test_filter_by_ip_family_ipv6(self):
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(cidr=str(network_v4.cidr))
        ip_v4 = factory.pick_ip_in_network(network_v4)
        ip_v4 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=ip_v4, subnet=subnet_v4
        )
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(cidr=str(network_v6.cidr))
        ip_v6 = factory.pick_ip_in_network(network_v6)
        ip_v6 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=ip_v6, subnet=subnet_v6
        )
        self.assertCountEqual(
            [ip_v6],
            StaticIPAddress.objects.filter_by_ip_family(IPADDRESS_FAMILY.IPv6),
        )

    def test_allocate_new_returns_ip_in_correct_range(self):
        subnet = factory.make_managed_Subnet()
        with post_commit_hooks:
            ipaddress = StaticIPAddress.objects.allocate_new(subnet)
        self.assertIsInstance(ipaddress, StaticIPAddress)
        self.assertTrue(
            subnet.is_valid_static_ip(ipaddress.ip),
            "%s: not valid for subnet with reserved IPs: %r"
            % (ipaddress.ip, subnet.get_ipranges_in_use()),
        )

    def test_allocate_new_allocates_IPv6_address(self):
        subnet = factory.make_managed_Subnet(ipv6=True)

        with post_commit_hooks:
            ipaddress = StaticIPAddress.objects.allocate_new(subnet)

        self.assertIsInstance(ipaddress, StaticIPAddress)
        self.assertTrue(subnet.is_valid_static_ip(ipaddress.ip))

    def test_allocate_new_sets_user(self):
        subnet = factory.make_managed_Subnet()
        user = factory.make_User()

        with post_commit_hooks:
            ipaddress = StaticIPAddress.objects.allocate_new(
                subnet=subnet,
                alloc_type=IPADDRESS_TYPE.USER_RESERVED,
                user=user,
            )

        self.assertEqual(user, ipaddress.user)

    def test_allocate_new_with_user_disallows_wrong_alloc_types(self):
        subnet = factory.make_managed_Subnet()
        user = factory.make_User()
        alloc_type = factory.pick_enum(
            IPADDRESS_TYPE,
            but_not=[
                IPADDRESS_TYPE.DHCP,
                IPADDRESS_TYPE.DISCOVERED,
                IPADDRESS_TYPE.USER_RESERVED,
            ],
        )
        self.assertRaises(
            AssertionError,
            StaticIPAddress.objects.allocate_new,
            subnet,
            user=user,
            alloc_type=alloc_type,
        )

    def test_allocate_new_with_reserved_type_requires_a_user(self):
        subnet = factory.make_managed_Subnet()
        self.assertRaises(
            AssertionError,
            StaticIPAddress.objects.allocate_new,
            subnet,
            alloc_type=IPADDRESS_TYPE.USER_RESERVED,
        )

    def test_allocate_new_returns_lowest_available_ip(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24", gateway_ip="10.0.0.1")
        factory.make_IPRange(subnet, "10.0.0.101", "10.0.0.254")
        factory.make_IPRange(subnet, "10.0.0.2", "10.0.0.97")
        factory.make_StaticIPAddress("10.0.0.99", subnet=subnet)
        subnet = reload_object(subnet)
        with post_commit_hooks:
            ipaddress = StaticIPAddress.objects.allocate_new(subnet)
        self.assertEqual(ipaddress.ip, "10.0.0.98")

    def test_allocate_new_returns_requested_IP_if_available(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")

        with post_commit_hooks:
            ipaddress = StaticIPAddress.objects.allocate_new(
                subnet,
                factory.pick_enum(
                    IPADDRESS_TYPE,
                    but_not=[
                        IPADDRESS_TYPE.DHCP,
                        IPADDRESS_TYPE.DISCOVERED,
                        IPADDRESS_TYPE.USER_RESERVED,
                    ],
                ),
                requested_address="10.0.0.1",
            )
        self.assertEqual("10.0.0.1", ipaddress.ip)

    def test_allocate_new_raises_when_requested_IP_unavailable(self):
        subnet = factory.make_ipv4_Subnet_with_IPRanges()
        with post_commit_hooks:
            requested_address = StaticIPAddress.objects.allocate_new(
                subnet,
                factory.pick_enum(
                    IPADDRESS_TYPE,
                    but_not=[
                        IPADDRESS_TYPE.DHCP,
                        IPADDRESS_TYPE.DISCOVERED,
                        IPADDRESS_TYPE.USER_RESERVED,
                    ],
                ),
            ).ip

        self.assertRaises(
            StaticIPAddressUnavailable,
            StaticIPAddress.objects.allocate_new,
            subnet,
            requested_address=requested_address,
        )

    def test_allocate_new_raises_when_requested_IP_out_of_network(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        requested_address = "10.0.1.1"
        e = self.assertRaises(
            StaticIPAddressOutOfRange,
            StaticIPAddress.objects.allocate_new,
            subnet,
            factory.pick_enum(
                IPADDRESS_TYPE,
                but_not=[
                    IPADDRESS_TYPE.DHCP,
                    IPADDRESS_TYPE.DISCOVERED,
                    IPADDRESS_TYPE.USER_RESERVED,
                ],
            ),
            requested_address=requested_address,
        )
        self.assertEqual(
            "%s is not within subnet CIDR: %s"
            % (requested_address, str(subnet.get_ipnetwork())),
            str(e),
        )

    def test_allocate_new_raises_when_requested_IP_in_dynamic_range(self):
        subnet = factory.make_ipv4_Subnet_with_IPRanges()
        dynamic_range = subnet.get_dynamic_ranges().first()
        requested_address = str(IPAddress(dynamic_range.netaddr_iprange.first))
        dynamic_range_end = str(IPAddress(dynamic_range.netaddr_iprange.last))
        subnet = reload_object(subnet)
        e = self.assertRaises(
            StaticIPAddressUnavailable,
            StaticIPAddress.objects.allocate_new,
            subnet,
            factory.pick_enum(
                IPADDRESS_TYPE,
                but_not=[
                    IPADDRESS_TYPE.DHCP,
                    IPADDRESS_TYPE.DISCOVERED,
                    IPADDRESS_TYPE.USER_RESERVED,
                ],
            ),
            requested_address=requested_address,
        )
        self.assertEqual(
            "%s is within the dynamic range from %s to %s"
            % (requested_address, requested_address, dynamic_range_end),
            str(e),
        )

    def test_allocate_new_raises_when_alloc_type_is_None(self):
        error = self.assertRaises(
            ValueError,
            StaticIPAddress.objects.allocate_new,
            sentinel.subnet,
            alloc_type=None,
        )
        self.assertEqual(
            "IP address type None is not allowed to use allocate_new.",
            str(error),
        )

    def test_allocate_new_raises_when_alloc_type_is_not_allowed(self):
        error = self.assertRaises(
            ValueError,
            StaticIPAddress.objects.allocate_new,
            sentinel.subnet,
            alloc_type=IPADDRESS_TYPE.DHCP,
        )
        self.assertEqual(
            "IP address type 5 is not allowed to use allocate_new.", str(error)
        )

    def test_allocate_new_raises_when_addresses_exhausted(self):
        network = "192.168.230.0/24"
        subnet = factory.make_Subnet(cidr=network)
        factory.make_IPRange(
            subnet,
            "192.168.230.1",
            "192.168.230.254",
            alloc_type=IPRANGE_TYPE.RESERVED,
        )
        e = self.assertRaises(
            StaticIPAddressExhaustion,
            StaticIPAddress.objects.allocate_new,
            subnet,
        )
        self.assertEqual(
            "No more IPs available in subnet: %s." % subnet.cidr, str(e)
        )

    def test_allocate_new_requests_retry_when_free_address_taken(self):
        set_ip_address = self.patch(StaticIPAddress, "set_ip_address")
        set_ip_address.side_effect = orm.make_unique_violation()
        with orm.retry_context:
            # A retry has been requested.
            self.assertRaises(
                orm.RetryTransaction,
                StaticIPAddress.objects.allocate_new,
                subnet=factory.make_managed_Subnet(),
            )
            # Aquisition of `address_allocation` is pending.
            self.assertEqual(
                [locks.address_allocation],
                list(orm.retry_context.stack._cm_pending),
            )

    def test_allocate_new_propagates_other_integrity_errors(self):
        set_ip_address = self.patch(StaticIPAddress, "set_ip_address")
        set_ip_address.side_effect = orm.make_unique_violation()
        set_ip_address.side_effect.__cause__.pgcode = FOREIGN_KEY_VIOLATION
        with orm.retry_context:
            # An integrity error that's not `UNIQUE_VIOLATION` is propagated.
            self.assertRaises(
                IntegrityError,
                StaticIPAddress.objects.allocate_new,
                subnet=factory.make_managed_Subnet(),
            )
            # There is no pending retry context.
            self.assertEqual(len(orm.retry_context.stack._cm_pending), 0)

    def test_allocate_new_returns_requested_IP_without_validation(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        factory.make_IPRange(
            subnet,
            "10.0.0.101",
            "10.0.0.254",
            alloc_type=IPRANGE_TYPE.RESERVED,
        )

        with post_commit_hooks:
            ipaddress = StaticIPAddress.objects.allocate_new(
                subnet,
                requested_address="10.0.0.101",
                restrict_ip_to_unreserved_ranges=False,
            )

        self.assertEqual("10.0.0.101", ipaddress.ip)


class TestStaticIPAddressManagerTransactional(MAASTransactionServerTestCase):
    """Transactional tests for `StaticIPAddressManager."""

    scenarios = (("IPv4", dict(ip_version=4)), ("IPv6", dict(ip_version=6)))

    def test_allocate_new_works_under_extreme_concurrency(self):
        self.patch(static_ip_address_module, "post_commit_do")
        ipv6 = self.ip_version == 6
        subnet = factory.make_managed_Subnet(ipv6=ipv6)
        count = 20  # Allocate this number of IP addresses.
        concurrency = threading.Semaphore(16)
        mutex = threading.Lock()
        results = []

        @transactional
        def allocate():
            return StaticIPAddress.objects.allocate_new(subnet)

        def allocate_one():
            try:
                with concurrency:
                    sip = allocate()
            except Exception:
                failure = Failure()
                with mutex:
                    results.append(failure)
            else:
                with mutex:
                    results.append(sip)

        threads = [threading.Thread(target=allocate_one) for _ in range(count)]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        for result in results:
            self.assertIsInstance(result, StaticIPAddress)
        ips = {sip.ip for sip in results}
        self.assertEqual(len(ips), count)
        for ip in ips:
            self.assertTrue(subnet.is_valid_static_ip(ip))


class TestStaticIPAddressManagerMapping(MAASServerTestCase):
    def test_get_hostname_ip_mapping_returns_mapping(self):
        domain = Domain.objects.get_default_domain()
        expected_mapping = {}
        for _ in range(3):
            node = factory.make_Node(interface=True)
            boot_interface = node.get_boot_interface()
            subnet = factory.make_Subnet()
            staticip = factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.STICKY,
                ip=factory.pick_ip_in_Subnet(subnet),
                subnet=subnet,
                interface=boot_interface,
            )
            full_hostname = f"{node.hostname}.{domain.name}"
            expected_mapping[full_hostname] = HostnameIPMapping(
                node.system_id, 30, {staticip.ip}, node.node_type
            )
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(domain)
        self.assertEqual(expected_mapping, mapping)

    def test_get_hostname_ip_mapping_includes_user_id(self):
        user = factory.make_User()
        domain = Domain.objects.get_default_domain()
        node_name = factory.make_name("node")
        node = factory.make_Node(
            hostname=node_name, domain=domain, owner=user, interface=True
        )
        boot_interface = node.get_boot_interface()
        subnet = factory.make_Subnet()
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=boot_interface,
            user=user,
        )
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(domain)
        fqdn = f"{node.hostname}.{domain.name}"
        self.assertEqual(mapping[fqdn].user_id, user.id)

    def test_get_hostname_ip_mapping_returns_all_mappings_for_subnet(self):
        domain = Domain.objects.get_default_domain()
        expected_mapping = {}
        for _ in range(3):
            node = factory.make_Node(interface=True)
            boot_interface = node.get_boot_interface()
            subnet = factory.make_Subnet()
            staticip = factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.STICKY,
                ip=factory.pick_ip_in_Subnet(subnet),
                subnet=subnet,
                interface=boot_interface,
            )
            full_hostname = f"{node.hostname}.{domain.name}"
            expected_mapping[full_hostname] = HostnameIPMapping(
                node.system_id, 30, {staticip.ip}, node.node_type
            )
        # See also LP#1600259.  It doesn't matter what subnet is passed in, you
        # get all of them.
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            Subnet.objects.first()
        )
        self.assertEqual(expected_mapping, mapping)

    def test_get_hostname_ip_mapping_only_node_current_interfaces(self):
        domain = Domain.objects.get_default_domain()
        node = factory.make_Node()
        other_node_config = factory.make_NodeConfig(
            node=node, name="deployment"
        )
        interface1 = factory.make_Interface(node_config=node.current_config)
        interface2 = factory.make_Interface(node_config=other_node_config)
        subnet = factory.make_Subnet()
        staticip1 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=interface1,
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=interface2,
        )
        self.assertEqual(
            dict(StaticIPAddress.objects.get_hostname_ip_mapping(subnet)),
            {
                f"{node.hostname}.{domain.name}": HostnameIPMapping(
                    node.system_id, 30, {staticip1.ip}, node.node_type
                ),
            },
        )

    def test_get_hostname_ip_mapping_ip_order(self):
        domain = Domain.objects.get_default_domain()
        node = factory.make_Node()
        interface1 = factory.make_Interface(node_config=node.current_config)
        subnet = factory.make_Subnet()
        staticip1 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=interface1,
        )
        staticip2 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=interface1,
        )
        self.assertEqual(
            dict(StaticIPAddress.objects.get_hostname_ip_mapping(subnet)),
            {
                f"{node.hostname}.{domain.name}": HostnameIPMapping(
                    node.system_id, 30, {staticip1.ip}, node.node_type
                ),
                f"{interface1.name}.{node.hostname}.{domain.name}": HostnameIPMapping(
                    node.system_id, 30, {staticip2.ip}, node.node_type
                ),
            },
        )

    def test_get_hostname_ip_mapping_returns_fqdn_and_other(self):
        hostname = factory.make_name("hostname")
        domainname = factory.make_name("domain")
        factory.make_Domain(name=domainname)
        full_hostname = f"{hostname}.{domainname}"
        subnet = factory.make_Subnet()
        node = factory.make_Node_with_Interface_on_Subnet(
            interface=True,
            hostname=full_hostname,
            interface_count=3,
            subnet=subnet,
        )
        boot_interface = node.get_boot_interface()
        staticip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=boot_interface,
        )
        iface2 = node.current_config.interface_set.exclude(
            id=boot_interface.id
        ).first()
        sip2 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=iface2,
        )
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(subnet)
        expected = {
            full_hostname: HostnameIPMapping(
                node.system_id, 30, {staticip.ip}, node.node_type
            ),
            "%s.%s" % (iface2.name, full_hostname): HostnameIPMapping(
                node.system_id, 30, {sip2.ip}, node.node_type
            ),
        }
        self.assertEqual(expected, mapping)

    def test_get_hostname_ip_mapping_sanitized_iface_name(self):
        hostname = factory.make_name("hostname")
        domainname = factory.make_name("domain")
        factory.make_Domain(name=domainname)
        full_hostname = f"{hostname}.{domainname}"
        subnet = factory.make_Subnet()
        node = factory.make_Node_with_Interface_on_Subnet(
            extra_ifnames=["eth_1"],
            hostname=full_hostname,
            interface_count=2,
            subnet=subnet,
        )
        boot_interface = node.get_boot_interface()
        staticip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=boot_interface,
        )
        iface2 = node.current_config.interface_set.exclude(
            id=boot_interface.id
        ).first()
        sip2 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=iface2,
        )
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(subnet)
        sanitized_if2name = get_iface_name_based_hostname(iface2.name)
        expected = {
            full_hostname: HostnameIPMapping(
                node.system_id, 30, {staticip.ip}, node.node_type
            ),
            "%s.%s" % (sanitized_if2name, full_hostname): HostnameIPMapping(
                node.system_id, 30, {sip2.ip}, node.node_type
            ),
        }
        self.assertEqual(expected, mapping)

    def make_mapping(self, node, raw_ttl=False):
        if raw_ttl or node.address_ttl is not None:
            ttl = node.address_ttl
        elif node.domain.ttl is not None:
            ttl = node.domain.ttl
        else:
            ttl = Config.objects.get_config("default_dns_ttl")
        mapping = HostnameIPMapping(
            system_id=node.system_id, node_type=node.node_type, ttl=ttl
        )
        for ip in node.boot_interface.ip_addresses.exclude(ip=None):
            mapping.ips.add(str(ip.ip))
        return {node.fqdn: mapping}

    def test_get_hostname_ip_mapping_inherits_ttl(self):
        # We create 2 domains, one with a ttl, one withoout.
        # Within each domain, create a node with an address_ttl, and one
        # without.
        global_ttl = randint(1, 99)
        Config.objects.set_config("default_dns_ttl", global_ttl)
        domains = [
            factory.make_Domain(),
            factory.make_Domain(ttl=randint(100, 199)),
        ]
        subnet = factory.make_Subnet(host_bits=randint(4, 15))
        for dom in domains:
            for ttl in (None, randint(200, 299)):
                node = factory.make_Node_with_Interface_on_Subnet(
                    interface=True,
                    hostname="%s.%s"
                    % (factory.make_name("hostname"), dom.name),
                    subnet=subnet,
                    address_ttl=ttl,
                )
                boot_interface = node.get_boot_interface()
                factory.make_StaticIPAddress(
                    alloc_type=IPADDRESS_TYPE.STICKY,
                    ip=factory.pick_ip_in_Subnet(subnet),
                    subnet=subnet,
                    interface=boot_interface,
                )
            expected_mapping = {}
            for node in dom.node_set.all():
                expected_mapping.update(self.make_mapping(node))
            actual = StaticIPAddress.objects.get_hostname_ip_mapping(dom)
            self.assertEqual(expected_mapping, actual)

    def test_get_hostname_ip_mapping_returns_raw_ttl(self):
        # We create 2 domains, one with a ttl, one withoout.
        # Within each domain, create a node with an address_ttl, and one
        # without.
        # We then query with raw_ttl=True, and confirm that nothing is
        # inherited.
        global_ttl = randint(1, 99)
        Config.objects.set_config("default_dns_ttl", global_ttl)
        domains = [
            factory.make_Domain(),
            factory.make_Domain(ttl=randint(100, 199)),
        ]
        subnet = factory.make_Subnet()
        for dom in domains:
            for ttl in (None, randint(200, 299)):
                node = factory.make_Node_with_Interface_on_Subnet(
                    interface=True,
                    hostname="%s.%s"
                    % (factory.make_name("hostname"), dom.name),
                    subnet=subnet,
                    address_ttl=ttl,
                )
                boot_interface = node.get_boot_interface()
                factory.make_StaticIPAddress(
                    alloc_type=IPADDRESS_TYPE.STICKY,
                    ip=factory.pick_ip_in_Subnet(subnet),
                    subnet=subnet,
                    interface=boot_interface,
                )
            expected_mapping = {}
            for node in dom.node_set.all():
                expected_mapping.update(self.make_mapping(node, raw_ttl=True))
            actual = StaticIPAddress.objects.get_hostname_ip_mapping(
                dom, raw_ttl=True
            )
            self.assertEqual(expected_mapping, actual)

    def test_get_hostname_ip_mapping_picks_mac_with_static_address(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=factory.make_name("host")
        )
        boot_interface = node.get_boot_interface()
        subnet = boot_interface.ip_addresses.first().subnet
        nic2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=boot_interface.vlan
        )
        staticip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, interface=nic2, subnet=subnet
        )
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(node.domain)
        self.assertEqual(
            {
                node.fqdn: HostnameIPMapping(
                    node.system_id, 30, {staticip.ip}, node.node_type
                )
            },
            mapping,
        )

    def test_get_hostname_ip_mapping_considers_given_domain(self):
        domain = factory.make_Domain()
        factory.make_Node_with_Interface_on_Subnet(domain=domain)
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(
            factory.make_Domain()
        )
        self.assertEqual({}, mapping)

    def test_get_hostname_ip_mapping_picks_oldest_nic_with_sticky_ip(self):
        subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr)
        )
        node = factory.make_Node(
            interface=True, hostname=factory.make_name("host")
        )
        boot_interface = node.get_boot_interface()
        staticip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=subnet,
            interface=boot_interface,
        )
        newer_nic = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        newer_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=subnet,
            interface=newer_nic,
        )
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(node.domain)
        expected_mapping = {
            node.fqdn: HostnameIPMapping(
                node.system_id, 30, {staticip.ip}, node.node_type
            ),
            "%s.%s" % (newer_nic.name, node.fqdn): HostnameIPMapping(
                node.system_id, 30, {newer_ip.ip}, node.node_type
            ),
        }
        self.assertEqual(expected_mapping, mapping)

    def test_get_hostname_ip_mapping_picks_sticky_over_auto(self):
        subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr)
        )
        node = factory.make_Node(
            interface=True, hostname=factory.make_name("host")
        )
        boot_interface = node.get_boot_interface()
        staticip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=subnet,
            interface=boot_interface,
        )
        nic = node.get_boot_interface()  # equals boot_interface
        auto_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, subnet=subnet, interface=nic
        )
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(node.domain)
        expected_mapping = {
            node.fqdn: HostnameIPMapping(
                node.system_id, 30, {staticip.ip}, node.node_type
            ),
            "%s.%s" % (nic.name, node.fqdn): HostnameIPMapping(
                node.system_id, 30, {auto_ip.ip}, node.node_type
            ),
        }
        self.assertEqual(expected_mapping, mapping)

    def test_get_hostname_ip_mapping_combines_IPv4_and_IPv6_addresses(self):
        node = factory.make_Node(interface=True)
        interface = node.get_boot_interface()
        ipv4_network = factory.make_ipv4_network()
        ipv4_subnet = factory.make_Subnet(cidr=ipv4_network)
        ipv4_address = factory.make_StaticIPAddress(
            interface=interface,
            ip=factory.pick_ip_in_network(ipv4_network),
            subnet=ipv4_subnet,
        )
        ipv6_network = factory.make_ipv6_network()
        ipv6_subnet = factory.make_Subnet(cidr=ipv6_network)
        ipv6_address = factory.make_StaticIPAddress(
            interface=interface,
            ip=factory.pick_ip_in_network(ipv6_network),
            subnet=ipv6_subnet,
        )
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(node.domain)
        self.assertEqual(
            {
                node.fqdn: HostnameIPMapping(
                    node.system_id,
                    30,
                    {ipv4_address.ip, ipv6_address.ip},
                    node.node_type,
                )
            },
            mapping,
        )

    def test_get_hostname_ip_mapping_combines_MACs_for_same_node(self):
        # A node's preferred static IPv4 and IPv6 addresses may be on
        # different MACs.
        node = factory.make_Node()
        ipv4_network = factory.make_ipv4_network()
        ipv4_subnet = factory.make_Subnet(cidr=ipv4_network)
        ipv4_address = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            interface=factory.make_Interface(
                INTERFACE_TYPE.PHYSICAL, node=node
            ),
            ip=factory.pick_ip_in_network(ipv4_network),
            subnet=ipv4_subnet,
        )
        ipv6_network = factory.make_ipv6_network()
        ipv6_subnet = factory.make_Subnet(cidr=ipv6_network)
        ipv6_address = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            interface=factory.make_Interface(
                INTERFACE_TYPE.PHYSICAL, node=node
            ),
            ip=factory.pick_ip_in_network(ipv6_network),
            subnet=ipv6_subnet,
        )
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(node.domain)
        self.assertEqual(
            {
                node.fqdn: HostnameIPMapping(
                    node.system_id,
                    30,
                    {ipv4_address.ip, ipv6_address.ip},
                    node.node_type,
                )
            },
            mapping,
        )

    def test_get_hostname_ip_mapping_prefers_non_discovered_addresses(self):
        subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr)
        )
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=factory.make_name("host"), subnet=subnet
        )
        iface = node.get_boot_interface()
        staticip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, interface=iface, subnet=subnet
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
            interface=iface,
            subnet=subnet,
        )
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(node.domain)
        expected_mapping = {
            node.fqdn: HostnameIPMapping(
                node.system_id, 30, {staticip.ip}, node.node_type
            )
        }
        self.assertEqual(expected_mapping, mapping)

    def test_get_hostname_ip_mapping_ignores_temp_ip_address(self):
        subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr)
        )
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=factory.make_name("host"), subnet=subnet
        )
        iface = node.get_boot_interface()
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            interface=iface,
            subnet=subnet,
            temp_expires_on=timezone.now(),
        )
        otherip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
            interface=iface,
            subnet=subnet,
        )
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(node.domain)
        expected_mapping = {
            node.fqdn: HostnameIPMapping(
                node.system_id, 30, {otherip.ip}, node.node_type
            )
        }
        self.assertEqual(expected_mapping, mapping)

    def test_get_hostname_ip_mapping_prefers_non_ula_addresses(self):
        subnet = factory.make_Subnet(cidr="2001:db8::/64")
        ula_subnet = factory.make_Subnet(
            cidr="fdd7:39:2::/48", vlan=subnet.vlan
        )
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=factory.make_name("host"), subnet=subnet
        )
        iface = node.get_boot_interface()
        staticip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, interface=iface, subnet=subnet
        )
        ula_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, interface=iface, subnet=ula_subnet
        )
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(node.domain)
        expected_mapping = {
            node.fqdn: HostnameIPMapping(
                node.system_id, 30, {staticip.ip}, node.node_type
            ),
            "%s.%s" % (iface.name, node.fqdn): HostnameIPMapping(
                node.system_id, 30, {ula_ip.ip}, node.node_type
            ),
        }
        self.assertEqual(expected_mapping, mapping)

    def test_get_hostname_ip_mapping_prefers_bond_with_no_boot_interface(self):
        subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr)
        )
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=factory.make_name("host"), subnet=subnet
        )
        node.boot_interface = None

        with post_commit_hooks:
            node.save()
        iface = node.get_boot_interface()
        iface2 = factory.make_Interface(node=node)
        iface3 = factory.make_Interface(node=node, vlan=iface2.vlan)
        bondif = factory.make_Interface(
            INTERFACE_TYPE.BOND, node=node, parents=[iface2, iface3]
        )
        iface_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=iface, subnet=subnet
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=iface2, subnet=subnet
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=iface3, subnet=subnet
        )
        bond_staticip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=bondif, subnet=subnet
        )
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(node.domain)
        expected_mapping = {
            node.fqdn: HostnameIPMapping(
                node.system_id, 30, {bond_staticip.ip}, node.node_type
            ),
            "%s.%s" % (iface.name, node.fqdn): HostnameIPMapping(
                node.system_id, 30, {iface_ip.ip}, node.node_type
            ),
        }
        self.assertEqual(expected_mapping, mapping)

    def test_get_hostname_ip_mapping_prefers_bond_with_boot_interface(self):
        subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr)
        )
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=factory.make_name("host"), subnet=subnet
        )
        iface = node.get_boot_interface()
        iface2 = factory.make_Interface(node=node, vlan=iface.vlan)
        bondif = factory.make_Interface(
            INTERFACE_TYPE.BOND, node=node, parents=[iface, iface2]
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=iface, subnet=subnet
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=iface2, subnet=subnet
        )
        bond_staticip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=bondif, subnet=subnet
        )
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(node.domain)
        expected_mapping = {
            node.fqdn: HostnameIPMapping(
                node.system_id, 30, {bond_staticip.ip}, node.node_type
            )
        }
        self.assertEqual(expected_mapping, mapping)

    def test_get_hostname_ip_mapping_ignores_bond_without_boot_interface(self):
        subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr)
        )
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=factory.make_name("host"), subnet=subnet
        )
        iface = node.get_boot_interface()
        iface2 = factory.make_Interface(node=node)
        iface3 = factory.make_Interface(node=node, vlan=iface2.vlan)
        bondif = factory.make_Interface(
            INTERFACE_TYPE.BOND, node=node, parents=[iface2, iface3]
        )
        boot_staticip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=iface, subnet=subnet
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=iface2, subnet=subnet
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=iface3, subnet=subnet
        )
        bondip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=bondif, subnet=subnet
        )
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(node.domain)
        expected_mapping = {
            node.fqdn: HostnameIPMapping(
                node.system_id, 30, {boot_staticip.ip}, node.node_type
            ),
            "%s.%s" % (bondif.name, node.fqdn): HostnameIPMapping(
                node.system_id, 30, {bondip.ip}, node.node_type
            ),
        }
        self.assertEqual(expected_mapping, mapping)

    def test_get_hostname_ip_mapping_prefers_boot_interface(self):
        subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr)
        )
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=factory.make_name("host"), subnet=subnet
        )
        iface = node.get_boot_interface()
        iface_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=iface, subnet=subnet
        )
        new_boot_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node
        )
        node.boot_interface = new_boot_interface
        node.save()
        # IP address should be selected over the other physical IP address.
        boot_sip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            interface=new_boot_interface,
            subnet=subnet,
        )
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(node.domain)
        expected_mapping = {
            node.fqdn: HostnameIPMapping(
                node.system_id, 30, {boot_sip.ip}, node.node_type
            ),
            "%s.%s" % (iface.name, node.fqdn): HostnameIPMapping(
                node.system_id, 30, {iface_ip.ip}, node.node_type
            ),
        }
        self.assertEqual(expected_mapping, mapping)

    def test_get_hostname_ip_mapping_prefers_boot_interface_to_alias(self):
        subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr)
        )
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=factory.make_name("host"), subnet=subnet
        )
        iface = node.get_boot_interface()
        iface_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=iface, subnet=subnet
        )
        new_boot_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node
        )
        node.boot_interface = new_boot_interface
        node.save()
        # IP address should be selected over the other STICKY IP address.
        boot_sip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            interface=new_boot_interface,
            subnet=subnet,
        )
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(node.domain)
        expected_mapping = {
            node.fqdn: HostnameIPMapping(
                node.system_id, 30, {boot_sip.ip}, node.node_type
            ),
            "%s.%s" % (iface.name, node.fqdn): HostnameIPMapping(
                node.system_id, 30, {iface_ip.ip}, node.node_type
            ),
        }
        self.assertEqual(expected_mapping, mapping)

    def test_get_hostname_ip_mapping_prefers_physical_interfaces_to_vlan(self):
        subnet = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr)
        )
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=factory.make_name("host"), subnet=subnet
        )
        iface = node.get_boot_interface()
        vlanif = factory.make_Interface(
            INTERFACE_TYPE.VLAN, node=node, parents=[iface]
        )
        phy_staticip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=iface, subnet=subnet
        )
        vlanip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=vlanif, subnet=subnet
        )
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(node.domain)
        expected_mapping = {
            node.fqdn: HostnameIPMapping(
                node.system_id, 30, {phy_staticip.ip}, node.node_type
            ),
            "%s.%s"
            % (
                get_iface_name_based_hostname(vlanif.name),
                node.fqdn,
            ): HostnameIPMapping(
                node.system_id, 30, {vlanip.ip}, node.node_type
            ),
        }
        self.assertEqual(expected_mapping, mapping)

    def test_get_hostname_ip_mapping_prefers_bridged_bond_pxe_interface(self):
        subnet = factory.make_Subnet(
            cidr="10.0.0.0/24", dns_servers=[], gateway_ip="10.0.0.1"
        )
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname="host", subnet=subnet
        )
        eth0 = node.get_boot_interface()
        eth0.name = "eth0"
        with post_commit_hooks:
            eth0.save()

        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, name="eth1", vlan=subnet.vlan
        )
        eth2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, name="eth2", vlan=subnet.vlan
        )
        node.boot_interface = eth1
        node.save()
        bond0 = factory.make_Interface(
            INTERFACE_TYPE.BOND, node=node, parents=[eth1, eth2], name="bond0"
        )
        br_bond0 = factory.make_Interface(
            INTERFACE_TYPE.BRIDGE, parents=[bond0], name="br-bond0"
        )
        phy_staticip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            interface=eth0,
            subnet=subnet,
            ip="10.0.0.2",
        )
        bridge_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            interface=br_bond0,
            subnet=subnet,
            ip="10.0.0.3",
        )
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(node.domain)
        expected_mapping = {
            node.fqdn: HostnameIPMapping(
                node.system_id, 30, {bridge_ip.ip}, node.node_type
            ),
            f"{eth0.name}.{node.fqdn}": HostnameIPMapping(
                node.system_id, 30, {phy_staticip.ip}, node.node_type
            ),
        }
        self.assertEqual(mapping, expected_mapping)

    def test_get_hostname_ip_mapping_with_v4_and_v6_and_bridged_bonds(self):
        subnet_v4 = factory.make_Subnet(
            cidr=str(factory.make_ipv4_network().cidr)
        )
        subnet_v6 = factory.make_Subnet(cidr="2001:db8::/64")
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname="host", subnet=subnet_v4
        )
        eth0 = node.get_boot_interface()
        eth0.name = "eth0"

        with post_commit_hooks:
            eth0.save()

        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, name="eth1"
        )
        eth2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, name="eth2"
        )
        node.boot_interface = eth1
        node.save()
        bond0 = factory.make_Interface(
            INTERFACE_TYPE.BOND, node=node, parents=[eth1, eth2], name="bond0"
        )
        br_bond0 = factory.make_Interface(
            INTERFACE_TYPE.BRIDGE, parents=[bond0], name="br-bond0"
        )
        phy_staticip_v4 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=eth0, subnet=subnet_v4
        )
        bridge_ip_v4 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            interface=br_bond0,
            subnet=subnet_v4,
        )
        phy_staticip_v6 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=eth0, subnet=subnet_v6
        )
        bridge_ip_v6 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            interface=br_bond0,
            subnet=subnet_v6,
        )
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(node.domain)
        expected_mapping = {
            node.fqdn: HostnameIPMapping(
                node.system_id,
                30,
                {bridge_ip_v4.ip, bridge_ip_v6.ip},
                node.node_type,
            ),
            f"{eth0.name}.{node.fqdn}": HostnameIPMapping(
                node.system_id,
                30,
                {phy_staticip_v4.ip, phy_staticip_v6.ip},
                node.node_type,
            ),
        }
        self.assertEqual(mapping, expected_mapping)

    def test_get_hostname_ip_mapping_returns_domain_head_ips(self):
        parent = factory.make_Domain()
        name = factory.make_name()
        child = factory.make_Domain(name=f"{name}.{parent.name}")
        subnet = factory.make_Subnet()
        node = factory.make_Node_with_Interface_on_Subnet(
            subnet=subnet, domain=parent, hostname=name
        )
        sip1 = factory.make_StaticIPAddress(subnet=subnet)
        node.current_config.interface_set.first().ip_addresses.add(sip1)
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(parent)
        self.assertEqual(
            {
                node.fqdn: HostnameIPMapping(
                    node.system_id, 30, {sip1.ip}, node.node_type
                )
            },
            mapping,
        )
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(child)
        self.assertEqual(
            {
                node.fqdn: HostnameIPMapping(
                    node.system_id, 30, {sip1.ip}, node.node_type
                )
            },
            mapping,
        )

    def test_get_hostname_ip_mapping_does_not_return_discovered_and_auto(self):
        # Create a situation where we have an AUTO ip on the pxeboot interface,
        # and a discovered IP of the other address family (v4/v6) on another
        # interface.
        domain = Domain.objects.get_default_domain()
        cidrs = [factory.make_ipv6_network(), factory.make_ipv4_network()]
        shuffle(cidrs)
        subnets = [factory.make_Subnet(cidr=cidr) for cidr in cidrs]
        # First, make a node with an interface on subnets[0].  Assign the boot
        # interface an AUTO IP on subnets[0].
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=factory.make_name("host"),
            subnet=subnets[0],
            vlan=subnets[0].vlan,
        )
        sip0 = node.boot_interface.ip_addresses.first()
        ip0 = factory.pick_ip_in_network(cidrs[0])
        sip0.ip = ip0
        sip0.alloc_type = IPADDRESS_TYPE.AUTO
        with post_commit_hooks:
            sip0.save()
        # Now create another interface, and give it a DISCOVERED IP of the
        # other family from subnets[1].
        iface1 = factory.make_Interface(node=node, vlan=subnets[1].vlan)
        ip1 = factory.pick_ip_in_network(cidrs[1])
        sip1 = factory.make_StaticIPAddress(
            subnet=subnets[1], ip=ip1, alloc_type=IPADDRESS_TYPE.DISCOVERED
        )
        iface1.ip_addresses.add(sip1)

        with post_commit_hooks:
            iface1.save()
        # The only mapping we should get is for the boot interface.
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(domain)
        expected_mapping = {
            node.fqdn: HostnameIPMapping(
                node.system_id, 30, {sip0.ip}, node.node_type
            )
        }
        self.assertEqual(expected_mapping, mapping)

    def test_get_hostname_ip_mapping_returns_correct_bond_ip(self):
        # Create a situation where we have a STICKY ip on the pxeboot
        # interface, a STICKY ip on a bond containing the pxeboot interface and
        # another interface, and a discovered IP of the other address family
        # (v4/v6) on another interface.  We should only get the bond ip.
        domain = Domain.objects.get_default_domain()
        cidrs = [factory.make_ipv6_network(), factory.make_ipv4_network()]
        shuffle(cidrs)
        subnets = [factory.make_Subnet(cidr=cidr) for cidr in cidrs]
        # First, make a node with an interface on subnets[0].  Assign the boot
        # interface an AUTO IP on subnets[0].
        node = factory.make_Node_with_Interface_on_Subnet(
            hostname=factory.make_name("host"),
            subnet=subnets[0],
            vlan=subnets[0].vlan,
        )
        sip0 = node.boot_interface.ip_addresses.first()
        ip0 = factory.pick_ip_in_network(cidrs[0])
        sip0.ip = ip0
        sip0.alloc_type = IPADDRESS_TYPE.STICKY

        with post_commit_hooks:
            sip0.save()
        # Now create another interface, and give it a DISCOVERED IP of the
        # other family from subnets[1].
        iface1 = factory.make_Interface(node=node, vlan=subnets[1].vlan)
        ip1 = factory.pick_ip_in_network(cidrs[1])
        sip1 = factory.make_StaticIPAddress(
            subnet=subnets[1], ip=ip1, alloc_type=IPADDRESS_TYPE.DISCOVERED
        )
        iface1.ip_addresses.add(sip1)
        iface1.save()
        # Now create a bond containing the boot interface, and assign it
        # another IP from the same subnet as the boot interface.
        iface0 = node.get_boot_interface()
        iface2 = factory.make_Interface(node=node)
        bondif = factory.make_Interface(
            INTERFACE_TYPE.BOND, node=node, parents=[iface0, iface2]
        )
        bondip = factory.pick_ip_in_network(cidrs[0], but_not=[ip0])
        bond_sip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            interface=bondif,
            subnet=subnets[0],
            ip=bondip,
        )
        # The only mapping we should get is for the bond interface.
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(domain)
        expected_mapping = {
            node.fqdn: HostnameIPMapping(
                node.system_id, 30, {bond_sip.ip}, node.node_type
            )
        }
        self.assertEqual(expected_mapping, mapping)

    def test_get_hostname_ip_mapping_handles_dnsrr_node_collision(self):
        hostname = factory.make_name("hostname")
        domainname = factory.make_name("domain")
        # Randomly make our domain either the default, or non-default.
        # This does not change what we expect the answer to be.
        if factory.pick_bool():
            Domain.objects.get_default_domain()
        domain = factory.make_Domain(name=domainname)
        full_hostname = f"{hostname}.{domainname}"
        dnsrrname = factory.make_name("dnsrrname")
        full_dnsrrname = f"{dnsrrname}.{domainname}"

        subnet = factory.make_Subnet()
        node = factory.make_Node_with_Interface_on_Subnet(
            interface=True,
            hostname=full_hostname,
            interface_count=3,
            subnet=subnet,
        )
        boot_interface = node.get_boot_interface()
        staticip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=boot_interface,
        )
        iface2 = node.current_config.interface_set.exclude(
            id=boot_interface.id
        ).first()
        sip2 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
            interface=iface2,
        )
        sip3 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_Subnet(subnet),
            subnet=subnet,
        )
        # Create a DNSResource with one address on the node, and one not.
        # The forward mapping for the dnsrr points to both IPs.
        # The subnet mapping for the IP on the node only points to the node.
        # The other IP points to the DNSRR name.
        factory.make_DNSResource(
            name=dnsrrname, domain=domain, ip_addresses=[sip2, sip3]
        )
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(domain)
        expected = {
            full_hostname: HostnameIPMapping(
                node.system_id, 30, {staticip.ip}, node.node_type
            ),
            "%s.%s" % (iface2.name, full_hostname): HostnameIPMapping(
                node.system_id, 30, {sip2.ip}, node.node_type
            ),
            full_dnsrrname: HostnameIPMapping(
                node.system_id,
                30,
                {sip2.ip, sip3.ip},
                node.node_type,
                sip3.dnsresource_set.first().id,
            ),
        }
        self.assertEqual(expected, mapping)
        mapping = StaticIPAddress.objects.get_hostname_ip_mapping(subnet)
        expected = {
            full_hostname: HostnameIPMapping(
                node.system_id, 30, {staticip.ip}, node.node_type
            ),
            "%s.%s" % (iface2.name, full_hostname): HostnameIPMapping(
                node.system_id, 30, {sip2.ip}, node.node_type
            ),
            full_dnsrrname: HostnameIPMapping(None, 30, {sip3.ip}, None),
        }


class TestStaticIPAddress(MAASServerTestCase):
    def test_repr_with_valid_type(self):
        # Using USER_RESERVED here because it doesn't validate the Subnet.
        actual = "%s" % factory.make_StaticIPAddress(
            ip="10.0.0.1", alloc_type=IPADDRESS_TYPE.USER_RESERVED
        )
        self.assertEqual("10.0.0.1:type=USER_RESERVED", actual)

    def test_repr_with_invalid_type(self):
        actual = "%s" % factory.make_StaticIPAddress(
            ip="10.0.0.1",
            alloc_type=99999,
            subnet=factory.make_Subnet(cidr="10.0.0.0/8"),
        )
        self.assertEqual("10.0.0.1:type=99999", actual)

    def test_stores_to_database(self):
        ipaddress = factory.make_StaticIPAddress()
        self.assertEqual([ipaddress], list(StaticIPAddress.objects.all()))

    def test_invalid_address_raises_validation_error(self):
        ip = StaticIPAddress(ip="256.0.0.0.0")
        self.assertRaises(ValidationError, ip.full_clean)

    def test_get_interface_link_type_returns_AUTO_for_AUTO(self):
        ip = StaticIPAddress(alloc_type=IPADDRESS_TYPE.AUTO)
        self.assertEqual(
            INTERFACE_LINK_TYPE.AUTO, ip.get_interface_link_type()
        )

    def test_get_interface_link_type_returns_DHCP_for_DHCP(self):
        ip = StaticIPAddress(alloc_type=IPADDRESS_TYPE.DHCP)
        self.assertEqual(
            INTERFACE_LINK_TYPE.DHCP, ip.get_interface_link_type()
        )

    def test_get_interface_link_type_returns_STATIC_for_USER_RESERVED(self):
        ip = StaticIPAddress(alloc_type=IPADDRESS_TYPE.USER_RESERVED)
        self.assertEqual(
            INTERFACE_LINK_TYPE.STATIC, ip.get_interface_link_type()
        )

    def test_get_interface_link_type_returns_STATIC_for_DISCOVERED(self):
        ip = StaticIPAddress(alloc_type=IPADDRESS_TYPE.DISCOVERED)
        self.assertEqual(
            INTERFACE_LINK_TYPE.DHCP, ip.get_interface_link_type()
        )

    def test_get_interface_link_type_returns_STATIC_for_STICKY_with_ip(self):
        ip = StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=factory.make_ipv4_address()
        )
        self.assertEqual(
            INTERFACE_LINK_TYPE.STATIC, ip.get_interface_link_type()
        )

    def test_get_interface_link_type_returns_LINK_UP_for_STICKY_no_ip(self):
        ip = StaticIPAddress(alloc_type=IPADDRESS_TYPE.STICKY, ip="")
        self.assertEqual(
            INTERFACE_LINK_TYPE.LINK_UP, ip.get_interface_link_type()
        )

    def test_save_create_calls_dhcp_configure_workflow(self):
        mock_start_workflow = self.patch(
            static_ip_address_module, "start_workflow"
        )
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        ip = StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="10.0.0.1", subnet=subnet
        )

        with post_commit_hooks:
            ip.save()

        mock_start_workflow.assert_called_once_with(
            workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
            param=ConfigureDHCPParam(static_ip_addr_ids=[ip.id]),
            task_queue="region",
        )

    def test_save_new_subnet_calls_dhcp_configure_workflow(self):
        mock_start_workflow = self.patch(
            static_ip_address_module, "start_workflow"
        )
        subnet1 = factory.make_Subnet(cidr="10.0.0.0/20")
        subnet2 = factory.make_Subnet(cidr="10.0.0.0/24")
        ip = StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="10.0.0.1", subnet=subnet1
        )

        with post_commit_hooks:
            ip.save()
            ip.subnet = subnet2
            ip.save()

        self.assertIn(
            call(
                workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
                param=ConfigureDHCPParam(subnet_ids=[subnet1.id, subnet2.id]),
                task_queue="region",
            ),
            mock_start_workflow.mock_calls,
        )

    def test_save_new_ip_calls_dhcp_configure_workflow(self):
        mock_start_workflow = self.patch(
            static_ip_address_module, "start_workflow"
        )
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        ip = StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="", subnet=subnet
        )

        with post_commit_hooks:
            ip.save()
            ip.ip = "10.0.0.1"
            ip.save()

        mock_start_workflow.assert_called_once_with(
            workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
            param=ConfigureDHCPParam(static_ip_addr_ids=[ip.id]),
            task_queue="region",
        )

    def test_save_new_temp_expires_on_calls_dhcp_configure_workflow(self):
        mock_start_workflow = self.patch(
            static_ip_address_module, "start_workflow"
        )
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        ip = StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="10.0.0.1", subnet=subnet
        )

        with post_commit_hooks:
            ip.save()
            ip.temp_expires_on = datetime.now()
            ip.save()

        self.assertIn(
            call(
                workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
                param=ConfigureDHCPParam(static_ip_addr_ids=[ip.id]),
                task_queue="region",
            ),
            mock_start_workflow.mock_calls,
        )

    def test_delete_calls_dhcp_configure_workflow(self):
        mock_start_workflow = self.patch(
            static_ip_address_module, "start_workflow"
        )
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        ip = StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip="10.0.0.1",
            subnet=subnet,
            temp_expires_on=timezone.now(),
        )

        with post_commit_hooks:
            ip.save()
            ip.delete()

        self.assertIn(
            call(
                workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
                param=ConfigureDHCPParam(subnet_ids=[subnet.id]),
                task_queue="region",
            ),
            mock_start_workflow.mock_calls,
        )

    def test_discovered_ips_do_not_call_dhcp_configure_workflow(self):
        mock_start_workflow = self.patch(
            static_ip_address_module, "start_workflow"
        )
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        ip = StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip="10.0.0.1", subnet=subnet
        )

        with post_commit_hooks:
            ip.save()

        mock_start_workflow.assert_not_called()

    def test_delete_empty_ip_does_not_call_dhcp_configure_workflow(self):
        mock_start_workflow = self.patch(
            static_ip_address_module, "start_workflow"
        )
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        ip = StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED,
            ip="10.0.0.1",
            subnet=subnet,
            temp_expires_on=None,
        )

        with post_commit_hooks:
            ip.save()
            ip.delete()

        assert len(mock_start_workflow.mock_calls) == 1


class TestUserReservedStaticIPAddress(MAASServerTestCase):
    def test_user_reserved_addresses_have_default_hostnames(self):
        # Reserved IPs get default hostnames when none are given.
        subnet = factory.make_Subnet()
        num_ips = randint(3, 5)
        ips = [
            factory.make_StaticIPAddress(
                subnet=subnet, alloc_type=IPADDRESS_TYPE.USER_RESERVED
            )
            for _ in range(num_ips)
        ]
        mappings = StaticIPAddress.objects._get_special_mappings(subnet)
        self.assertEqual(len(mappings), len(ips))

    def test_user_reserved_addresses_included_in_get_hostname_ip_mapping(self):
        # Generate several IPs, with names in domain0, and make sure they don't
        # show up in domain1.
        num_ips = randint(3, 5)
        domain0 = Domain.objects.get_default_domain()
        domain1 = factory.make_Domain()
        ips = [
            factory.make_StaticIPAddress(
                hostname="{}.{}".format(
                    factory.make_name("host"), domain0.name
                ),
                alloc_type=IPADDRESS_TYPE.USER_RESERVED,
            )
            for _ in range(num_ips)
        ]
        expected = {
            ip.dnsresource_set.first().fqdn: HostnameIPMapping(
                None, 30, {ip.ip}, None, ip.dnsresource_set.first().id
            )
            for ip in ips
        }
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(domain0)
        self.assertEqual(expected, mappings)
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(domain1)
        self.assertEqual(len(mappings), 0)

    def test_user_reserved_addresses_included_in_correct_domains(self):
        # Generate some addresses with no names attached, and some more in each
        # of two (non-default) domains.  Make sure that they wind up in the
        # right domains, and not in other domains.
        domain0 = Domain.objects.get_default_domain()
        domain1 = factory.make_Domain()
        domain2 = factory.make_Domain()
        ips0 = [
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.USER_RESERVED
            )
            for _ in range(randint(3, 5))
        ]
        ips1 = [
            factory.make_StaticIPAddress(
                hostname="{}.{}".format(
                    factory.make_name("host"), domain1.name
                ),
                alloc_type=IPADDRESS_TYPE.USER_RESERVED,
            )
            for _ in range(randint(6, 9))
        ]
        ips2 = [
            factory.make_StaticIPAddress(
                hostname="{}.{}".format(
                    factory.make_name("host"), domain2.name
                ),
                alloc_type=IPADDRESS_TYPE.USER_RESERVED,
            )
            for _ in range(randint(1, 2))
        ]
        expected = {
            "%s.%s"
            % (get_ip_based_hostname(ip.ip), domain0.name): HostnameIPMapping(
                None, 30, {ip.ip}, None
            )
            for ip in ips0
        }
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(domain0)
        self.assertEqual(expected, mappings)
        expected = {
            ip.dnsresource_set.first().fqdn: HostnameIPMapping(
                None, 30, {ip.ip}, None, ip.dnsresource_set.first().id
            )
            for ip in ips1
        }
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(domain1)
        self.assertEqual(expected, mappings)
        expected = {
            ip.dnsresource_set.first().fqdn: HostnameIPMapping(
                None, 30, {ip.ip}, None, ip.dnsresource_set.first().id
            )
            for ip in ips2
        }
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(domain2)
        self.assertEqual(expected, mappings)

    def test_dns_resources_only_have_correct_domain(self):
        # Create two DNS resources pointing to the same IP, and make sure that
        # they only get the forward mapping that they should have, but get both
        # reverse mappings, as is proper.
        domain0 = Domain.objects.get_default_domain()
        domain1 = factory.make_Domain()
        domain2 = factory.make_Domain()
        subnet = factory.make_Subnet()
        ip = factory.make_StaticIPAddress(subnet=subnet)
        name1 = factory.make_name("label")
        name2 = factory.make_name("label")
        factory.make_DNSResource(name=name1, ip_addresses=[ip], domain=domain1)
        factory.make_DNSResource(name=name2, ip_addresses=[ip], domain=domain2)
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(domain0)
        self.assertEqual(len(mappings), 0)
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(domain1)
        domain1_rr_id = ip.dnsresource_set.filter(domain=domain1.id).first().id
        domain2_rr_id = ip.dnsresource_set.filter(domain=domain2.id).first().id
        self.assertEqual(len(mappings), 1)
        self.assertEqual(
            mappings.get(f"{name1}.{domain1.name}"),
            HostnameIPMapping(None, 30, {ip.ip}, None, domain1_rr_id),
        )
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(domain2)
        self.assertEqual(len(mappings), 1)
        self.assertEqual(
            mappings.get(f"{name2}.{domain2.name}"),
            HostnameIPMapping(None, 30, {ip.ip}, None, domain2_rr_id),
        )
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(subnet)
        self.assertEqual(
            mappings,
            {
                "%s.%s" % (name1, domain1.name): HostnameIPMapping(
                    None, 30, {ip.ip}, None, domain1_rr_id
                ),
                "%s.%s" % (name2, domain2.name): HostnameIPMapping(
                    None, 30, {ip.ip}, None, domain2_rr_id
                ),
            },
        )

    def test_user_reserved_IP_on_node_or_default_domain_not_both(self):
        # ip1 gets assigned to an interface on a node in domain1
        # ip2 is not assigned to anything.
        # ip3 gets assigned to a DNS resource in domain2
        # ip1 should show up for the node, in domain1, and the subnet.
        # ip2 should show up in the default domain, and the subnet.
        # ip3 should show up in domain2, and the subnet.
        domain0 = Domain.objects.get_default_domain()
        domain1 = factory.make_Domain()
        domain2 = factory.make_Domain()
        rrname = factory.make_name("dnsrr")
        subnet = factory.make_Subnet()
        ip1 = factory.make_StaticIPAddress(subnet=subnet)
        ip2 = factory.make_StaticIPAddress(
            subnet=subnet, alloc_type=IPADDRESS_TYPE.USER_RESERVED
        )
        ip3 = factory.make_StaticIPAddress(
            subnet=subnet, alloc_type=IPADDRESS_TYPE.USER_RESERVED
        )
        dnsrr = factory.make_DNSResource(
            name=rrname, domain=domain2, ip_addresses=[ip3]
        )
        name2 = f"{get_ip_based_hostname(ip2.ip)}.{domain0.name}"
        node = factory.make_Node(
            interface=True, domain=domain1, vlan=subnet.vlan
        )
        node.current_config.interface_set.first().ip_addresses.add(ip1)
        expected0 = {name2: HostnameIPMapping(None, 30, {ip2.ip}, None)}
        expected1 = {
            node.fqdn: HostnameIPMapping(
                node.system_id, 30, {ip1.ip}, node.node_type
            )
        }
        expected2 = {
            dnsrr.fqdn: HostnameIPMapping(
                None, 30, {ip3.ip}, None, ip3.dnsresource_set.first().id
            )
        }
        expected_subnet = {
            name2: HostnameIPMapping(None, 30, {ip2.ip}, None),
            node.fqdn: HostnameIPMapping(
                node.system_id, 30, {ip1.ip}, node.node_type
            ),
            dnsrr.fqdn: HostnameIPMapping(
                None, 30, {ip3.ip}, None, ip3.dnsresource_set.first().id
            ),
        }
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(domain0)
        self.assertEqual(expected0, mappings)
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(domain1)
        self.assertEqual(expected1, mappings)
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(domain2)
        self.assertEqual(expected2, mappings)
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(subnet)
        self.assertEqual(expected_subnet, mappings)

    def test_node_glue_correctly_generated(self):
        # Given node "foo.bar.com" and a "foo.bar.com" domain (in addition to
        # "bar.com"), with an IP associated with it, make sure that both
        # domains are correctly populated.
        domain0 = Domain.objects.get_default_domain()
        parent = factory.make_Domain(name=factory.make_name("parent"))
        name = factory.make_name("child")
        domain = factory.make_Domain(name=f"{name}.{parent.name}")
        subnet = factory.make_Subnet()
        ip = factory.make_StaticIPAddress(subnet=subnet)
        node = factory.make_Node(
            interface=True, domain=parent, hostname=name, vlan=subnet.vlan
        )
        node.current_config.interface_set.first().ip_addresses.add(ip)
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(domain0)
        self.assertEqual(len(mappings), 0)
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(parent)
        self.assertEqual(len(mappings), 1)
        self.assertEqual(
            HostnameIPMapping(node.system_id, 30, {ip.ip}, node.node_type),
            mappings.get(node.fqdn),
        )
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(domain)
        self.assertEqual(len(mappings), 1)
        self.assertEqual(
            HostnameIPMapping(node.system_id, 30, {ip.ip}, node.node_type),
            mappings.get(node.fqdn),
        )
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(subnet)
        self.assertEqual(
            {
                node.fqdn: HostnameIPMapping(
                    node.system_id, 30, {ip.ip}, node.node_type
                )
            },
            mappings,
        )

    def test_dnsrr_glue_correctly_generated(self):
        # Given DNSResource "foo.bar.com" and a "foo.bar.com" domain (in
        # addition to "bar.com"), with an IP associated with it, make sure that
        # both domains are correctly populated.
        domain0 = Domain.objects.get_default_domain()
        parent = factory.make_Domain(name=factory.make_name("parent"))
        name = factory.make_name("child")
        domain = factory.make_Domain(name=f"{name}.{parent.name}")
        subnet = factory.make_Subnet()
        ip = factory.make_StaticIPAddress(subnet=subnet)
        dnsrr = factory.make_DNSResource(
            domain=domain, name="@", ip_addresses=[ip]
        )
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(domain0)
        self.assertEqual(len(mappings), 0)
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(parent)
        self.assertEqual(len(mappings), 1)
        self.assertEqual(
            HostnameIPMapping(
                None, 30, {ip.ip}, None, ip.dnsresource_set.first().id
            ),
            mappings.get(dnsrr.fqdn),
        )
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(domain)
        self.assertEqual(len(mappings), 1)
        self.assertEqual(
            HostnameIPMapping(
                None, 30, {ip.ip}, None, ip.dnsresource_set.first().id
            ),
            mappings.get(dnsrr.fqdn),
        )
        mappings = StaticIPAddress.objects.get_hostname_ip_mapping(subnet)
        self.assertEqual(
            {
                dnsrr.fqdn: HostnameIPMapping(
                    None, 30, {ip.ip}, None, ip.dnsresource_set.first().id
                )
            },
            mappings,
        )


class TestRenderJSON(MAASServerTestCase):
    def test_excludes_username_and_node_summary_by_default(self):
        ip = factory.make_StaticIPAddress(
            ip=factory.make_ipv4_address(),
            alloc_type=IPADDRESS_TYPE.USER_RESERVED,
        )
        json = ip.render_json()
        self.assertNotIn("user", json)
        self.assertNotIn("node_summary", json)

    def test_includes_username_if_requested(self):
        user = factory.make_User()
        ip = factory.make_StaticIPAddress(
            ip=factory.make_ipv4_address(),
            user=user,
            alloc_type=IPADDRESS_TYPE.USER_RESERVED,
        )
        json = ip.render_json(with_username=True)
        self.assertIn("user", json)
        self.assertNotIn("node_summary", json)
        self.assertEqual(json["user"], user.username)

    def test_includes_node_summary_if_requested(self):
        user = factory.make_User()
        subnet = factory.make_Subnet()
        node = factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
        ip = factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_Subnet(subnet),
            user=user,
            interface=node.get_boot_interface(),
        )
        json = ip.render_json(with_summary=True)
        self.assertNotIn("user", json)
        self.assertIn("node_summary", json)

    def test_node_summary_includes_interface_name(self):
        user = factory.make_User()
        subnet = factory.make_Subnet()
        node = factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
        self.assertEqual(node.current_config.interface_set.count(), 1)
        iface = node.current_config.interface_set.first()
        ip = factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_Subnet(subnet),
            user=user,
            interface=node.get_boot_interface(),
        )
        json = ip.render_json(with_summary=True)
        self.assertNotIn("user", json)
        self.assertIn("node_summary", json)
        self.assertEqual(json["node_summary"]["via"], iface.name)

    def test_data_is_accurate_and_complete(self):
        user = factory.make_User()
        hostname = factory.make_name("hostname")
        subnet = factory.make_Subnet()
        node = factory.make_Node_with_Interface_on_Subnet(
            subnet=subnet, hostname=hostname
        )
        ip = factory.make_StaticIPAddress(
            ip=factory.pick_ip_in_Subnet(subnet),
            user=user,
            interface=node.get_boot_interface(),
        )
        json = ip.render_json(with_username=True, with_summary=True)
        self.assertEqual(json["created"], dehydrate_datetime(ip.created))
        self.assertEqual(json["updated"], dehydrate_datetime(ip.updated))
        self.assertEqual(json["user"], user.username)
        self.assertIn("node_summary", json)
        node_summary = json["node_summary"]
        self.assertEqual(node_summary["system_id"], node.system_id)
        self.assertEqual(node_summary["node_type"], node.node_type)


class TestAllocTypeName(MAASServerTestCase):
    def test_provides_human_readable_values_for_known_types(self):
        ip = factory.make_StaticIPAddress()
        self.assertEqual(
            IPADDRESS_TYPE_CHOICES_DICT[ip.alloc_type],
            ip.alloc_type_name,
        )

    def test_returns_empty_string_for_unknown_types(self):
        ip = factory.make_StaticIPAddress()
        ip.alloc_type = randint(2**16, 2**32)
        self.assertEqual("", ip.alloc_type_name)


class TestUniqueConstraints(MAASServerTestCase):
    assertRaises = TestCase.assertRaises

    def test_rejects_duplicate_address_of_same_type(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/8")
        factory.make_StaticIPAddress(
            ip="10.0.0.1",
            subnet=subnet,
            alloc_type=IPADDRESS_TYPE.USER_RESERVED,
        )
        with self.assertRaises(ValidationError):
            factory.make_StaticIPAddress(
                ip="10.0.0.1", alloc_type=IPADDRESS_TYPE.USER_RESERVED
            )

    def test_rejects_duplicate_address_for_two_different_static_types(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/8")
        factory.make_StaticIPAddress(
            ip="10.0.0.1", subnet=subnet, alloc_type=IPADDRESS_TYPE.STICKY
        )
        with self.assertRaises(IntegrityError):
            factory.make_StaticIPAddress(
                ip="10.0.0.1",
                subnet=subnet,
                alloc_type=IPADDRESS_TYPE.USER_RESERVED,
            )

    def test_rejects_duplicate_discovered(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/8")
        factory.make_StaticIPAddress(
            ip="10.0.0.1", subnet=subnet, alloc_type=IPADDRESS_TYPE.DISCOVERED
        )
        with self.assertRaises(ValidationError):
            factory.make_StaticIPAddress(
                ip="10.0.0.1",
                subnet=subnet,
                alloc_type=IPADDRESS_TYPE.DISCOVERED,
            )

    def test_allows_discovered_to_coexist_with_static(self):
        subnet = factory.make_Subnet(cidr="10.0.0.0/8")
        factory.make_StaticIPAddress(
            ip="10.0.0.1", subnet=subnet, alloc_type=IPADDRESS_TYPE.DISCOVERED
        )
        factory.make_StaticIPAddress(
            ip="10.0.0.1", subnet=subnet, alloc_type=IPADDRESS_TYPE.STICKY
        )
        self.assertEqual(
            2, StaticIPAddress.objects.filter(ip="10.0.0.1").count()
        )
