# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver models."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from datetime import (
    datetime,
    timedelta,
    )
from itertools import izip
import random

import crochet
from django.core.exceptions import ValidationError
from django.db import transaction
from maasserver import preseed as preseed_module
from maasserver.clusterrpc.power_parameters import get_power_types
from maasserver.clusterrpc.testing.boot_images import make_rpc_boot_image
from maasserver.dns import config as dns_config
from maasserver.enum import (
    IPADDRESS_TYPE,
    NODE_BOOT,
    NODE_PERMISSION,
    NODE_STATUS,
    NODE_STATUS_CHOICES,
    NODE_STATUS_CHOICES_DICT,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    POWER_STATE,
    )
from maasserver.exceptions import (
    NodeStateViolation,
    StaticIPAddressTypeClash,
    )
from maasserver.fields import MAC
from maasserver.models import (
    Config,
    LicenseKey,
    MACAddress,
    Node,
    node as node_module,
    )
from maasserver.models.node import (
    PowerInfo,
    validate_hostname,
    )
from maasserver.models.staticipaddress import (
    StaticIPAddress,
    StaticIPAddressManager,
    )
from maasserver.models.user import create_auth_token
from maasserver.node_action import RPC_EXCEPTIONS
from maasserver.node_status import (
    get_failed_status,
    MONITORED_STATUSES,
    NODE_FAILURE_STATUS_TRANSITIONS,
    NODE_TRANSITIONS,
    )
from maasserver.rpc.testing.fixtures import (
    MockLiveRegionToClusterRPCFixture,
    RunningClusterRPCFixture,
    )
from maasserver.testing.eventloop import (
    RegionEventLoopFixture,
    RunningEventLoopFixture,
    )
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.osystems import make_usable_osystem
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils import ignore_unused
from maastesting.djangotestcase import count_queries
from maastesting.matchers import (
    MockAnyCall,
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
    )
from maastesting.testcase import MAASTestCase
from metadataserver.enum import RESULT_TYPE
from metadataserver.fields import Bin
from metadataserver.models import (
    NodeResult,
    NodeUserData,
    )
from metadataserver.user_data import (
    commissioning,
    disk_erasing,
    )
from mock import (
    ANY,
    call,
    Mock,
    sentinel,
    )
from provisioningserver.power.poweraction import UnknownPowerType
from provisioningserver.power_schema import JSON_POWER_TYPE_PARAMETERS
from provisioningserver.rpc import cluster as cluster_module
from provisioningserver.rpc.cluster import StartMonitors
from provisioningserver.rpc.exceptions import (
    MultipleFailures,
    NoConnectionsAvailable,
    )
from provisioningserver.rpc.power import QUERY_POWER_TYPES
from provisioningserver.rpc.testing import (
    always_succeed_with,
    TwistedLoggerFixture,
    )
from provisioningserver.utils.enum import map_enum
from testtools.matchers import (
    Equals,
    HasLength,
    Is,
    IsInstance,
    MatchesStructure,
    )
from twisted.internet import defer
from twisted.internet.defer import Deferred
from twisted.protocols import amp
from twisted.python.failure import Failure


class TestHostnameValidator(MAASTestCase):
    """Tests for the validation of hostnames.

    Specifications based on:
        http://en.wikipedia.org/wiki/Hostname#Restrictions_on_valid_host_names

    This does not support Internationalized Domain Names.  To do so, we'd have
    to accept and store unicode, but use the Punycode-encoded version.  The
    validator would have to validate both versions: the unicode input for
    invalid characters, and the encoded version for length.
    """
    def make_maximum_hostname(self):
        """Create a hostname of the maximum permitted length.

        The maximum permitted length is 255 characters.  The last label in the
        hostname will not be of the maximum length, so tests can still append a
        character to it without creating an invalid label.

        The hostname is not randomised, so do not count on it being unique.
        """
        # A hostname may contain any number of labels, separated by dots.
        # Each of the labels has a maximum length of 63 characters, so this has
        # to be built up from multiple labels.
        ten_chars = ('a' * 9) + '.'
        hostname = ten_chars * 25 + ('b' * 5)
        self.assertEqual(255, len(hostname))
        return hostname

    def assertAccepts(self, hostname):
        """Assertion: the validator accepts `hostname`."""
        try:
            validate_hostname(hostname)
        except ValidationError as e:
            raise AssertionError(unicode(e))

    def assertRejects(self, hostname):
        """Assertion: the validator rejects `hostname`."""
        self.assertRaises(ValidationError, validate_hostname, hostname)

    def test_accepts_ascii_letters(self):
        self.assertAccepts('abcde')

    def test_accepts_dots(self):
        self.assertAccepts('abc.def')

    def test_rejects_adjacent_dots(self):
        self.assertRejects('abc..def')

    def test_rejects_leading_dot(self):
        self.assertRejects('.abc')

    def test_rejects_trailing_dot(self):
        self.assertRejects('abc.')

    def test_accepts_ascii_digits(self):
        self.assertAccepts('abc123')

    def test_accepts_leading_digits(self):
        # Leading digits used to be forbidden, but are now allowed.
        self.assertAccepts('123abc')

    def test_rejects_whitespace(self):
        self.assertRejects('a b')
        self.assertRejects('a\nb')
        self.assertRejects('a\tb')

    def test_rejects_other_ascii_characters(self):
        self.assertRejects('a?b')
        self.assertRejects('a!b')
        self.assertRejects('a,b')
        self.assertRejects('a:b')
        self.assertRejects('a;b')
        self.assertRejects('a+b')
        self.assertRejects('a=b')

    def test_accepts_underscore_in_domain(self):
        self.assertAccepts('host.local_domain')

    def test_rejects_underscore_in_host(self):
        self.assertRejects('host_name.local')

    def test_accepts_hyphen(self):
        self.assertAccepts('a-b')

    def test_rejects_hyphen_at_start_of_label(self):
        self.assertRejects('-ab')

    def test_rejects_hyphen_at_end_of_label(self):
        self.assertRejects('ab-')

    def test_accepts_maximum_valid_length(self):
        self.assertAccepts(self.make_maximum_hostname())

    def test_rejects_oversized_hostname(self):
        self.assertRejects(self.make_maximum_hostname() + 'x')

    def test_accepts_maximum_label_length(self):
        self.assertAccepts('a' * 63)

    def test_rejects_oversized_label(self):
        self.assertRejects('b' * 64)

    def test_rejects_nonascii_letter(self):
        # The \u03be is the Greek letter xi.  Perfectly good letter, just not
        # ASCII.
        self.assertRejects('\u03be')


def make_active_lease(nodegroup=None):
    """Create a `DHCPLease` on a managed `NodeGroupInterface`."""
    lease = factory.make_DHCPLease(nodegroup=nodegroup)
    factory.make_NodeGroupInterface(
        lease.nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
    return lease


class NodeTest(MAASServerTestCase):

    def test_system_id(self):
        """
        The generated system_id looks good.

        """
        node = factory.make_Node()
        self.assertEqual(len(node.system_id), 41)
        self.assertTrue(node.system_id.startswith('node-'))

    def test_hostname_is_validated(self):
        bad_hostname = '-_?!@*-'
        self.assertRaises(
            ValidationError,
            factory.make_Node, hostname=bad_hostname)

    def test_work_queue_returns_nodegroup_uuid(self):
        nodegroup = factory.make_NodeGroup()
        node = factory.make_Node(nodegroup=nodegroup)
        self.assertEqual(nodegroup.uuid, node.work_queue)

    def test_display_status_shows_default_status(self):
        node = factory.make_Node()
        self.assertEqual(
            NODE_STATUS_CHOICES_DICT[node.status],
            node.display_status())

    def test_display_memory_returns_decimal_less_than_1024(self):
        node = factory.make_Node(memory=512)
        self.assertEqual('0.5', node.display_memory())

    def test_display_memory_returns_value_divided_by_1024(self):
        node = factory.make_Node(memory=2048)
        self.assertEqual('2', node.display_memory())

    def test_display_storage_returns_decimal_less_than_1024(self):
        node = factory.make_Node(storage=512)
        self.assertEqual('0.5', node.display_storage())

    def test_display_storage_returns_value_divided_by_1024(self):
        node = factory.make_Node(storage=2048)
        self.assertEqual('2', node.display_storage())

    def test_add_node_with_token(self):
        user = factory.make_User()
        token = create_auth_token(user)
        node = factory.make_Node(token=token)
        self.assertEqual(token, node.token)

    def test_add_mac_address(self):
        mac = factory.make_mac_address()
        node = factory.make_Node()
        node.add_mac_address(mac)
        macs = MACAddress.objects.filter(node=node, mac_address=mac).count()
        self.assertEqual(1, macs)

    def test_add_mac_address_sets_cluster_interface(self):
        # If a DHCPLease exists for this mac, ensure the
        # cluster_interface is set on the basis of that lease.
        cluster = factory.make_NodeGroup()
        cluster_interface = factory.make_NodeGroupInterface(nodegroup=cluster)
        ip_in_range = cluster_interface.static_ip_range_low
        mac_address = factory.make_mac_address()
        factory.make_DHCPLease(
            mac=mac_address, ip=ip_in_range, nodegroup=cluster)
        node = factory.make_Node(nodegroup=cluster)

        node.add_mac_address(mac_address)
        self.assertEqual(
            cluster_interface, node.get_primary_mac().cluster_interface)

    def test_remove_mac_address(self):
        mac = factory.make_mac_address()
        node = factory.make_Node()
        node.add_mac_address(mac)
        node.remove_mac_address(mac)
        self.assertItemsEqual(
            [],
            MACAddress.objects.filter(node=node, mac_address=mac))

    def test_get_primary_mac_returns_mac_address(self):
        node = factory.make_Node()
        mac = factory.make_mac_address()
        node.add_mac_address(mac)
        self.assertEqual(mac, node.get_primary_mac().mac_address)

    def test_get_primary_mac_returns_None_if_node_has_no_mac(self):
        node = factory.make_Node()
        self.assertIsNone(node.get_primary_mac())

    def test_get_primary_mac_returns_oldest_mac(self):
        node = factory.make_Node()
        macs = [factory.make_mac_address() for counter in range(3)]
        offset = timedelta(0)
        for mac in macs:
            mac_address = node.add_mac_address(mac)
            mac_address.created += offset
            mac_address.save()
            offset += timedelta(1)
        self.assertEqual(macs[0], node.get_primary_mac().mac_address)

    def test_get_osystem_returns_default_osystem(self):
        node = factory.make_Node(osystem='')
        osystem = Config.objects.get_config('default_osystem')
        self.assertEqual(osystem, node.get_osystem())

    def test_get_distro_series_returns_default_series(self):
        node = factory.make_Node(distro_series='')
        series = Config.objects.get_config('default_distro_series')
        self.assertEqual(series, node.get_distro_series())

    def test_get_effective_license_key_returns_node_value(self):
        license_key = factory.make_name('license_key')
        node = factory.make_Node(license_key=license_key)
        self.assertEqual(license_key, node.get_effective_license_key())

    def test_get_effective_license_key_returns_blank(self):
        node = factory.make_Node()
        self.assertEqual('', node.get_effective_license_key())

    def test_get_effective_license_key_returns_global(self):
        license_key = factory.make_name('license_key')
        osystem = factory.make_name('os')
        series = factory.make_name('series')
        LicenseKey.objects.create(
            osystem=osystem, distro_series=series, license_key=license_key)
        node = factory.make_Node(osystem=osystem, distro_series=series)
        self.assertEqual(license_key, node.get_effective_license_key())

    def test_delete_node_deletes_managed_node_when_changed_to_unmanaged(self):
        node = factory.make_node_with_mac_attached_to_nodegroupinterface()
        factory.make_DHCPLease(
            nodegroup=node.nodegroup,
            mac=node.macaddress_set.all().first().mac_address)
        interface = node.nodegroup.nodegroupinterface_set.all().first()
        interface.management = NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED
        interface.save()
        self.useFixture(RunningClusterRPCFixture())
        node.delete()
        self.assertItemsEqual([], Node.objects.all())

    def test_delete_node_deletes_related_mac(self):
        node = factory.make_Node()
        mac = node.add_mac_address('AA:BB:CC:DD:EE:FF')
        node.delete()
        self.assertRaises(
            MACAddress.DoesNotExist, MACAddress.objects.get, id=mac.id)

    def test_cannot_delete_allocated_node(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        self.assertRaises(NodeStateViolation, node.delete)

    def test_delete_node_also_deletes_related_static_IPs(self):
        self.patch_autospec(node_module, "remove_host_maps")
        node = factory.make_node_with_mac_attached_to_nodegroupinterface()
        primary_mac = node.get_primary_mac()
        random_alloc_type = factory.pick_enum(
            IPADDRESS_TYPE, but_not=[IPADDRESS_TYPE.USER_RESERVED])
        primary_mac.claim_static_ips(alloc_type=random_alloc_type)
        node.delete()
        self.assertItemsEqual([], StaticIPAddress.objects.all())

    def test_delete_node_also_deletes_static_dhcp_maps(self):
        remove_host_maps = self.patch_autospec(
            node_module, "remove_host_maps")
        node = factory.make_node_with_mac_attached_to_nodegroupinterface()
        primary_mac = node.get_primary_mac()
        static_ip_addresses = set(
            static_ip_address.ip for static_ip_address in
            primary_mac.claim_static_ips(alloc_type=IPADDRESS_TYPE.STICKY))
        node.delete()
        self.assertThat(
            remove_host_maps, MockCalledOnceWith(
                {node.nodegroup: static_ip_addresses}))

    def test_delete_node_also_deletes_dhcp_host_map(self):
        remove_host_maps = self.patch_autospec(
            node_module, "remove_host_maps")
        node = factory.make_node_with_mac_attached_to_nodegroupinterface()
        lease = factory.make_DHCPLease(
            nodegroup=node.nodegroup,
            mac=node.macaddress_set.all().first().mac_address)
        node.delete()
        self.assertThat(
            remove_host_maps, MockCalledOnceWith(
                {node.nodegroup: {lease.ip}}))

    def test_delete_node_removes_multiple_host_maps(self):
        remove_host_maps = self.patch_autospec(
            node_module, "remove_host_maps")
        node = factory.make_node_with_mac_attached_to_nodegroupinterface()
        mac = node.add_mac_address('AA:BB:CC:DD:EE:FF')
        mac.cluster_interface = (
            node.nodegroup.nodegroupinterface_set.all()[:1].get())
        mac.save()
        lease1 = factory.make_DHCPLease(
            nodegroup=node.nodegroup,
            mac=node.macaddress_set.all()[:1].get().mac_address)
        lease2 = factory.make_DHCPLease(
            nodegroup=node.nodegroup,
            mac=mac.mac_address)
        node.delete()
        self.assertThat(
            remove_host_maps, MockCalledOnceWith(
                {node.nodegroup: {lease1.ip, lease2.ip}},
            ))

    def test_set_random_hostname_set_hostname(self):
        # Blank out enlistment_domain.
        Config.objects.set_config("enlistment_domain", '')
        node = factory.make_Node()
        original_hostname = node.hostname
        node.set_random_hostname()
        self.assertNotEqual(original_hostname, node.hostname)
        self.assertNotEqual("", node.hostname)

    def test_set_random_hostname_checks_hostname_existence(self):
        Config.objects.set_config("enlistment_domain", '')
        existing_node = factory.make_Node(hostname='hostname')

        hostnames = [existing_node.hostname, "new-hostname"]
        self.patch(
            node_module, "gen_candidate_names",
            lambda: iter(hostnames))

        node = factory.make_Node()
        node.set_random_hostname()
        self.assertEqual('new-hostname', node.hostname)

    def test_get_effective_power_type_raises_if_not_set(self):
        node = factory.make_Node(power_type='')
        self.assertRaises(
            UnknownPowerType, node.get_effective_power_type)

    def test_get_effective_power_type_reads_node_field(self):
        power_types = list(get_power_types().keys())  # Python3 proof.
        nodes = [
            factory.make_Node(power_type=power_type)
            for power_type in power_types]
        self.assertEqual(
            power_types, [node.get_effective_power_type() for node in nodes])

    def test_power_parameters_are_stored(self):
        node = factory.make_Node(power_type='')
        parameters = dict(user="tarquin", address="10.1.2.3")
        node.power_parameters = parameters
        node.save()
        node = reload_object(node)
        self.assertEqual(parameters, node.power_parameters)

    def test_power_parameters_default(self):
        node = factory.make_Node(power_type='')
        self.assertEqual('', node.power_parameters)

    def test_get_effective_power_parameters_returns_power_parameters(self):
        params = {'test_parameter': factory.make_string()}
        node = factory.make_Node(power_parameters=params)
        self.assertEqual(
            params['test_parameter'],
            node.get_effective_power_parameters()['test_parameter'])

    def test_get_effective_power_parameters_adds_system_id(self):
        node = factory.make_Node()
        self.assertEqual(
            node.system_id,
            node.get_effective_power_parameters()['system_id'])

    def test_get_effective_power_parameters_adds_mac_if_no_params_set(self):
        node = factory.make_Node()
        mac = factory.make_mac_address()
        node.add_mac_address(mac)
        self.assertEqual(
            mac, node.get_effective_power_parameters()['mac_address'])

    def test_get_effective_power_parameters_adds_no_mac_if_params_set(self):
        node = factory.make_Node(power_parameters={'foo': 'bar'})
        mac = factory.make_mac_address()
        node.add_mac_address(mac)
        self.assertNotIn('mac', node.get_effective_power_parameters())

    def test_get_effective_power_parameters_adds_empty_power_off_mode(self):
        node = factory.make_Node()
        params = node.get_effective_power_parameters()
        self.assertEqual("", params["power_off_mode"])

    def test_get_effective_power_type_no_default_power_address_if_not_virsh(
            self):
        node = factory.make_Node(power_type="ether_wake")
        params = node.get_effective_power_parameters()
        self.assertEqual("", params["power_address"])

    def test_get_effective_power_type_defaults_power_address_if_virsh(self):
        node = factory.make_Node(power_type="virsh")
        params = node.get_effective_power_parameters()
        self.assertEqual("qemu://localhost/system", params["power_address"])

    def test_get_effective_power_info_is_False_for_unset_power_type(self):
        node = factory.make_Node(power_type="")
        self.assertEqual(
            (False, False, False, None, None),
            node.get_effective_power_info())

    def test_get_effective_power_info_is_True_for_set_power_type(self):
        node = factory.make_Node(power_type=factory.make_name("pwr"))
        gepp = self.patch(node, "get_effective_power_parameters")
        gepp.return_value = sentinel.power_parameters
        self.assertEqual(
            PowerInfo(
                True, True, False, node.power_type, sentinel.power_parameters),
            node.get_effective_power_info())

    def test_get_effective_power_info_can_be_False_for_ether_wake(self):
        node = factory.make_Node(power_type="ether_wake")
        gepp = self.patch(node, "get_effective_power_parameters")
        # When there's no MAC address in the power parameters,
        # get_effective_power_info() says that this node's power cannot
        # be turned on. However, it does return the power parameters.
        # For ether_wake the power can never be turned off.
        gepp.return_value = {}
        self.assertEqual(
            (False, False, False, "ether_wake", {}),
            node.get_effective_power_info())

    def test_get_effective_power_info_can_be_True_for_ether_wake(self):
        node = factory.make_Node(power_type="ether_wake")
        gepp = self.patch(node, "get_effective_power_parameters")
        # When the MAC address is supplied it changes its mind: this
        # node's power can be turned on. For ether_wake the power can
        # never be turned off.
        gepp.return_value = {"mac_address": sentinel.mac_addr}
        self.assertEqual(
            (
                True, False, False, "ether_wake",
                {"mac_address": sentinel.mac_addr}
            ),
            node.get_effective_power_info())

    def test_get_effective_power_info_cant_be_queried(self):
        all_power_types = {
            power_type_details['name']
            for power_type_details in JSON_POWER_TYPE_PARAMETERS
        }
        uncontrolled_power_types = all_power_types.difference(
            QUERY_POWER_TYPES)
        power_type = random.choice(list(uncontrolled_power_types))
        node = factory.make_Node(power_type=power_type)
        gepp = self.patch(node, "get_effective_power_parameters")
        self.assertEqual(
            PowerInfo(
                True, power_type != 'ether_wake', False, power_type,
                gepp()),
            node.get_effective_power_info())

    def test_get_effective_power_info_can_be_queried(self):
        power_type = random.choice(QUERY_POWER_TYPES)
        node = factory.make_Node(power_type=power_type)
        gepp = self.patch(node, "get_effective_power_parameters")
        self.assertEqual(
            PowerInfo(
                True, power_type != 'ether_wake', True,
                power_type, gepp()),
            node.get_effective_power_info())

    def test_get_effective_power_info_returns_named_tuple(self):
        node = factory.make_Node(power_type="ether_wake")
        # Ensure that can_be_started and can_be_stopped have different
        # values by specifying a MAC address for ether_wake.
        gepp = self.patch(node, "get_effective_power_parameters")
        gepp.return_value = {"mac_address": sentinel.mac_addr}
        self.assertThat(
            node.get_effective_power_info(),
            MatchesStructure.byEquality(
                can_be_started=True,
                can_be_stopped=False,
                can_be_queried=False,
                power_type="ether_wake",
                power_parameters={
                    "mac_address": sentinel.mac_addr,
                },
            ),
        )

    def test_get_effective_kernel_options_with_nothing_set(self):
        node = factory.make_Node()
        self.assertEqual((None, None), node.get_effective_kernel_options())

    def test_get_effective_kernel_options_sees_global_config(self):
        node = factory.make_Node()
        kernel_opts = factory.make_string()
        Config.objects.set_config('kernel_opts', kernel_opts)
        self.assertEqual(
            (None, kernel_opts), node.get_effective_kernel_options())

    def test_get_effective_kernel_options_not_confused_by_None_opts(self):
        node = factory.make_Node()
        tag = factory.make_Tag()
        node.tags.add(tag)
        kernel_opts = factory.make_string()
        Config.objects.set_config('kernel_opts', kernel_opts)
        self.assertEqual(
            (None, kernel_opts), node.get_effective_kernel_options())

    def test_get_effective_kernel_options_not_confused_by_empty_str_opts(self):
        node = factory.make_Node()
        tag = factory.make_Tag(kernel_opts="")
        node.tags.add(tag)
        kernel_opts = factory.make_string()
        Config.objects.set_config('kernel_opts', kernel_opts)
        self.assertEqual(
            (None, kernel_opts), node.get_effective_kernel_options())

    def test_get_effective_kernel_options_multiple_tags_with_opts(self):
        # In this scenario:
        #     global   kernel_opts='fish-n-chips'
        #     tag_a    kernel_opts=null
        #     tag_b    kernel_opts=''
        #     tag_c    kernel_opts='bacon-n-eggs'
        # we require that 'bacon-n-eggs' is chosen as it is the first
        # tag with a valid kernel option.
        Config.objects.set_config('kernel_opts', 'fish-n-chips')
        node = factory.make_Node()
        node.tags.add(factory.make_Tag('tag_a'))
        node.tags.add(factory.make_Tag('tag_b', kernel_opts=''))
        tag_c = factory.make_Tag('tag_c', kernel_opts='bacon-n-eggs')
        node.tags.add(tag_c)

        self.assertEqual(
            (tag_c, 'bacon-n-eggs'), node.get_effective_kernel_options())

    def test_get_effective_kernel_options_ignores_unassociated_tag_value(self):
        node = factory.make_Node()
        factory.make_Tag(kernel_opts=factory.make_string())
        self.assertEqual((None, None), node.get_effective_kernel_options())

    def test_get_effective_kernel_options_uses_tag_value(self):
        node = factory.make_Node()
        tag = factory.make_Tag(kernel_opts=factory.make_string())
        node.tags.add(tag)
        self.assertEqual(
            (tag, tag.kernel_opts), node.get_effective_kernel_options())

    def test_get_effective_kernel_options_tag_overrides_global(self):
        node = factory.make_Node()
        global_opts = factory.make_string()
        Config.objects.set_config('kernel_opts', global_opts)
        tag = factory.make_Tag(kernel_opts=factory.make_string())
        node.tags.add(tag)
        self.assertEqual(
            (tag, tag.kernel_opts), node.get_effective_kernel_options())

    def test_get_effective_kernel_options_uses_first_real_tag_value(self):
        node = factory.make_Node()
        # Intentionally create them in reverse order, so the default 'db' order
        # doesn't work, and we have asserted that we sort them.
        tag3 = factory.make_Tag(
            factory.make_name('tag-03-'),
            kernel_opts=factory.make_string())
        tag2 = factory.make_Tag(
            factory.make_name('tag-02-'),
            kernel_opts=factory.make_string())
        tag1 = factory.make_Tag(factory.make_name('tag-01-'), kernel_opts=None)
        self.assertTrue(tag1.name < tag2.name)
        self.assertTrue(tag2.name < tag3.name)
        node.tags.add(tag1, tag2, tag3)
        self.assertEqual(
            (tag2, tag2.kernel_opts), node.get_effective_kernel_options())

    def test_acquire(self):
        node = factory.make_Node(status=NODE_STATUS.READY)
        user = factory.make_User()
        token = create_auth_token(user)
        agent_name = factory.make_name('agent-name')
        node.acquire(user, token, agent_name)
        self.assertEqual(
            (user, NODE_STATUS.ALLOCATED, agent_name),
            (node.owner, node.status, node.agent_name))

    def test_start_disk_erasing_changes_state_and_starts_node(self):
        agent_name = factory.make_name('agent-name')
        owner = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=owner, agent_name=agent_name)
        start_nodes = self.patch(Node.objects, "start_nodes")
        node.start_disk_erasing(owner)
        self.assertEqual(
            (owner, NODE_STATUS.DISK_ERASING, agent_name),
            (node.owner, node.status, node.agent_name))
        self.assertThat(start_nodes, MockCalledOnceWith(
            [node.system_id], owner, user_data=ANY))

    def test_abort_disk_erasing_changes_state_and_stops_node(self):
        agent_name = factory.make_name('agent-name')
        owner = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.DISK_ERASING, owner=owner,
            agent_name=agent_name)
        stop_nodes = self.patch(Node.objects, "stop_nodes")
        stop_nodes.return_value = [node]
        node.abort_disk_erasing(owner)
        self.assertEqual(
            (owner, NODE_STATUS.FAILED_DISK_ERASING, agent_name),
            (node.owner, node.status, node.agent_name))
        self.assertThat(stop_nodes, MockCalledOnceWith(
            [node.system_id], owner))

    def test_start_disk_erasing_reverts_to_sane_state_on_error(self):
        # If start_disk_erasing encounters an error when calling
        # start_nodes(), it will transition the node to a sane state.
        # Failures encountered in one call to start_disk_erasing() won't
        # affect subsequent calls.
        admin = factory.make_admin()
        nodes = [
            factory.make_Node(
                status=NODE_STATUS.ALLOCATED, power_type="virsh")
            for _ in range(3)
            ]
        generate_user_data = self.patch(disk_erasing, 'generate_user_data')
        start_nodes = self.patch(Node.objects, 'start_nodes')
        start_nodes.side_effect = [
            None,
            MultipleFailures(
                Failure(NoConnectionsAvailable())),
            None,
            ]

        with transaction.atomic():
            for node in nodes:
                try:
                    node.start_disk_erasing(admin)
                except RPC_EXCEPTIONS:
                    # Suppress all the expected errors coming out of
                    # start_disk_erasing() because they're tested
                    # eleswhere.
                    pass

        expected_calls = (
            call(
                [node.system_id], admin,
                user_data=generate_user_data.return_value)
            for node in nodes)
        self.assertThat(
            start_nodes, MockCallsMatch(*expected_calls))
        self.assertEqual(
            [
                NODE_STATUS.DISK_ERASING,
                NODE_STATUS.FAILED_DISK_ERASING,
                NODE_STATUS.DISK_ERASING,
            ],
            [node.status for node in nodes])

    def test_start_disk_erasing_logs_and_raises_errors_in_starting(self):
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        maaslog = self.patch(node_module, 'maaslog')
        exception = NoConnectionsAvailable(factory.make_name())
        self.patch(Node.objects, 'start_nodes').side_effect = exception
        self.assertRaises(
            NoConnectionsAvailable, node.start_disk_erasing, admin)
        self.assertEqual(NODE_STATUS.FAILED_DISK_ERASING, node.status)
        self.assertThat(
            maaslog.error, MockCalledOnceWith(
                "%s: Unable to start node: %s",
                node.hostname, unicode(exception)))

    def test_abort_operation_aborts_disk_erasing(self):
        agent_name = factory.make_name('agent-name')
        owner = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.DISK_ERASING, owner=owner,
            agent_name=agent_name)
        abort_disk_erasing = self.patch_autospec(node, 'abort_disk_erasing')
        node.abort_operation(owner)
        self.assertThat(abort_disk_erasing, MockCalledOnceWith(owner))

    def test_abort_operation_raises_exception_for_unsupported_state(self):
        agent_name = factory.make_name('agent-name')
        owner = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.READY, owner=owner,
            agent_name=agent_name)
        self.assertRaises(NodeStateViolation, node.abort_operation, owner)

    def test_abort_disk_erasing_reverts_to_sane_state_on_error(self):
        # If start_disk_erasing encounters an error when calling
        # start_nodes(), it will transition the node to a sane state.
        # Failures encountered in one call to start_disk_erasing() won't
        # affect subsequent calls.
        admin = factory.make_admin()
        nodes = [
            factory.make_Node(
                status=NODE_STATUS.DISK_ERASING, power_type="virsh")
            for _ in range(3)
            ]
        stop_nodes = self.patch(Node.objects, 'stop_nodes')
        stop_nodes.return_value = [
            [node] for node in nodes
            ]
        stop_nodes.side_effect = [
            None,
            MultipleFailures(
                Failure(NoConnectionsAvailable())),
            None,
            ]

        with transaction.atomic():
            for node in nodes:
                try:
                    node.abort_disk_erasing(admin)
                except RPC_EXCEPTIONS:
                    # Suppress all the expected errors coming out of
                    # abort_disk_erasing() because they're tested
                    # eleswhere.
                    pass

        self.assertThat(
            stop_nodes, MockCallsMatch(
                *(call([node.system_id], admin) for node in nodes)))
        self.assertEqual(
            [
                NODE_STATUS.FAILED_DISK_ERASING,
                NODE_STATUS.DISK_ERASING,
                NODE_STATUS.FAILED_DISK_ERASING,
            ],
            [node.status for node in nodes])

    def test_abort_disk_erasing_logs_and_raises_errors_in_stopping(self):
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.DISK_ERASING)
        maaslog = self.patch(node_module, 'maaslog')
        exception = NoConnectionsAvailable(factory.make_name())
        self.patch(Node.objects, 'stop_nodes').side_effect = exception
        self.assertRaises(
            NoConnectionsAvailable, node.abort_disk_erasing, admin)
        self.assertEqual(NODE_STATUS.DISK_ERASING, node.status)
        self.assertThat(
            maaslog.error, MockCalledOnceWith(
                "%s: Unable to shut node down: %s",
                node.hostname, unicode(exception)))

    def test_release_node_that_has_power_on_and_controlled_power_type(self):
        self.patch(node_module, 'wait_for_power_commands')
        agent_name = factory.make_name('agent-name')
        owner = factory.make_User()
        # Use a "controlled" power type (i.e. a power type for which we
        # can query the status of the node).
        power_type = random.choice(QUERY_POWER_TYPES)
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=owner, agent_name=agent_name,
            power_type=power_type)
        node.power_state = POWER_STATE.ON
        node.release()
        self.expectThat(node.status, Equals(NODE_STATUS.RELEASING))
        self.expectThat(node.owner, Equals(owner))
        self.expectThat(node.agent_name, Equals(''))
        self.expectThat(node.token, Is(None))
        self.expectThat(node.netboot, Is(True))
        self.expectThat(node.osystem, Equals(''))
        self.expectThat(node.distro_series, Equals(''))
        self.expectThat(node.license_key, Equals(''))

    def test_release_node_that_has_power_on_and_uncontrolled_power_type(self):
        self.patch(node_module, 'wait_for_power_commands')
        agent_name = factory.make_name('agent-name')
        owner = factory.make_User()
        # Use an "uncontrolled" power type (i.e. a power type for which we
        # cannot query the status of the node).
        all_power_types = {
            power_type_details['name']
            for power_type_details in JSON_POWER_TYPE_PARAMETERS
        }
        uncontrolled_power_types = list(
            all_power_types.difference(QUERY_POWER_TYPES))
        power_type = random.choice(uncontrolled_power_types)
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=owner, agent_name=agent_name,
            power_type=power_type)
        node.power_state = POWER_STATE.ON
        node.release()
        self.expectThat(node.status, Equals(NODE_STATUS.READY))
        self.expectThat(node.owner, Is(None))
        self.expectThat(node.agent_name, Equals(''))
        self.expectThat(node.token, Is(None))
        self.expectThat(node.netboot, Is(True))
        self.expectThat(node.osystem, Equals(''))
        self.expectThat(node.distro_series, Equals(''))
        self.expectThat(node.license_key, Equals(''))

    def test_release_node_that_has_power_off(self):
        agent_name = factory.make_name('agent-name')
        owner = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=owner, agent_name=agent_name)
        node.power_state = POWER_STATE.OFF
        node.release()
        self.expectThat(node.status, Equals(NODE_STATUS.READY))
        self.expectThat(node.owner, Is(None))
        self.expectThat(node.agent_name, Equals(''))
        self.expectThat(node.token, Is(None))
        self.expectThat(node.netboot, Is(True))
        self.expectThat(node.osystem, Equals(''))
        self.expectThat(node.distro_series, Equals(''))
        self.expectThat(node.license_key, Equals(''))

    def test_release_deletes_static_ip_host_maps(self):
        remove_host_maps = self.patch_autospec(
            node_module, "remove_host_maps")
        user = factory.make_User()
        node = factory.make_node_with_mac_attached_to_nodegroupinterface(
            owner=user, status=NODE_STATUS.ALLOCATED)
        sips = node.get_primary_mac().claim_static_ips()
        node.release()
        expected = {sip.ip.format() for sip in sips}
        self.assertThat(
            remove_host_maps, MockCalledOnceWith(
                {node.nodegroup: expected}))

    def test_dynamic_ip_addresses_queries_leases(self):
        node = factory.make_Node()
        macs = [factory.make_MACAddress(node=node) for _ in range(2)]
        leases = [
            factory.make_DHCPLease(
                nodegroup=node.nodegroup, mac=mac.mac_address)
            for mac in macs]
        self.assertItemsEqual(
            [lease.ip for lease in leases], node.dynamic_ip_addresses())

    def test_dynamic_ip_addresses_uses_result_cache(self):
        # dynamic_ip_addresses has a specialized code path for the case where
        # the node group's set of DHCP leases is already cached in Django's
        # ORM.  This test exercises that code path.
        node = factory.make_Node()
        macs = [factory.make_MACAddress(node=node) for _ in range(2)]
        leases = [
            factory.make_DHCPLease(
                nodegroup=node.nodegroup, mac=mac.mac_address)
            for mac in macs]
        # Other nodes in the nodegroup have leases, but those are not
        # relevant here.
        factory.make_DHCPLease(nodegroup=node.nodegroup)

        # Don't address the node directly; address it through a query with
        # prefetched DHCP leases, to ensure that the query cache for those
        # leases on the nodegroup will be populated.
        query = Node.objects.filter(id=node.id)
        query = query.prefetch_related('nodegroup__dhcplease_set')
        # The cache is populated.  This is the condition that triggers the
        # separate code path in Node.dynamic_ip_addresses().
        self.assertIsNotNone(
            query[0].nodegroup.dhcplease_set.all()._result_cache)

        # dynamic_ip_addresses() still returns the node's leased addresses.
        num_queries, addresses = count_queries(query[0].dynamic_ip_addresses)
        # It only takes one query: to get the node's MAC addresses.
        self.assertEqual(1, num_queries)
        # The result is not a query set, so this isn't hiding a further query.
        no_queries, _ = count_queries(list, addresses)
        self.assertEqual(0, no_queries)
        # We still get exactly the right IP addresses.
        self.assertItemsEqual([lease.ip for lease in leases], addresses)

    def test_dynamic_ip_addresses_filters_by_mac_addresses(self):
        node = factory.make_Node()
        # Another node in the same nodegroup has some IP leases.  The one thing
        # that tells ip_addresses what nodes these leases belong to are their
        # MAC addresses.
        other_node = factory.make_Node(nodegroup=node.nodegroup)
        macs = [factory.make_MACAddress(node=node) for _ in range(2)]
        for mac in macs:
            factory.make_DHCPLease(
                nodegroup=node.nodegroup, mac=mac.mac_address)
        # The other node's leases do not get mistaken for ones that belong to
        # our original node.
        self.assertItemsEqual([], other_node.dynamic_ip_addresses())

    def test_static_ip_addresses_returns_static_ip_addresses(self):
        node = factory.make_Node()
        [mac2, mac3] = [
            factory.make_MACAddress(node=node) for _ in range(2)]
        ip1 = factory.make_StaticIPAddress(mac=mac2)
        ip2 = factory.make_StaticIPAddress(mac=mac3)
        # Create another node with a static IP address.
        other_node = factory.make_Node(nodegroup=node.nodegroup, mac=True)
        factory.make_StaticIPAddress(mac=other_node.macaddress_set.all()[0])
        self.assertItemsEqual([ip1.ip, ip2.ip], node.static_ip_addresses())

    def test_static_ip_addresses_uses_result_cache(self):
        # static_ip_addresses has a specialized code path for the case where
        # the node's static IPs are already cached in Django's ORM.  This
        # test exercises that code path.
        node = factory.make_Node()
        [mac2, mac3] = [
            factory.make_MACAddress(node=node) for _ in range(2)]
        ip1 = factory.make_StaticIPAddress(mac=mac2)
        ip2 = factory.make_StaticIPAddress(mac=mac3)

        # Don't address the node directly; address it through a query with
        # prefetched static IPs, to ensure that the query cache for those
        # IP addresses.
        query = Node.objects.filter(id=node.id)
        query = query.prefetch_related('macaddress_set__ip_addresses')

        # dynamic_ip_addresses() still returns the node's leased addresses.
        num_queries, addresses = count_queries(query[0].static_ip_addresses)
        self.assertEqual(0, num_queries)
        # The result is not a query set, so this isn't hiding a further query.
        self.assertIsInstance(addresses, list)
        # We still get exactly the right IP addresses.
        self.assertItemsEqual([ip1.ip, ip2.ip], addresses)

    def test_ip_addresses_returns_static_ip_addresses_if_allocated(self):
        # If both static and dynamic IP addresses are present, the static
        # addresses take precedence: they are allocated and deallocated in
        # a synchronous fashion whereas the dynamic addresses are updated
        # periodically.
        node = factory.make_Node(mac=True, disable_ipv4=False)
        mac = node.macaddress_set.all()[0]
        # Create a dynamic IP attached to the node.
        factory.make_DHCPLease(
            nodegroup=node.nodegroup, mac=mac.mac_address)
        # Create a static IP attached to the node.
        ip = factory.make_StaticIPAddress(mac=mac)
        self.assertItemsEqual([ip.ip], node.ip_addresses())

    def test_ip_addresses_returns_dynamic_ip_if_no_static_ip(self):
        node = factory.make_Node(mac=True, disable_ipv4=False)
        lease = factory.make_DHCPLease(
            nodegroup=node.nodegroup,
            mac=node.macaddress_set.all()[0].mac_address)
        self.assertItemsEqual([lease.ip], node.ip_addresses())

    def test_ip_addresses_includes_static_ipv4_addresses_by_default(self):
        node = factory.make_Node(disable_ipv4=False)
        ipv4_address = factory.make_ipv4_address()
        ipv6_address = factory.make_ipv6_address()
        self.patch(node, 'static_ip_addresses').return_value = [
            ipv4_address,
            ipv6_address,
            ]
        self.assertItemsEqual(
            [ipv4_address, ipv6_address],
            node.ip_addresses())

    def test_ip_addresses_includes_dynamic_ipv4_addresses_by_default(self):
        node = factory.make_Node(disable_ipv4=False)
        ipv4_address = factory.make_ipv4_address()
        ipv6_address = factory.make_ipv6_address()
        self.patch(node, 'dynamic_ip_addresses').return_value = [
            ipv4_address,
            ipv6_address,
            ]
        self.assertItemsEqual(
            [ipv4_address, ipv6_address],
            node.ip_addresses())

    def test_ip_addresses_strips_static_ipv4_addresses_if_ipv4_disabled(self):
        node = factory.make_Node(disable_ipv4=True)
        ipv4_address = factory.make_ipv4_address()
        ipv6_address = factory.make_ipv6_address()
        self.patch(node, 'static_ip_addresses').return_value = [
            ipv4_address,
            ipv6_address,
            ]
        self.assertEqual([ipv6_address], node.ip_addresses())

    def test_ip_addresses_strips_dynamic_ipv4_addresses_if_ipv4_disabled(self):
        node = factory.make_Node(disable_ipv4=True)
        ipv4_address = factory.make_ipv4_address()
        ipv6_address = factory.make_ipv6_address()
        self.patch(node, 'dynamic_ip_addresses').return_value = [
            ipv4_address,
            ipv6_address,
            ]
        self.assertEqual([ipv6_address], node.ip_addresses())

    def test_get_static_ip_mappings_returns_static_ip_and_mac(self):
        node = factory.make_Node(mac=True, disable_ipv4=False)
        [mac] = node.macaddress_set.all()
        sip = factory.make_StaticIPAddress(mac=mac)
        self.assertEqual(
            [(sip.ip, mac.mac_address)],
            node.get_static_ip_mappings())

    def test_get_static_ip_mappings_returns_mappings_for_all_macs(self):
        node = factory.make_Node(disable_ipv4=False)
        mac1 = factory.make_MACAddress(node=node)
        mac2 = factory.make_MACAddress(node=node)
        sip1 = factory.make_StaticIPAddress(mac=mac1)
        sip2 = factory.make_StaticIPAddress(mac=mac2)
        self.assertItemsEqual(
            [
                (sip1.ip, mac1.mac_address),
                (sip2.ip, mac2.mac_address),
            ],
            node.get_static_ip_mappings())

    def test_get_static_ip_mappings_includes_multiple_addresses(self):
        node = factory.make_Node(mac=True, disable_ipv4=False)
        [mac] = node.macaddress_set.all()
        sip1 = factory.make_StaticIPAddress(mac=mac)
        sip2 = factory.make_StaticIPAddress(mac=mac)
        self.assertItemsEqual(
            [
                (sip1.ip, mac.mac_address),
                (sip2.ip, mac.mac_address),
            ],
            node.get_static_ip_mappings())

    def test_get_static_ip_mappings_ignores_dynamic_addresses(self):
        node = factory.make_Node(mac=True, disable_ipv4=False)
        [mac] = node.macaddress_set.all()
        factory.make_DHCPLease(nodegroup=node.nodegroup, mac=mac.mac_address)
        self.assertEqual([], node.get_static_ip_mappings())

    def test_release_turns_on_netboot(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())
        node.set_netboot(on=False)
        node.release()
        self.assertTrue(node.netboot)

    def test_release_clears_osystem_and_distro_series(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())
        node.osystem = factory.make_name('os')
        node.distro_series = factory.make_name('series')
        node.release()
        self.assertEqual("", node.osystem)
        self.assertEqual("", node.distro_series)

    def test_release_powers_off_node(self):
        stop_nodes = self.patch_autospec(Node.objects, "stop_nodes")
        user = factory.make_User()
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=user, power_type='virsh')
        node.release()
        self.assertThat(
            stop_nodes, MockCalledOnceWith([node.system_id], user))

    def test_release_deallocates_static_ips(self):
        deallocate = self.patch(StaticIPAddressManager, 'deallocate_by_node')
        deallocate.return_value = set()
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User(),
            power_type='ether_wake')
        node.release()
        self.assertThat(deallocate, MockCalledOnceWith(node))

    def test_release_updates_dns(self):
        change_dns_zones = self.patch(dns_config, 'change_dns_zones')
        nodegroup = factory.make_NodeGroup(
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
            status=NODEGROUP_STATUS.ACCEPTED)
        node = factory.make_Node(
            nodegroup=nodegroup, status=NODE_STATUS.ALLOCATED,
            owner=factory.make_User(), power_type='ether_wake')
        node.release()
        self.assertThat(change_dns_zones, MockCalledOnceWith([node.nodegroup]))

    def test_release_logs_and_raises_errors_in_stopping(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED)
        maaslog = self.patch(node_module, 'maaslog')
        exception = NoConnectionsAvailable(factory.make_name())
        self.patch(Node.objects, 'stop_nodes').side_effect = exception
        self.assertRaises(NoConnectionsAvailable, node.release)
        self.assertEqual(NODE_STATUS.DEPLOYED, node.status)
        self.assertThat(
            maaslog.error, MockCalledOnceWith(
                "%s: Unable to shut node down: %s",
                node.hostname, unicode(exception)))

    def test_release_reverts_to_sane_state_on_error(self):
        # If release() encounters an error when stopping the node, it
        # will leave the node in its previous state (i.e. DEPLOYED).
        nodes = [
            factory.make_Node(
                status=NODE_STATUS.DEPLOYED, power_type="virsh")
            for _ in range(3)
            ]
        stop_nodes = self.patch(Node.objects, 'stop_nodes')
        stop_nodes.return_value = [
            [node] for node in nodes
            ]
        stop_nodes.side_effect = [
            None,
            MultipleFailures(
                Failure(NoConnectionsAvailable())),
            None,
            ]

        with transaction.atomic():
            for node in nodes:
                try:
                    node.release()
                except RPC_EXCEPTIONS:
                    # Suppress all expected errors; we test for them
                    # elsewhere.
                    pass

        self.assertThat(
            stop_nodes, MockCallsMatch(
                *(call([node.system_id], None) for node in nodes)))
        self.assertEqual(
            [
                NODE_STATUS.RELEASING,
                NODE_STATUS.DEPLOYED,
                NODE_STATUS.RELEASING,
            ],
            [node.status for node in nodes])

    def test_accept_enlistment_gets_node_out_of_declared_state(self):
        # If called on a node in New state, accept_enlistment()
        # changes the node's status, and returns the node.
        target_state = NODE_STATUS.COMMISSIONING

        node = factory.make_Node(status=NODE_STATUS.NEW)
        return_value = node.accept_enlistment(factory.make_User())
        self.assertEqual((node, target_state), (return_value, node.status))

    def test_accept_enlistment_does_nothing_if_already_accepted(self):
        # If a node has already been accepted, but not assigned a role
        # yet, calling accept_enlistment on it is meaningless but not an
        # error.  The method returns None in this case.
        accepted_states = [
            NODE_STATUS.COMMISSIONING,
            NODE_STATUS.READY,
            ]
        nodes = {
            status: factory.make_Node(status=status)
            for status in accepted_states}

        return_values = {
            status: node.accept_enlistment(factory.make_User())
            for status, node in nodes.items()}

        self.assertEqual(
            {status: None for status in accepted_states}, return_values)
        self.assertEqual(
            {status: status for status in accepted_states},
            {status: node.status for status, node in nodes.items()})

    def test_accept_enlistment_rejects_bad_state_change(self):
        # If a node is neither New nor in one of the "accepted"
        # states where acceptance is a safe no-op, accept_enlistment
        # raises a node state violation and leaves the node's state
        # unchanged.
        all_states = map_enum(NODE_STATUS).values()
        acceptable_states = [
            NODE_STATUS.NEW,
            NODE_STATUS.COMMISSIONING,
            NODE_STATUS.READY,
            ]
        unacceptable_states = set(all_states) - set(acceptable_states)
        nodes = {
            status: factory.make_Node(status=status)
            for status in unacceptable_states}

        exceptions = {status: False for status in unacceptable_states}
        for status, node in nodes.items():
            try:
                node.accept_enlistment(factory.make_User())
            except NodeStateViolation:
                exceptions[status] = True

        self.assertEqual(
            {status: True for status in unacceptable_states}, exceptions)
        self.assertEqual(
            {status: status for status in unacceptable_states},
            {status: node.status for status, node in nodes.items()})

    def test_start_commissioning_changes_status_and_starts_node(self):
        node = factory.make_Node(
            status=NODE_STATUS.NEW, power_type='ether_wake')
        start_nodes = self.patch(Node.objects, "start_nodes")
        start_nodes.return_value = [node]
        factory.make_MACAddress(node=node)
        admin = factory.make_admin()
        node.start_commissioning(admin)

        expected_attrs = {
            'status': NODE_STATUS.COMMISSIONING,
        }
        self.assertAttributes(node, expected_attrs)
        self.assertThat(start_nodes, MockCalledOnceWith(
            [node.system_id], admin, user_data=ANY))

    def test_start_commissioning_sets_user_data(self):
        start_nodes = self.patch(Node.objects, "start_nodes")

        node = factory.make_Node(status=NODE_STATUS.NEW)
        user_data = factory.make_string().encode('ascii')
        generate_user_data = self.patch(
            commissioning, 'generate_user_data')
        generate_user_data.return_value = user_data
        admin = factory.make_admin()
        node.start_commissioning(admin)
        self.assertThat(start_nodes, MockCalledOnceWith(
            [node.system_id], admin, user_data=user_data))

    def test_start_commissioning_clears_node_commissioning_results(self):
        node = factory.make_Node(status=NODE_STATUS.NEW)
        NodeResult.objects.store_data(
            node, factory.make_string(),
            random.randint(0, 10),
            RESULT_TYPE.COMMISSIONING,
            Bin(factory.make_bytes()))
        node.start_commissioning(factory.make_admin())
        self.assertItemsEqual([], node.noderesult_set.all())

    def test_start_commissioning_ignores_other_commissioning_results(self):
        node = factory.make_Node()
        filename = factory.make_string()
        data = factory.make_bytes()
        script_result = random.randint(0, 10)
        NodeResult.objects.store_data(
            node, filename, script_result, RESULT_TYPE.COMMISSIONING,
            Bin(data))
        other_node = factory.make_Node(status=NODE_STATUS.NEW)
        other_node.start_commissioning(factory.make_admin())
        self.assertEqual(
            data, NodeResult.objects.get_data(node, filename))

    def test_start_commissioning_reverts_to_sane_state_on_error(self):
        # When start_commissioning encounters an error when trying to
        # start the node, it will revert the node to its previous
        # status.
        admin = factory.make_admin()
        nodes = [
            factory.make_Node(status=NODE_STATUS.NEW, power_type="ether_wake")
            for _ in range(3)
            ]
        generate_user_data = self.patch(commissioning, 'generate_user_data')
        start_nodes = self.patch(Node.objects, 'start_nodes')
        start_nodes.side_effect = [
            None,
            MultipleFailures(
                Failure(NoConnectionsAvailable())),
            None,
            ]

        with transaction.atomic():
            for node in nodes:
                try:
                    node.start_commissioning(admin)
                except RPC_EXCEPTIONS:
                    # Suppress all expected errors; we test for them
                    # elsewhere.
                    pass

        expected_calls = (
            call(
                [node.system_id], admin,
                user_data=generate_user_data.return_value)
            for node in nodes)
        self.assertThat(
            start_nodes, MockCallsMatch(*expected_calls))
        self.assertEqual(
            [
                NODE_STATUS.COMMISSIONING,
                NODE_STATUS.NEW,
                NODE_STATUS.COMMISSIONING
            ],
            [node.status for node in nodes])

    def test_start_commissioning_logs_and_raises_errors_in_starting(self):
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.NEW)
        maaslog = self.patch(node_module, 'maaslog')
        exception = NoConnectionsAvailable(factory.make_name())
        self.patch(Node.objects, 'start_nodes').side_effect = exception
        self.assertRaises(
            NoConnectionsAvailable, node.start_commissioning, admin)
        self.assertEqual(NODE_STATUS.NEW, node.status)
        self.assertThat(
            maaslog.error, MockCalledOnceWith(
                "%s: Unable to start node: %s",
                node.hostname, unicode(exception)))

    def test_abort_commissioning_reverts_to_sane_state_on_error(self):
        # If abort commissioning hits an error when trying to stop the
        # node, it will revert the node to the state it was in before
        # abort_commissioning() was called.
        admin = factory.make_admin()
        nodes = [
            factory.make_Node(
                status=NODE_STATUS.COMMISSIONING, power_type="virsh")
            for _ in range(3)
            ]
        stop_nodes = self.patch(Node.objects, 'stop_nodes')
        stop_nodes.return_value = [
            [node] for node in nodes
            ]
        stop_nodes.side_effect = [
            None,
            MultipleFailures(
                Failure(NoConnectionsAvailable())),
            None,
            ]

        with transaction.atomic():
            for node in nodes:
                try:
                    node.abort_commissioning(admin)
                except RPC_EXCEPTIONS:
                    # Suppress all expected errors; we test for them
                    # elsewhere.
                    pass

        self.assertThat(
            stop_nodes, MockCallsMatch(
                *(call([node.system_id], admin) for node in nodes)))
        self.assertEqual(
            [
                NODE_STATUS.NEW,
                NODE_STATUS.COMMISSIONING,
                NODE_STATUS.NEW,
            ],
            [node.status for node in nodes])

    def test_abort_commissioning_logs_and_raises_errors_in_stopping(self):
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        maaslog = self.patch(node_module, 'maaslog')
        exception = NoConnectionsAvailable(factory.make_name())
        self.patch(Node.objects, 'stop_nodes').side_effect = exception
        self.assertRaises(
            NoConnectionsAvailable, node.abort_commissioning, admin)
        self.assertEqual(NODE_STATUS.COMMISSIONING, node.status)
        self.assertThat(
            maaslog.error, MockCalledOnceWith(
                "%s: Unable to shut node down: %s",
                node.hostname, unicode(exception)))

    def test_abort_commissioning_changes_status_and_stops_node(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, power_type='virsh')
        admin = factory.make_admin()

        stop_nodes = self.patch_autospec(Node.objects, "stop_nodes")
        stop_nodes.return_value = [node]

        node.abort_commissioning(admin)
        expected_attrs = {
            'status': NODE_STATUS.NEW,
        }
        self.assertAttributes(node, expected_attrs)
        self.assertThat(
            stop_nodes, MockCalledOnceWith([node.system_id], admin))

    def test_abort_commisssioning_errors_if_node_is_not_commissioning(self):
        unaccepted_statuses = set(map_enum(NODE_STATUS).values())
        unaccepted_statuses.remove(NODE_STATUS.COMMISSIONING)
        for status in unaccepted_statuses:
            node = factory.make_Node(
                status=status, power_type='virsh')
            self.assertRaises(
                NodeStateViolation, node.abort_commissioning,
                factory.make_admin())

    def test_full_clean_checks_status_transition_and_raises_if_invalid(self):
        # RETIRED -> ALLOCATED is an invalid transition.
        node = factory.make_Node(
            status=NODE_STATUS.RETIRED, owner=factory.make_User())
        node.status = NODE_STATUS.ALLOCATED
        self.assertRaisesRegexp(
            NodeStateViolation,
            "Invalid transition: Retired -> Allocated.",
            node.full_clean)

    def test_full_clean_passes_if_status_unchanged(self):
        status = factory.pick_choice(NODE_STATUS_CHOICES)
        node = factory.make_Node(status=status)
        node.status = status
        node.full_clean()
        # The test is that this does not raise an error.
        pass

    def test_full_clean_passes_if_status_valid_transition(self):
        # NODE_STATUS.READY -> NODE_STATUS.ALLOCATED is a valid
        # transition.
        status = NODE_STATUS.READY
        node = factory.make_Node(status=status)
        node.status = NODE_STATUS.ALLOCATED
        node.full_clean()
        # The test is that this does not raise an error.
        pass

    def test_save_raises_node_state_violation_on_bad_transition(self):
        # RETIRED -> ALLOCATED is an invalid transition.
        node = factory.make_Node(
            status=NODE_STATUS.RETIRED, owner=factory.make_User())
        node.status = NODE_STATUS.ALLOCATED
        self.assertRaisesRegexp(
            NodeStateViolation,
            "Invalid transition: Retired -> Allocated.",
            node.save)

    def test_netboot_defaults_to_True(self):
        node = Node()
        self.assertTrue(node.netboot)

    def test_nodegroup_cannot_be_null(self):
        node = factory.make_Node()
        node.nodegroup = None
        self.assertRaises(ValidationError, node.save)

    def test_fqdn_returns_hostname_if_dns_not_managed(self):
        nodegroup = factory.make_NodeGroup(
            name=factory.make_string(),
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        hostname_with_domain = '%s.%s' % (
            factory.make_string(), factory.make_string())
        node = factory.make_Node(
            nodegroup=nodegroup, hostname=hostname_with_domain)
        self.assertEqual(hostname_with_domain, node.fqdn)

    def test_fqdn_replaces_hostname_if_dns_is_managed(self):
        hostname_without_domain = factory.make_name('hostname')
        hostname_with_domain = '%s.%s' % (
            hostname_without_domain, factory.make_string())
        domain = factory.make_name('domain')
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ACCEPTED,
            name=domain,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        node = factory.make_Node(
            hostname=hostname_with_domain, nodegroup=nodegroup)
        expected_hostname = '%s.%s' % (hostname_without_domain, domain)
        self.assertEqual(expected_hostname, node.fqdn)

    def test_boot_type_has_fastpath_set_by_default(self):
        node = factory.make_Node()
        self.assertEqual(NODE_BOOT.FASTPATH, node.boot_type)

    def test_split_arch_returns_arch_as_tuple(self):
        main_arch = factory.make_name('arch')
        sub_arch = factory.make_name('subarch')
        full_arch = '%s/%s' % (main_arch, sub_arch)
        node = factory.make_Node(architecture=full_arch)
        self.assertEqual((main_arch, sub_arch), node.split_arch())

    def test_mac_addresses_on_managed_interfaces_returns_only_managed(self):
        node = factory.make_node_with_mac_attached_to_nodegroupinterface(
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        mac_with_interface = node.get_primary_mac()

        mac_with_no_interface = factory.make_MACAddress(node=node)
        unmanaged_interface = factory.make_NodeGroupInterface(
            nodegroup=node.nodegroup,
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        mac_with_unmanaged_interface = factory.make_MACAddress(
            node=node, cluster_interface=unmanaged_interface)
        ignore_unused(mac_with_no_interface, mac_with_unmanaged_interface)

        observed = node.mac_addresses_on_managed_interfaces()
        self.assertItemsEqual([mac_with_interface], observed)

    def test_mac_addresses_on_managed_interfaces_returns_empty_if_none(self):
        node = factory.make_Node(mac=True)
        observed = node.mac_addresses_on_managed_interfaces()
        self.assertItemsEqual([], observed)

    def test_mark_failed_updates_status(self):
        nodes_mapping = {
            status: factory.make_Node(status=status)
            for status in NODE_FAILURE_STATUS_TRANSITIONS
        }
        for node in nodes_mapping.values():
            node.mark_failed(factory.make_name('error-description'))
        self.assertEqual(
            NODE_FAILURE_STATUS_TRANSITIONS,
            {status: node.status for status, node in nodes_mapping.items()})

    def test_mark_failed_updates_error_description(self):
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        description = factory.make_name('error-description')
        node.mark_failed(description)
        self.assertEqual(description, reload_object(node).error_description)

    def test_mark_failed_raises_for_unauthorized_node_status(self):
        but_not = NODE_FAILURE_STATUS_TRANSITIONS.keys()
        but_not.extend(NODE_FAILURE_STATUS_TRANSITIONS.viewvalues())
        status = factory.pick_choice(NODE_STATUS_CHOICES, but_not=but_not)
        node = factory.make_Node(status=status)
        description = factory.make_name('error-description')
        self.assertRaises(NodeStateViolation, node.mark_failed, description)

    def test_mark_failed_ignores_if_already_failed(self):
        status = random.choice([
            NODE_STATUS.FAILED_DEPLOYMENT, NODE_STATUS.FAILED_COMMISSIONING])
        node = factory.make_Node(status=status)
        description = factory.make_name('error-description')
        node.mark_failed(description)
        self.assertEqual(status, node.status)

    def test_mark_broken_changes_status_to_broken(self):
        node = factory.make_Node(
            status=NODE_STATUS.NEW, owner=factory.make_User())
        node.mark_broken(factory.make_name('error-description'))
        self.assertEqual(NODE_STATUS.BROKEN, reload_object(node).status)

    def test_mark_broken_releases_allocated_node(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())
        err_desc = factory.make_name('error-description')
        release = self.patch(node, 'release')
        node.mark_broken(err_desc)
        self.expectThat(node.owner, Is(None))
        self.assertThat(release, MockCalledOnceWith())

    def test_mark_fixed_changes_status(self):
        node = factory.make_Node(status=NODE_STATUS.BROKEN)
        node.mark_fixed()
        self.assertEqual(NODE_STATUS.READY, reload_object(node).status)

    def test_mark_fixed_updates_error_description(self):
        description = factory.make_name('error-description')
        node = factory.make_Node(
            status=NODE_STATUS.BROKEN, error_description=description)
        node.mark_fixed()
        self.assertEqual('', reload_object(node).error_description)

    def test_mark_fixed_fails_if_node_isnt_broken(self):
        status = factory.pick_choice(
            NODE_STATUS_CHOICES, but_not=[NODE_STATUS.BROKEN])
        node = factory.make_Node(status=status)
        self.assertRaises(NodeStateViolation, node.mark_fixed)

    def test_update_power_state(self):
        node = factory.make_Node()
        state = factory.pick_enum(POWER_STATE)
        node.update_power_state(state)
        self.assertEqual(state, reload_object(node).power_state)

    def test_update_power_state_readies_node_if_releasing(self):
        node = factory.make_Node(
            power_state=POWER_STATE.ON, status=NODE_STATUS.RELEASING,
            owner=None)
        node.update_power_state(POWER_STATE.OFF)
        self.expectThat(node.status, Equals(NODE_STATUS.READY))
        self.expectThat(node.owner, Is(None))

    def test_update_power_state_does_not_change_status_if_not_releasing(self):
        node = factory.make_Node(
            power_state=POWER_STATE.ON, status=NODE_STATUS.ALLOCATED)
        node.update_power_state(POWER_STATE.OFF)
        self.assertThat(node.status, Equals(NODE_STATUS.ALLOCATED))

    def test_update_power_state_does_not_change_status_if_not_off(self):
        node = factory.make_Node(
            power_state=POWER_STATE.OFF, status=NODE_STATUS.ALLOCATED)
        node.update_power_state(POWER_STATE.ON)
        self.expectThat(node.status, Equals(NODE_STATUS.ALLOCATED))

    def test_end_deployment_changes_state(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYING)
        node.end_deployment()
        self.assertEqual(NODE_STATUS.DEPLOYED, reload_object(node).status)

    def test_start_deployment_changes_state(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        # Do not start the transaction monitor.
        self.patch(node, 'start_transition_monitor')
        node.start_deployment()
        self.assertEqual(NODE_STATUS.DEPLOYING, reload_object(node).status)

    def test_start_deployment_starts_monitor(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        monitor_timeout = random.randint(1, 100)
        self.patch(node, 'get_deployment_time').return_value = monitor_timeout
        mock_start_transition_monitor = self.patch(
            node, 'start_transition_monitor')
        node.start_deployment()
        self.assertThat(
            mock_start_transition_monitor, MockCalledOnceWith(monitor_timeout))

    def test_handle_monitor_expired_marks_node_as_failed(self):
        status = random.choice(MONITORED_STATUSES)
        node = factory.make_Node(status=status)
        timeout = random.randint(1, 100)
        monitor_context = {
            'timeout': timeout,
        }
        node.handle_monitor_expired(monitor_context)
        node = reload_object(node)
        self.assertEqual(get_failed_status(status), node.status)
        error_msg = (
            "Node operation '%s' timed out after %s." % (
                NODE_STATUS_CHOICES_DICT[status],
                timedelta(seconds=timeout))
        )
        self.assertEqual(error_msg, node.error_description)

    def test_handle_monitor_expired_ignores_event_if_node_state_changed(self):
        status = factory.pick_enum(NODE_STATUS, but_not=MONITORED_STATUSES)
        node = factory.make_Node(status=status)
        node.handle_monitor_expired({})
        node = reload_object(node)
        self.assertEqual(status, node.status)

    def test_get_boot_purpose_known_node(self):
        # The following table shows the expected boot "purpose" for each set
        # of node parameters.
        options = [
            ("poweroff", {"status": NODE_STATUS.NEW}),
            ("commissioning", {"status": NODE_STATUS.COMMISSIONING}),
            ("commissioning", {"status": NODE_STATUS.DISK_ERASING}),
            ("poweroff", {"status": NODE_STATUS.FAILED_COMMISSIONING}),
            ("poweroff", {"status": NODE_STATUS.MISSING}),
            ("poweroff", {"status": NODE_STATUS.READY}),
            ("poweroff", {"status": NODE_STATUS.RESERVED}),
            ("install", {"status": NODE_STATUS.DEPLOYING, "netboot": True}),
            ("xinstall", {"status": NODE_STATUS.DEPLOYING, "netboot": True}),
            ("local", {"status": NODE_STATUS.DEPLOYING, "netboot": False}),
            ("local", {"status": NODE_STATUS.DEPLOYED}),
            ("poweroff", {"status": NODE_STATUS.RETIRED}),
            ]
        node = factory.make_Node(boot_type=NODE_BOOT.DEBIAN)
        mock_get_boot_images_for = self.patch(
            preseed_module, 'get_boot_images_for')
        for purpose, parameters in options:
            boot_image = make_rpc_boot_image(purpose=purpose)
            mock_get_boot_images_for.return_value = [boot_image]
            if purpose == "xinstall":
                node.boot_type = NODE_BOOT.FASTPATH
            for name, value in parameters.items():
                setattr(node, name, value)
            self.assertEqual(purpose, node.get_boot_purpose())

    def test_get_boot_purpose_osystem_no_xinstall_support(self):
        osystem = make_usable_osystem(self)
        release = osystem['default_release']
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING, netboot=True,
            osystem=osystem['name'], distro_series=release,
            boot_type=NODE_BOOT.FASTPATH)
        boot_image = make_rpc_boot_image(purpose='install')
        self.patch(
            preseed_module, 'get_boot_images_for').return_value = [boot_image]
        self.assertEqual('install', node.get_boot_purpose())

    def test_pxe_mac_default_is_none(self):
        node = factory.make_Node()
        self.assertIsNone(node.pxe_mac)

    def test_get_pxe_mac_returns_pxe_mac_if_pxe_mac_set(self):
        node = factory.make_Node(mac=True)
        node.pxe_mac = factory.make_MACAddress(node=node)
        node.save()
        self.assertEqual(node.pxe_mac, node.get_pxe_mac())

    def test_get_pxe_mac_returns_first_macaddress_if_pxe_mac_unset(self):
        node = factory.make_Node(mac=True)
        factory.make_MACAddress(node=node)
        self.assertEqual(node.macaddress_set.first(), node.get_pxe_mac())


class NodeRoutersTest(MAASServerTestCase):

    def test_routers_stores_mac_address(self):
        node = factory.make_Node()
        macs = [MAC('aa:bb:cc:dd:ee:ff')]
        node.routers = macs
        node.save()
        self.assertEqual(macs, reload_object(node).routers)

    def test_routers_stores_multiple_mac_addresses(self):
        node = factory.make_Node()
        macs = [MAC('aa:bb:cc:dd:ee:ff'), MAC('00:11:22:33:44:55')]
        node.routers = macs
        node.save()
        self.assertEqual(macs, reload_object(node).routers)

    def test_routers_can_append(self):
        node = factory.make_Node()
        mac1 = MAC('aa:bb:cc:dd:ee:ff')
        mac2 = MAC('00:11:22:33:44:55')
        node.routers = [mac1]
        node.save()
        node = reload_object(node)
        node.routers.append(mac2)
        node.save()
        self.assertEqual([mac1, mac2], reload_object(node).routers)


class NodeTransitionsTests(MAASServerTestCase):
    """Test the structure of NODE_TRANSITIONS."""

    def test_NODE_TRANSITIONS_initial_states(self):
        allowed_states = set(NODE_STATUS_CHOICES_DICT.keys() + [None])

        self.assertTrue(set(NODE_TRANSITIONS.keys()) <= allowed_states)

    def test_NODE_TRANSITIONS_destination_state(self):
        all_destination_states = []
        for destination_states in NODE_TRANSITIONS.values():
            all_destination_states.extend(destination_states)
        allowed_states = set(NODE_STATUS_CHOICES_DICT.keys())

        self.assertTrue(set(all_destination_states) <= allowed_states)


class NodeManagerTest(MAASServerTestCase):

    def make_node(self, user=None, **kwargs):
        """Create a node, allocated to `user` if given."""
        if user is None:
            status = NODE_STATUS.READY
        else:
            status = NODE_STATUS.ALLOCATED
        return factory.make_Node(status=status, owner=user, **kwargs)

    def make_node_with_mac(self, user=None, **kwargs):
        node = self.make_node(user, **kwargs)
        mac = factory.make_MACAddress(node=node)
        return node, mac

    def make_user_data(self):
        """Create a blob of arbitrary user-data."""
        return factory.make_string().encode('ascii')

    def test_filter_by_ids_filters_nodes_by_ids(self):
        nodes = [factory.make_Node() for counter in range(5)]
        ids = [node.system_id for node in nodes]
        selection = slice(1, 3)
        self.assertItemsEqual(
            nodes[selection],
            Node.objects.filter_by_ids(Node.objects.all(), ids[selection]))

    def test_filter_by_ids_with_empty_list_returns_empty(self):
        factory.make_Node()
        self.assertItemsEqual(
            [], Node.objects.filter_by_ids(Node.objects.all(), []))

    def test_filter_by_ids_without_ids_returns_full(self):
        node = factory.make_Node()
        self.assertItemsEqual(
            [node], Node.objects.filter_by_ids(Node.objects.all(), None))

    def test_get_nodes_for_user_lists_visible_nodes(self):
        """get_nodes with perm=NODE_PERMISSION.VIEW lists the nodes a user
        has access to.

        When run for a regular user it returns unowned nodes, and nodes
        owned by that user.
        """
        user = factory.make_User()
        visible_nodes = [self.make_node(owner) for owner in [None, user]]
        self.make_node(factory.make_User())
        self.assertItemsEqual(
            visible_nodes, Node.objects.get_nodes(user, NODE_PERMISSION.VIEW))

    def test_get_nodes_admin_lists_all_nodes(self):
        admin = factory.make_admin()
        owners = [
            None,
            factory.make_User(),
            factory.make_admin(),
            admin,
            ]
        nodes = [self.make_node(owner) for owner in owners]
        self.assertItemsEqual(
            nodes, Node.objects.get_nodes(admin, NODE_PERMISSION.VIEW))

    def test_get_nodes_filters_by_id(self):
        user = factory.make_User()
        nodes = [self.make_node(user) for counter in range(5)]
        ids = [node.system_id for node in nodes]
        wanted_slice = slice(0, 3)
        self.assertItemsEqual(
            nodes[wanted_slice],
            Node.objects.get_nodes(
                user, NODE_PERMISSION.VIEW, ids=ids[wanted_slice]))

    def test_get_nodes_filters_from_nodes(self):
        admin = factory.make_admin()
        # Node that we want to see in the result:
        wanted_node = factory.make_Node()
        # Node that we'll exclude from from_nodes:
        factory.make_Node()

        self.assertItemsEqual(
            [wanted_node],
            Node.objects.get_nodes(
                admin, NODE_PERMISSION.VIEW,
                from_nodes=Node.objects.filter(id=wanted_node.id)))

    def test_get_nodes_combines_from_nodes_with_other_filter(self):
        user = factory.make_User()
        # Node that we want to see in the result:
        matching_node = factory.make_Node(owner=user)
        # Node that we'll exclude from from_nodes:
        factory.make_Node(owner=user)
        # Node that will be ignored on account of belonging to someone else:
        invisible_node = factory.make_Node(owner=factory.make_User())

        self.assertItemsEqual(
            [matching_node],
            Node.objects.get_nodes(
                user, NODE_PERMISSION.VIEW,
                from_nodes=Node.objects.filter(id__in=(
                    matching_node.id,
                    invisible_node.id,
                    ))))

    def test_get_nodes_with_edit_perm_for_user_lists_owned_nodes(self):
        user = factory.make_User()
        visible_node = self.make_node(user)
        self.make_node(None)
        self.make_node(factory.make_User())
        self.assertItemsEqual(
            [visible_node],
            Node.objects.get_nodes(user, NODE_PERMISSION.EDIT))

    def test_get_nodes_with_edit_perm_admin_lists_all_nodes(self):
        admin = factory.make_admin()
        owners = [
            None,
            factory.make_User(),
            factory.make_admin(),
            admin,
            ]
        nodes = [self.make_node(owner) for owner in owners]
        self.assertItemsEqual(
            nodes, Node.objects.get_nodes(admin, NODE_PERMISSION.EDIT))

    def test_get_nodes_with_admin_perm_returns_empty_list_for_user(self):
        user = factory.make_User()
        [self.make_node(user) for counter in range(5)]
        self.assertItemsEqual(
            [],
            Node.objects.get_nodes(user, NODE_PERMISSION.ADMIN))

    def test_get_nodes_with_admin_perm_returns_all_nodes_for_admin(self):
        user = factory.make_User()
        nodes = [self.make_node(user) for counter in range(5)]
        self.assertItemsEqual(
            nodes,
            Node.objects.get_nodes(
                factory.make_admin(), NODE_PERMISSION.ADMIN))

    def test_get_visible_node_or_404_ok(self):
        """get_node_or_404 fetches nodes by system_id."""
        user = factory.make_User()
        node = self.make_node(user)
        self.assertEqual(
            node,
            Node.objects.get_node_or_404(
                node.system_id, user, NODE_PERMISSION.VIEW))

    def test_get_available_nodes_finds_available_nodes(self):
        user = factory.make_User()
        node1 = self.make_node(None)
        node2 = self.make_node(None)
        self.assertItemsEqual(
            [node1, node2],
            Node.objects.get_available_nodes_for_acquisition(user))

    def test_get_available_node_returns_empty_list_if_empty(self):
        user = factory.make_User()
        self.assertEqual(
            [], list(Node.objects.get_available_nodes_for_acquisition(user)))

    def test_get_available_nodes_ignores_taken_nodes(self):
        user = factory.make_User()
        available_status = NODE_STATUS.READY
        unavailable_statuses = (
            set(NODE_STATUS_CHOICES_DICT) - set([available_status]))
        for status in unavailable_statuses:
            factory.make_Node(status=status)
        self.assertEqual(
            [], list(Node.objects.get_available_nodes_for_acquisition(user)))

    def test_get_available_node_ignores_invisible_nodes(self):
        user = factory.make_User()
        node = self.make_node()
        node.owner = factory.make_User()
        node.save()
        self.assertEqual(
            [], list(Node.objects.get_available_nodes_for_acquisition(user)))

    def test_netboot_on(self):
        node = factory.make_Node(netboot=False)
        node.set_netboot(True)
        self.assertTrue(node.netboot)

    def test_netboot_off(self):
        node = factory.make_Node(netboot=True)
        node.set_netboot(False)
        self.assertFalse(node.netboot)

    def test_release_or_erase_erases_when_enabled(self):
        owner = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=owner)
        Config.objects.set_config(
            'enable_disk_erasing_on_release', True)
        erase_mock = self.patch_autospec(node, 'start_disk_erasing')
        release_mock = self.patch_autospec(node, 'release')
        node.release_or_erase()
        self.assertThat(erase_mock, MockCalledOnceWith(owner))
        self.assertThat(release_mock, MockNotCalled())

    def test_release_or_erase_releases_when_disabled(self):
        owner = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=owner)
        Config.objects.set_config(
            'enable_disk_erasing_on_release', False)
        erase_mock = self.patch_autospec(node, 'start_disk_erasing')
        release_mock = self.patch_autospec(node, 'release')
        node.release_or_erase()
        self.assertThat(release_mock, MockCalledOnceWith())
        self.assertThat(erase_mock, MockNotCalled())


class NodeManagerTest_StartNodes(MAASServerTestCase):

    def setUp(self):
        super(NodeManagerTest_StartNodes, self).setUp()
        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        self.rpc_fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())

    def prepare_rpc_to_cluster(self, nodegroup):
        protocol = self.rpc_fixture.makeCluster(
            nodegroup, cluster_module.CreateHostMaps, cluster_module.PowerOn,
            cluster_module.StartMonitors)
        protocol.CreateHostMaps.side_effect = always_succeed_with({})
        protocol.StartMonitors.side_effect = always_succeed_with({})
        protocol.PowerOn.side_effect = always_succeed_with({})
        return protocol

    def make_acquired_nodes_with_macs(self, user, nodegroup=None, count=3):
        nodes = []
        for _ in xrange(count):
            node = factory.make_node_with_mac_attached_to_nodegroupinterface(
                nodegroup=nodegroup, status=NODE_STATUS.READY)
            self.prepare_rpc_to_cluster(node.nodegroup)
            node.acquire(user)
            nodes.append(node)
        return nodes

    def test__sets_user_data(self):
        user = factory.make_User()
        nodegroup = factory.make_NodeGroup()
        self.prepare_rpc_to_cluster(nodegroup)
        nodes = self.make_acquired_nodes_with_macs(user, nodegroup)
        user_data = factory.make_bytes()

        with TwistedLoggerFixture() as twisted_log:
            Node.objects.start_nodes(
                list(node.system_id for node in nodes),
                user, user_data=user_data)

        # All three nodes have been given the same user data.
        nuds = NodeUserData.objects.filter(
            node_id__in=(node.id for node in nodes))
        self.assertEqual({user_data}, {nud.data for nud in nuds})
        # No complaints are made to the Twisted log.
        self.assertFalse(twisted_log.containsError(), twisted_log.output)

    def test__resets_user_data(self):
        user = factory.make_User()
        nodegroup = factory.make_NodeGroup()
        self.prepare_rpc_to_cluster(nodegroup)
        nodes = self.make_acquired_nodes_with_macs(user, nodegroup)

        with TwistedLoggerFixture() as twisted_log:
            Node.objects.start_nodes(
                list(node.system_id for node in nodes),
                user, user_data=None)

        # All three nodes have been given the same user data.
        nuds = NodeUserData.objects.filter(
            node_id__in=(node.id for node in nodes))
        self.assertThat(list(nuds), HasLength(0))
        # No complaints are made to the Twisted log.
        self.assertFalse(twisted_log.containsError(), twisted_log.output)

    def test__claims_static_ip_addresses(self):
        user = factory.make_User()
        nodegroup = factory.make_NodeGroup()
        self.prepare_rpc_to_cluster(nodegroup)
        nodes = self.make_acquired_nodes_with_macs(user, nodegroup)

        claim_static_ip_addresses = self.patch_autospec(
            Node, "claim_static_ip_addresses", spec_set=False)
        claim_static_ip_addresses.return_value = {}

        with TwistedLoggerFixture() as twisted_log:
            Node.objects.start_nodes(
                list(node.system_id for node in nodes), user)

        for node in nodes:
            self.expectThat(claim_static_ip_addresses, MockAnyCall(node))
        # No complaints are made to the Twisted log.
        self.assertFalse(twisted_log.containsError(), twisted_log.output)

    def test__claims_static_ip_addresses_for_allocated_nodes_only(self):
        user = factory.make_User()
        nodegroup = factory.make_NodeGroup()
        self.prepare_rpc_to_cluster(nodegroup)
        nodes = self.make_acquired_nodes_with_macs(user, nodegroup, count=2)

        # Change the status of the first node to something other than
        # allocated.
        broken_node, allocated_node = nodes
        broken_node.status = NODE_STATUS.BROKEN
        broken_node.save()

        claim_static_ip_addresses = self.patch_autospec(
            Node, "claim_static_ip_addresses", spec_set=False)
        claim_static_ip_addresses.return_value = {}

        with TwistedLoggerFixture() as twisted_log:
            Node.objects.start_nodes(
                list(node.system_id for node in nodes), user)

        # Only one call is made to claim_static_ip_addresses(), for the
        # still-allocated node.
        self.assertThat(
            claim_static_ip_addresses,
            MockCalledOnceWith(allocated_node))
        # No complaints are made to the Twisted log.
        self.assertFalse(twisted_log.containsError(), twisted_log.output)

    def test__updates_host_maps(self):
        user = factory.make_User()
        nodes = self.make_acquired_nodes_with_macs(user)

        update_host_maps = self.patch(node_module, "update_host_maps")
        update_host_maps.return_value = []  # No failures.

        with TwistedLoggerFixture() as twisted_log:
            Node.objects.start_nodes(
                list(node.system_id for node in nodes), user)

        # Host maps are updated.
        self.assertThat(
            update_host_maps, MockCalledOnceWith({
                node.nodegroup: {
                    ip_address.ip: mac.mac_address
                    for ip_address in mac.ip_addresses.all()
                }
                for node in nodes
                for mac in node.mac_addresses_on_managed_interfaces()
            }))
        # No complaints are made to the Twisted log.
        self.assertFalse(twisted_log.containsError(), twisted_log.output)

    def test__propagates_errors_when_updating_host_maps(self):
        user = factory.make_User()
        nodes = self.make_acquired_nodes_with_macs(user)

        update_host_maps = self.patch(node_module, "update_host_maps")
        update_host_maps.return_value = [
            Failure(AssertionError("That is so not true")),
            Failure(ZeroDivisionError("I cannot defy mathematics")),
        ]

        with TwistedLoggerFixture() as twisted_log:
            error = self.assertRaises(
                MultipleFailures, Node.objects.start_nodes,
                list(node.system_id for node in nodes), user)

        self.assertSequenceEqual(
            update_host_maps.return_value, error.args)

        # No complaints are made to the Twisted log.
        self.assertFalse(twisted_log.containsError(), twisted_log.output)

    def test__updates_dns(self):
        user = factory.make_User()
        nodes = self.make_acquired_nodes_with_macs(user)

        change_dns_zones = self.patch(dns_config, "change_dns_zones")

        with TwistedLoggerFixture() as twisted_log:
            Node.objects.start_nodes(
                list(node.system_id for node in nodes), user)

        self.assertThat(
            change_dns_zones, MockCalledOnceWith(
                {node.nodegroup for node in nodes}))

        # No complaints are made to the Twisted log.
        self.assertFalse(twisted_log.containsError(), twisted_log.output)

    def test__starts_nodes(self):
        user = factory.make_User()
        nodes = self.make_acquired_nodes_with_macs(user)
        power_infos = list(
            node.get_effective_power_info()
            for node in nodes)

        power_on_nodes = self.patch(node_module, "power_on_nodes")
        power_on_nodes.return_value = {}

        with TwistedLoggerFixture() as twisted_log:
            Node.objects.start_nodes(
                list(node.system_id for node in nodes), user)

        self.assertThat(power_on_nodes, MockCalledOnceWith(ANY))

        nodes_start_info_observed = power_on_nodes.call_args[0][0]
        nodes_start_info_expected = [
            (node.system_id, node.hostname, node.nodegroup.uuid, power_info)
            for node, power_info in izip(nodes, power_infos)
        ]

        # If the following fails the diff is big, but it's useful.
        self.maxDiff = None

        self.assertItemsEqual(
            nodes_start_info_expected,
            nodes_start_info_observed)

        # No complaints are made to the Twisted log.
        self.assertFalse(twisted_log.containsError(), twisted_log.output)

    def test__raises_failures_for_nodes_that_cannot_be_started(self):
        power_on_nodes = self.patch(node_module, "power_on_nodes")
        power_on_nodes.return_value = {
            factory.make_name("system_id"): defer.fail(
                ZeroDivisionError("Defiance is futile")),
            factory.make_name("system_id"): defer.succeed({}),
        }

        failures = self.assertRaises(
            MultipleFailures, Node.objects.start_nodes, [],
            factory.make_User())
        [failure] = failures.args
        self.assertThat(failure.value, IsInstance(ZeroDivisionError))

    def test__marks_allocated_node_as_deploying(self):
        user = factory.make_User()
        [node] = self.make_acquired_nodes_with_macs(user, count=1)
        nodes_started = Node.objects.start_nodes([node.system_id], user)
        self.assertItemsEqual([node], nodes_started)
        self.assertEqual(
            NODE_STATUS.DEPLOYING, reload_object(node).status)

    def test__does_not_change_state_of_deployed_node(self):
        user = factory.make_User()
        node = factory.make_Node(
            power_type='ether_wake', status=NODE_STATUS.DEPLOYED,
            owner=user)
        factory.make_MACAddress(node=node)
        power_on_nodes = self.patch(node_module, "power_on_nodes")
        power_on_nodes.return_value = {
            node.system_id: defer.succeed({}),
        }
        nodes_started = Node.objects.start_nodes([node.system_id], user)
        self.assertItemsEqual([node], nodes_started)
        self.assertEqual(
            NODE_STATUS.DEPLOYED, reload_object(node).status)

    def test__only_returns_nodes_for_which_power_commands_have_been_sent(self):
        user = factory.make_User()
        node1, node2 = self.make_acquired_nodes_with_macs(user, count=2)
        node1.power_type = 'ether_wake'  # Can be started.
        node1.save()
        node2.power_type = ''  # Undefined power type, cannot be started.
        node2.save()
        nodes_started = Node.objects.start_nodes(
            [node1.system_id, node2.system_id], user)
        self.assertItemsEqual([node1], nodes_started)


class NodeManagerTest_StopNodes(MAASServerTestCase):

    def make_nodes_with_macs(self, user, nodegroup=None, count=3):
        nodes = []
        for _ in xrange(count):
            node = factory.make_node_with_mac_attached_to_nodegroupinterface(
                nodegroup=nodegroup, status=NODE_STATUS.READY,
                power_type='virsh')
            node.acquire(user)
            nodes.append(node)
        return nodes

    def test_stop_nodes_stops_nodes(self):
        wait_for_power_commands = self.patch_autospec(
            node_module, 'wait_for_power_commands')
        power_off_nodes = self.patch_autospec(node_module, "power_off_nodes")
        power_off_nodes.side_effect = lambda nodes: {
            system_id: Deferred() for system_id, _, _, _ in nodes}

        user = factory.make_User()
        nodes = self.make_nodes_with_macs(user)
        power_infos = list(node.get_effective_power_info() for node in nodes)

        stop_mode = factory.make_name('stop-mode')
        nodes_stopped = Node.objects.stop_nodes(
            list(node.system_id for node in nodes), user, stop_mode)

        self.assertItemsEqual(nodes, nodes_stopped)
        self.assertThat(power_off_nodes, MockCalledOnceWith(ANY))
        self.assertThat(wait_for_power_commands, MockCalledOnceWith(ANY))

        nodes_stop_info_observed = power_off_nodes.call_args[0][0]
        nodes_stop_info_expected = [
            (node.system_id, node.hostname, node.nodegroup.uuid, power_info)
            for node, power_info in izip(nodes, power_infos)
        ]

        # The stop mode is added into the power info that's passed.
        for _, _, _, power_info in nodes_stop_info_expected:
            power_info.power_parameters['power_off_mode'] = stop_mode

        # If the following fails the diff is big, but it's useful.
        self.maxDiff = None

        self.assertItemsEqual(
            nodes_stop_info_expected,
            nodes_stop_info_observed)

    def test_stop_nodes_ignores_uneditable_nodes(self):
        owner = factory.make_User()
        nodes = self.make_nodes_with_macs(owner)

        user = factory.make_User()
        nodes_stopped = Node.objects.stop_nodes(
            list(node.system_id for node in nodes), user)

        self.assertItemsEqual([], nodes_stopped)

    def test_stop_nodes_does_not_attempt_power_off_if_no_power_type(self):
        # If the node has a power_type set to UNKNOWN_POWER_TYPE, stop_nodes()
        # won't attempt to power it off.
        user = factory.make_User()
        [node] = self.make_nodes_with_macs(user, count=1)
        node.power_type = ""
        node.save()

        nodes_stopped = Node.objects.stop_nodes([node.system_id], user)
        self.assertItemsEqual([], nodes_stopped)

    def test_stop_nodes_does_not_attempt_power_off_if_cannot_be_stopped(self):
        # If the node has a power_type that MAAS knows stopping does not work,
        # stop_nodes() won't attempt to power it off.
        user = factory.make_User()
        [node] = self.make_nodes_with_macs(user, count=1)
        node.power_type = "ether_wake"
        node.save()

        nodes_stopped = Node.objects.stop_nodes([node.system_id], user)
        self.assertItemsEqual([], nodes_stopped)

    def test__raises_failures_for_nodes_that_cannot_be_stopped(self):
        power_off_nodes = self.patch(node_module, "power_off_nodes")
        power_off_nodes.return_value = {
            factory.make_name("system_id"): defer.fail(
                ZeroDivisionError("Ee by gum lad, that's a rum 'un.")),
            factory.make_name("system_id"): defer.succeed({}),
        }

        failures = self.assertRaises(
            MultipleFailures, Node.objects.stop_nodes, [], factory.make_User())
        [failure] = failures.args
        self.assertThat(failure.value, IsInstance(ZeroDivisionError))


class TestNodeTransitionMonitors(MAASServerTestCase):

    def prepare_rpc(self):
        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        return self.useFixture(MockLiveRegionToClusterRPCFixture())

    def patch_datetime_now(self, nowish_timestamp):
        mock_datetime = self.patch(node_module, "datetime")
        mock_datetime.now.return_value = nowish_timestamp

    def test__start_transition_monitor_starts_monitor(self):
        rpc_fixture = self.prepare_rpc()
        now = datetime.now(tz=amp.utc)
        self.patch_datetime_now(now)
        node = factory.make_Node()
        cluster = rpc_fixture.makeCluster(node.nodegroup, StartMonitors)
        monitor_timeout = random.randint(1, 100)
        node.start_transition_monitor(monitor_timeout)
        monitors = [{
            'deadline': now + timedelta(seconds=monitor_timeout),
            'id': node.system_id,
            'context': {
                'timeout': monitor_timeout,
                'node_status': node.status,
                },
            }]
        self.assertThat(
            cluster.StartMonitors, MockCalledOnceWith(ANY, monitors=monitors)
        )

    def test__start_transition_monitor_copes_with_timeouterror(self):
        now = datetime.now(tz=amp.utc)
        self.patch_datetime_now(now)
        node = factory.make_Node()
        mock_client = Mock()
        mock_client.wait.side_effect = crochet.TimeoutError("error")
        mock_getClientFor = self.patch(node_module, 'getClientFor')
        mock_getClientFor.return_value = mock_client
        monitor_timeout = random.randint(1, 100)
        # The real test is that node.start_transition_monitor doesn't raise
        # an exception.
        self.assertIsNone(node.start_transition_monitor(monitor_timeout))


class TestClaimStaticIPAddresses(MAASTestCase):
    """Tests for `Node.claim_static_ip_addresses`."""

    def test__returns_empty_list_if_no_iface(self):
        node = factory.make_Node()
        self.assertEqual([], node.claim_static_ip_addresses())

    def test__returns_empty_list_if_no_iface_on_managed_network(self):
        node = factory.make_Node()
        factory.make_MACAddress(node=node)
        self.assertEqual([], node.claim_static_ip_addresses())

    def test__returns_mapping_for_iface_on_managed_network(self):
        node = factory.make_node_with_mac_attached_to_nodegroupinterface()
        static_mappings = node.claim_static_ip_addresses()
        [static_ip] = node.static_ip_addresses()
        [mac_address] = node.macaddress_set.all()
        self.assertEqual(
            [(static_ip, unicode(mac_address))],
            static_mappings)

    def test__returns_mapping_for_pxe_mac_interface(self):
        node = factory.make_node_with_mac_attached_to_nodegroupinterface()
        node.pxe_mac = factory.make_MACAddress(node=node)
        node.save()
        [managed_interface] = node.nodegroup.get_managed_interfaces()
        node.pxe_mac.cluster_interface = managed_interface
        node.pxe_mac.save()
        static_mappings = node.claim_static_ip_addresses()
        [static_ip] = node.static_ip_addresses()
        mac_address = node.get_pxe_mac()
        self.assertEqual(
            [(static_ip, unicode(mac_address))],
            static_mappings)

    def test__ignores_mac_address_with_non_auto_addresses(self):
        node = factory.make_node_with_mac_attached_to_nodegroupinterface()
        mac_address = node.macaddress_set.first()
        mac_address.claim_static_ips(IPADDRESS_TYPE.STICKY)
        self.assertRaises(
            StaticIPAddressTypeClash, mac_address.claim_static_ips)
        static_mappings = node.claim_static_ip_addresses()
        self.assertEqual([], static_mappings)


class TestDeploymentStatus(MAASServerTestCase):
    """Tests for node.get_deployment_status."""

    def test_returns_deploying_when_deploying(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYING)
        self.assertEqual("Deploying", node.get_deployment_status())

    def test_returns_deployed_when_deployed(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED)
        self.assertEqual("Deployed", node.get_deployment_status())

    def test_returns_failed_deployment_when_failed_deployment(self):
        node = factory.make_Node(status=NODE_STATUS.FAILED_DEPLOYMENT)
        self.assertEqual("Failed deployment", node.get_deployment_status())

    def test_returns_not_deploying_otherwise(self):
        status = factory.pick_enum(
            NODE_STATUS, but_not=[
                NODE_STATUS.DEPLOYING, NODE_STATUS.DEPLOYED,
                NODE_STATUS.FAILED_DEPLOYMENT
                ]
            )
        node = factory.make_Node(status=status)
        self.assertEqual("Not in deployment", node.get_deployment_status())
