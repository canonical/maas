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

from datetime import timedelta
import random

import celery
from django.core.exceptions import ValidationError
from maasserver.clusterrpc.power_parameters import get_power_types
from maasserver.enum import (
    NODE_PERMISSION,
    NODE_STATUS,
    NODE_STATUS_CHOICES,
    NODE_STATUS_CHOICES_DICT,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.exceptions import (
    NodeStateViolation,
    StaticIPAddressExhaustion,
    )
from maasserver.fields import MAC
from maasserver.models import (
    Config,
    MACAddress,
    Node,
    node as node_module,
    Tag,
    )
from maasserver.models.node import (
    generate_hostname,
    NODE_TRANSITIONS,
    validate_hostname,
    )
from maasserver.models.staticipaddress import StaticIPAddressManager
from maasserver.models.user import create_auth_token
from maasserver.testing import reload_object
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils import (
    ignore_unused,
    map_enum,
    )
from maastesting.djangotestcase import count_queries
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
    )
from maastesting.testcase import MAASTestCase
from metadataserver import commissioning
from metadataserver.fields import Bin
from metadataserver.models import (
    NodeCommissionResult,
    NodeUserData,
    )
from provisioningserver.power.poweraction import PowerAction
from provisioningserver.tasks import Omshell
from testtools.matchers import (
    AllMatch,
    Contains,
    Equals,
    MatchesAll,
    Not,
    )


class UtilitiesTest(MAASTestCase):

    def test_generate_hostname_does_not_contain_ambiguous_chars(self):
        ambiguous_chars = 'ilousvz1250'
        hostnames = [generate_hostname(5) for i in range(200)]
        does_not_contain_chars_matcher = (
            MatchesAll(*[Not(Contains(char)) for char in ambiguous_chars]))
        self.assertThat(
            hostnames, AllMatch(does_not_contain_chars_matcher))

    def test_generate_hostname_uses_size(self):
        sizes = [
            random.randint(1, 10), random.randint(1, 10),
            random.randint(1, 10)]
        hostnames = [generate_hostname(size) for size in sizes]
        self.assertEqual(sizes, [len(hostname) for hostname in hostnames])


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


class NodeTest(MAASServerTestCase):

    def test_system_id(self):
        """
        The generated system_id looks good.

        """
        node = factory.make_node()
        self.assertEqual(len(node.system_id), 41)
        self.assertTrue(node.system_id.startswith('node-'))

    def test_hostname_is_validated(self):
        bad_hostname = '-_?!@*-'
        self.assertRaises(
            ValidationError,
            factory.make_node, hostname=bad_hostname)

    def test_work_queue_returns_nodegroup_uuid(self):
        nodegroup = factory.make_node_group()
        node = factory.make_node(nodegroup=nodegroup)
        self.assertEqual(nodegroup.uuid, node.work_queue)

    def test_display_status_shows_default_status(self):
        node = factory.make_node()
        self.assertEqual(
            NODE_STATUS_CHOICES_DICT[node.status],
            node.display_status())

    def test_display_status_for_allocated_node_shows_owner(self):
        node = factory.make_node(
            owner=factory.make_user(), status=NODE_STATUS.ALLOCATED)
        self.assertEqual(
            "Allocated to %s" % node.owner.username,
            node.display_status())

    def test_add_node_with_token(self):
        user = factory.make_user()
        token = create_auth_token(user)
        node = factory.make_node(token=token)
        self.assertEqual(token, node.token)

    def test_add_mac_address(self):
        mac = factory.getRandomMACAddress()
        node = factory.make_node()
        node.add_mac_address(mac)
        macs = MACAddress.objects.filter(node=node, mac_address=mac).count()
        self.assertEqual(1, macs)

    def test_remove_mac_address(self):
        mac = factory.getRandomMACAddress()
        node = factory.make_node()
        node.add_mac_address(mac)
        node.remove_mac_address(mac)
        self.assertItemsEqual(
            [],
            MACAddress.objects.filter(node=node, mac_address=mac))

    def test_get_primary_mac_returns_mac_address(self):
        node = factory.make_node()
        mac = factory.getRandomMACAddress()
        node.add_mac_address(mac)
        self.assertEqual(mac, node.get_primary_mac().mac_address)

    def test_get_primary_mac_returns_None_if_node_has_no_mac(self):
        node = factory.make_node()
        self.assertIsNone(node.get_primary_mac())

    def test_get_primary_mac_returns_oldest_mac(self):
        node = factory.make_node()
        macs = [factory.getRandomMACAddress() for counter in range(3)]
        offset = timedelta(0)
        for mac in macs:
            mac_address = node.add_mac_address(mac)
            mac_address.created += offset
            mac_address.save()
            offset += timedelta(1)
        self.assertEqual(macs[0], node.get_primary_mac().mac_address)

    def test_get_osystem_returns_default_osystem(self):
        node = factory.make_node(osystem='')
        osystem = Config.objects.get_config('default_osystem')
        self.assertEqual(osystem, node.get_osystem())

    def test_get_distro_series_returns_default_series(self):
        node = factory.make_node(distro_series='')
        series = Config.objects.get_config('default_distro_series')
        self.assertEqual(series, node.get_distro_series())

    def test_delete_node_deletes_related_mac(self):
        node = factory.make_node()
        mac = node.add_mac_address('AA:BB:CC:DD:EE:FF')
        node.delete()
        self.assertRaises(
            MACAddress.DoesNotExist, MACAddress.objects.get, id=mac.id)

    def test_cannot_delete_allocated_node(self):
        node = factory.make_node(status=NODE_STATUS.ALLOCATED)
        self.assertRaises(NodeStateViolation, node.delete)

    def test_delete_node_also_deletes_dhcp_host_map(self):
        lease = factory.make_dhcp_lease()
        node = factory.make_node(nodegroup=lease.nodegroup)
        node.add_mac_address(lease.mac)
        # Prevent actual omshell commands from being called in the task.
        self.patch(Omshell, 'remove')
        node.delete()
        self.assertThat(
            self.celery.tasks[0]['kwargs'],
            Equals({
                'ip_address': lease.ip,
                'server_address': "127.0.0.1",
                'omapi_key': lease.nodegroup.dhcp_key,
                }))

    def test_delete_dynamic_host_maps_sends_to_correct_queue(self):
        lease = factory.make_dhcp_lease()
        node = factory.make_node(nodegroup=lease.nodegroup)
        node.add_mac_address(lease.mac)
        # Prevent actual omshell commands from being called in the task.
        self.patch(Omshell, 'remove')
        option_call = self.patch(celery.canvas.Signature, 'set')
        work_queue = node.work_queue
        node.delete()
        args, kwargs = option_call.call_args
        self.assertEqual(work_queue, kwargs['queue'])

    def test_delete_dynamic_host_maps_leaves_static_addresses_alone(self):
        # DHCPLeases can be associated with host maps written due to
        # staticipaddress entries. When deleting a node, we must not
        # delete those static entries because a) some are permanent, b)
        # they should all get deleted when nodes are released anyway.
        node = factory.make_node_with_mac_attached_to_nodegroupinterface()
        mac = node.get_primary_mac()
        sip = mac.claim_static_ip()
        factory.make_dhcp_lease(
            ip=sip.ip.format(), nodegroup=node.nodegroup,
            mac=mac.mac_address.get_raw())
        # Prevent actual omshell commands from being called in the task.
        self.patch(Omshell, 'remove')
        node.delete()
        self.assertItemsEqual([], self.celery.tasks)

    def test_delete_node_removes_multiple_host_maps(self):
        lease1 = factory.make_dhcp_lease()
        lease2 = factory.make_dhcp_lease(nodegroup=lease1.nodegroup)
        node = factory.make_node(nodegroup=lease1.nodegroup)
        node.add_mac_address(lease1.mac)
        node.add_mac_address(lease2.mac)
        # Prevent actual omshell commands from being called in the task.
        self.patch(Omshell, 'remove')
        node.delete()
        self.assertEqual(2, len(self.celery.tasks))

    def test_set_random_hostname_set_hostname(self):
        # Blank out enlistment_domain.
        Config.objects.set_config("enlistment_domain", '')
        node = factory.make_node('test' * 10)
        node.set_random_hostname()
        self.assertEqual(5, len(node.hostname))

    def test_set_random_hostname_checks_hostname_existence(self):
        Config.objects.set_config("enlistment_domain", '')
        existing_node = factory.make_node(hostname='hostname')

        hostnames = [existing_node.hostname, "new-hostname"]
        self.patch(
            node_module, "generate_hostname",
            lambda size: hostnames.pop(0))

        node = factory.make_node()
        node.set_random_hostname()
        self.assertEqual('new-hostname', node.hostname)

    def test_get_effective_power_type_raises_if_not_set(self):
        node = factory.make_node(power_type='')
        self.assertRaises(
            node_module.UnknownPowerType, node.get_effective_power_type)

    def test_get_effective_power_type_reads_node_field(self):
        power_types = list(get_power_types().keys())  # Python3 proof.
        nodes = [
            factory.make_node(power_type=power_type)
            for power_type in power_types]
        self.assertEqual(
            power_types, [node.get_effective_power_type() for node in nodes])

    def test_power_parameters_are_stored(self):
        node = factory.make_node(power_type='')
        parameters = dict(user="tarquin", address="10.1.2.3")
        node.power_parameters = parameters
        node.save()
        node = reload_object(node)
        self.assertEqual(parameters, node.power_parameters)

    def test_power_parameters_default(self):
        node = factory.make_node(power_type='')
        self.assertEqual('', node.power_parameters)

    def test_get_effective_power_parameters_returns_power_parameters(self):
        params = {'test_parameter': factory.getRandomString()}
        node = factory.make_node(power_parameters=params)
        self.assertEqual(
            params['test_parameter'],
            node.get_effective_power_parameters()['test_parameter'])

    def test_get_effective_power_parameters_adds_system_id(self):
        node = factory.make_node()
        self.assertEqual(
            node.system_id,
            node.get_effective_power_parameters()['system_id'])

    def test_get_effective_power_parameters_adds_mac_if_no_params_set(self):
        node = factory.make_node()
        mac = factory.getRandomMACAddress()
        node.add_mac_address(mac)
        self.assertEqual(
            mac, node.get_effective_power_parameters()['mac_address'])

    def test_get_effective_power_parameters_adds_no_mac_if_params_set(self):
        node = factory.make_node(power_parameters={'foo': 'bar'})
        mac = factory.getRandomMACAddress()
        node.add_mac_address(mac)
        self.assertNotIn('mac', node.get_effective_power_parameters())

    def test_get_effective_power_parameters_provides_usable_defaults(self):
        # For some power types at least, the defaults provided by
        # get_effective_power_parameters are enough to get a basic setup
        # working.
        configless_power_types = [
            'ether_wake',
            'virsh',
            ]
        # We don't actually want to fire off power events, but we'll go
        # through the motions right up to the point where we'd normally
        # run shell commands.
        self.patch(PowerAction, 'run_shell', lambda *args, **kwargs: ('', ''))
        user = factory.make_admin()
        nodes = [
            factory.make_node(power_type=power_type)
            for power_type in configless_power_types]
        for node in nodes:
            node.add_mac_address(factory.getRandomMACAddress())
        node_power_types = {
            node: node.get_effective_power_type()
            for node in nodes}
        started_nodes = Node.objects.start_nodes(
            [node.system_id for node in list(node_power_types.keys())], user)
        successful_types = [node_power_types[node] for node in started_nodes]
        self.assertItemsEqual(configless_power_types, successful_types)

    def test_get_effective_power_type_no_default_power_address_if_not_virsh(
            self):
        node = factory.make_node(power_type="ether_wake")
        params = node.get_effective_power_parameters()
        self.assertEqual("", params["power_address"])

    def test_get_effective_power_type_defaults_power_address_if_virsh(self):
        node = factory.make_node(power_type="virsh")
        params = node.get_effective_power_parameters()
        self.assertEqual("qemu://localhost/system", params["power_address"])

    def test_get_effective_kernel_options_with_nothing_set(self):
        node = factory.make_node()
        self.assertEqual((None, None), node.get_effective_kernel_options())

    def test_get_effective_kernel_options_sees_global_config(self):
        node = factory.make_node()
        kernel_opts = factory.getRandomString()
        Config.objects.set_config('kernel_opts', kernel_opts)
        self.assertEqual(
            (None, kernel_opts), node.get_effective_kernel_options())

    def test_get_effective_kernel_options_not_confused_by_None_opts(self):
        node = factory.make_node()
        tag = factory.make_tag()
        node.tags.add(tag)
        kernel_opts = factory.getRandomString()
        Config.objects.set_config('kernel_opts', kernel_opts)
        self.assertEqual(
            (None, kernel_opts), node.get_effective_kernel_options())

    def test_get_effective_kernel_options_not_confused_by_empty_str_opts(self):
        node = factory.make_node()
        tag = factory.make_tag(kernel_opts="")
        node.tags.add(tag)
        kernel_opts = factory.getRandomString()
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
        node = factory.make_node()
        node.tags.add(factory.make_tag('tag_a'))
        node.tags.add(factory.make_tag('tag_b', kernel_opts=''))
        tag_c = factory.make_tag('tag_c', kernel_opts='bacon-n-eggs')
        node.tags.add(tag_c)

        self.assertEqual(
            (tag_c, 'bacon-n-eggs'), node.get_effective_kernel_options())

    def test_get_effective_kernel_options_ignores_unassociated_tag_value(self):
        node = factory.make_node()
        factory.make_tag(kernel_opts=factory.getRandomString())
        self.assertEqual((None, None), node.get_effective_kernel_options())

    def test_get_effective_kernel_options_uses_tag_value(self):
        node = factory.make_node()
        tag = factory.make_tag(kernel_opts=factory.getRandomString())
        node.tags.add(tag)
        self.assertEqual(
            (tag, tag.kernel_opts), node.get_effective_kernel_options())

    def test_get_effective_kernel_options_tag_overrides_global(self):
        node = factory.make_node()
        global_opts = factory.getRandomString()
        Config.objects.set_config('kernel_opts', global_opts)
        tag = factory.make_tag(kernel_opts=factory.getRandomString())
        node.tags.add(tag)
        self.assertEqual(
            (tag, tag.kernel_opts), node.get_effective_kernel_options())

    def test_get_effective_kernel_options_uses_first_real_tag_value(self):
        node = factory.make_node()
        # Intentionally create them in reverse order, so the default 'db' order
        # doesn't work, and we have asserted that we sort them.
        tag3 = factory.make_tag(factory.make_name('tag-03-'),
                                kernel_opts=factory.getRandomString())
        tag2 = factory.make_tag(factory.make_name('tag-02-'),
                                kernel_opts=factory.getRandomString())
        tag1 = factory.make_tag(factory.make_name('tag-01-'), kernel_opts=None)
        self.assertTrue(tag1.name < tag2.name)
        self.assertTrue(tag2.name < tag3.name)
        node.tags.add(tag1, tag2, tag3)
        self.assertEqual(
            (tag2, tag2.kernel_opts), node.get_effective_kernel_options())

    def test_acquire(self):
        node = factory.make_node(status=NODE_STATUS.READY)
        user = factory.make_user()
        token = create_auth_token(user)
        agent_name = factory.make_name('agent-name')
        node.acquire(user, token, agent_name)
        self.assertEqual(
            (user, NODE_STATUS.ALLOCATED, agent_name),
            (node.owner, node.status, node.agent_name))

    def test_release(self):
        agent_name = factory.make_name('agent-name')
        node = factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_user(),
            agent_name=agent_name)
        node.release()
        self.assertEqual(
            (NODE_STATUS.READY, None, node.agent_name),
            (node.status, node.owner, ''))

    def test_release_deletes_static_ip_host_maps(self):
        user = factory.make_user()
        node = factory.make_node_with_mac_attached_to_nodegroupinterface(
            owner=user, status=NODE_STATUS.ALLOCATED)
        sip = node.get_primary_mac().claim_static_ip()
        delete_static_host_maps = self.patch(node, 'delete_static_host_maps')
        node.release()
        expected = [sip.ip.format()]
        self.assertThat(delete_static_host_maps, MockCalledOnceWith(expected))

    def test_delete_static_host_maps(self):
        user = factory.make_user()
        node = factory.make_node_with_mac_attached_to_nodegroupinterface(
            owner=user, status=NODE_STATUS.ALLOCATED)
        sip = node.get_primary_mac().claim_static_ip()
        self.patch(Omshell, 'remove')
        set_call = self.patch(celery.canvas.Signature, 'set')
        node.delete_static_host_maps([sip.ip.format()])
        self.assertThat(
            self.celery.tasks[0]['kwargs'],
            Equals({
                'ip_address': sip.ip.format(),
                'server_address': "127.0.0.1",
                'omapi_key': node.nodegroup.dhcp_key,
                }))
        args, kwargs = set_call.call_args
        self.assertEqual(node.work_queue, kwargs['queue'])

    def test_dynamic_ip_addresses_queries_leases(self):
        node = factory.make_node()
        macs = [factory.make_mac_address(node=node) for i in range(2)]
        leases = [
            factory.make_dhcp_lease(
                nodegroup=node.nodegroup, mac=mac.mac_address)
            for mac in macs]
        self.assertItemsEqual(
            [lease.ip for lease in leases], node.dynamic_ip_addresses())

    def test_dynamic_ip_addresses_uses_result_cache(self):
        # dynamic_ip_addresses has a specialized code path for the case where
        # the node group's set of DHCP leases is already cached in Django's
        # ORM.  This test exercises that code path.
        node = factory.make_node()
        macs = [factory.make_mac_address(node=node) for i in range(2)]
        leases = [
            factory.make_dhcp_lease(
                nodegroup=node.nodegroup, mac=mac.mac_address)
            for mac in macs]
        # Other nodes in the nodegroup have leases, but those are not
        # relevant here.
        factory.make_dhcp_lease(nodegroup=node.nodegroup)

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
        node = factory.make_node()
        # Another node in the same nodegroup has some IP leases.  The one thing
        # that tells ip_addresses what nodes these leases belong to are their
        # MAC addresses.
        other_node = factory.make_node(nodegroup=node.nodegroup)
        macs = [factory.make_mac_address(node=node) for i in range(2)]
        for mac in macs:
            factory.make_dhcp_lease(
                nodegroup=node.nodegroup, mac=mac.mac_address)
        # The other node's leases do not get mistaken for ones that belong to
        # our original node.
        self.assertItemsEqual([], other_node.dynamic_ip_addresses())

    def test_static_ip_addresses_returns_static_ip_addresses(self):
        node = factory.make_node()
        [mac2, mac3] = [
            factory.make_mac_address(node=node) for i in range(2)]
        ip1 = factory.make_staticipaddress(mac=mac2)
        ip2 = factory.make_staticipaddress(mac=mac3)
        # Create another node with a static IP address.
        other_node = factory.make_node(nodegroup=node.nodegroup, mac=True)
        factory.make_staticipaddress(mac=other_node.macaddress_set.all()[0])
        self.assertItemsEqual([ip1.ip, ip2.ip], node.static_ip_addresses())

    def test_static_ip_addresses_uses_result_cache(self):
        # static_ip_addresses has a specialized code path for the case where
        # the node's static IPs are already cached in Django's ORM.  This
        # test exercises that code path.
        node = factory.make_node()
        [mac2, mac3] = [
            factory.make_mac_address(node=node) for i in range(2)]
        ip1 = factory.make_staticipaddress(mac=mac2)
        ip2 = factory.make_staticipaddress(mac=mac3)

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

    def test_ip_addresses_returns_static_ip_addresses(self):
        # If both static and dynamic IP addresses are present, the static
        # addresses take precedence: they are allocated and deallocated in
        # a synchronous fashion whereas the dynamic addresses are updated
        # periodically.
        node = factory.make_node(mac=True)
        mac = node.macaddress_set.all()[0]
        # Create a dynamic IP attached to the node.
        factory.make_dhcp_lease(
            nodegroup=node.nodegroup, mac=mac.mac_address)
        # Create a static IP attached to the node.
        ip = factory.make_staticipaddress(mac=mac)
        self.assertItemsEqual([ip.ip], node.ip_addresses())

    def test_ip_addresses_returns_dynamic_ip_if_no_static_ip(self):
        node = factory.make_node(mac=True)
        lease = factory.make_dhcp_lease(
            nodegroup=node.nodegroup,
            mac=node.macaddress_set.all()[0].mac_address)
        self.assertItemsEqual([lease.ip], node.ip_addresses())

    def test_release_turns_on_netboot(self):
        node = factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_user())
        node.set_netboot(on=False)
        node.release()
        self.assertTrue(node.netboot)

    def test_release_clears_osystem_and_distro_series(self):
        node = factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_user())
        osystem = factory.getRandomOS()
        release = factory.getRandomRelease(osystem)
        node.osystem = osystem.name
        node.distro_series = release
        node.release()
        self.assertEqual("", node.osystem)
        self.assertEqual("", node.distro_series)

    def test_release_powers_off_node(self):
        # Test that releasing a node causes a 'power_off' celery job.
        node = factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_user(),
            power_type='virsh')
        # Prevent actual job script from running.
        self.patch(PowerAction, 'run_shell', lambda *args, **kwargs: ('', ''))
        node.release()
        self.assertEqual(
            (1, 'provisioningserver.tasks.power_off'),
            (len(self.celery.tasks), self.celery.tasks[0]['task'].name))

    def test_release_deallocates_static_ips(self):
        deallocate = self.patch(StaticIPAddressManager, 'deallocate_by_node')
        node = factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_user(),
            power_type='ether_wake')
        node.release()
        self.assertThat(deallocate, MockCalledOnceWith(node))

    def test_accept_enlistment_gets_node_out_of_declared_state(self):
        # If called on a node in Declared state, accept_enlistment()
        # changes the node's status, and returns the node.
        target_state = NODE_STATUS.COMMISSIONING

        node = factory.make_node(status=NODE_STATUS.DECLARED)
        return_value = node.accept_enlistment(factory.make_user())
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
            status: factory.make_node(status=status)
            for status in accepted_states}

        return_values = {
            status: node.accept_enlistment(factory.make_user())
            for status, node in nodes.items()}

        self.assertEqual(
            {status: None for status in accepted_states}, return_values)
        self.assertEqual(
            {status: status for status in accepted_states},
            {status: node.status for status, node in nodes.items()})

    def test_accept_enlistment_rejects_bad_state_change(self):
        # If a node is neither Declared nor in one of the "accepted"
        # states where acceptance is a safe no-op, accept_enlistment
        # raises a node state violation and leaves the node's state
        # unchanged.
        all_states = map_enum(NODE_STATUS).values()
        acceptable_states = [
            NODE_STATUS.DECLARED,
            NODE_STATUS.COMMISSIONING,
            NODE_STATUS.READY,
            ]
        unacceptable_states = set(all_states) - set(acceptable_states)
        nodes = {
            status: factory.make_node(status=status)
            for status in unacceptable_states}

        exceptions = {status: False for status in unacceptable_states}
        for status, node in nodes.items():
            try:
                node.accept_enlistment(factory.make_user())
            except NodeStateViolation:
                exceptions[status] = True

        self.assertEqual(
            {status: True for status in unacceptable_states}, exceptions)
        self.assertEqual(
            {status: status for status in unacceptable_states},
            {status: node.status for status, node in nodes.items()})

    def test_start_commissioning_changes_status_and_starts_node(self):
        node = factory.make_node(
            status=NODE_STATUS.DECLARED, power_type='ether_wake')
        factory.make_mac_address(node=node)
        node.start_commissioning(factory.make_admin())

        expected_attrs = {
            'status': NODE_STATUS.COMMISSIONING,
        }
        self.assertAttributes(node, expected_attrs)
        self.assertEqual(
            ['provisioningserver.tasks.power_on'],
            [task['task'].name for task in self.celery.tasks])

    def test_start_commisssioning_doesnt_start_nodes_for_non_admin_users(self):
        node = factory.make_node(
            status=NODE_STATUS.DECLARED, power_type='ether_wake')
        factory.make_mac_address(node=node)
        node.start_commissioning(factory.make_user())

        expected_attrs = {
            'status': NODE_STATUS.COMMISSIONING,
        }
        self.assertAttributes(node, expected_attrs)
        self.assertEqual([], self.celery.tasks)

    def test_start_commissioning_sets_user_data(self):
        node = factory.make_node(status=NODE_STATUS.DECLARED)
        user_data = factory.getRandomString().encode('ascii')
        self.patch(
            commissioning.user_data, 'generate_user_data'
            ).return_value = user_data
        node.start_commissioning(factory.make_admin())
        self.assertEqual(user_data, NodeUserData.objects.get_user_data(node))
        commissioning.user_data.generate_user_data.assert_called_with(
            nodegroup=node.nodegroup)

    def test_start_commissioning_clears_node_commissioning_results(self):
        node = factory.make_node(status=NODE_STATUS.DECLARED)
        NodeCommissionResult.objects.store_data(
            node, factory.getRandomString(),
            random.randint(0, 10),
            Bin(factory.getRandomBytes()))
        node.start_commissioning(factory.make_admin())
        self.assertItemsEqual([], node.nodecommissionresult_set.all())

    def test_start_commissioning_ignores_other_commissioning_results(self):
        node = factory.make_node()
        filename = factory.getRandomString()
        data = factory.getRandomBytes()
        script_result = random.randint(0, 10)
        NodeCommissionResult.objects.store_data(
            node, filename, script_result, Bin(data))
        other_node = factory.make_node(status=NODE_STATUS.DECLARED)
        other_node.start_commissioning(factory.make_admin())
        self.assertEqual(
            data, NodeCommissionResult.objects.get_data(node, filename))

    def test_abort_commissioning_changes_status_and_stops_node(self):
        self.patch(PowerAction, 'run_shell').return_value = ('', '')
        node = factory.make_node(
            status=NODE_STATUS.COMMISSIONING, power_type='virsh')
        node.abort_commissioning(factory.make_admin())
        expected_attrs = {
            'status': NODE_STATUS.DECLARED,
        }
        self.assertAttributes(node, expected_attrs)
        self.assertEqual(
            ['provisioningserver.tasks.power_off'],
            [task['task'].name for task in self.celery.tasks])

    def test_abort_commisssioning_doesnt_stop_nodes_for_non_admin_users(self):
        node = factory.make_node(
            status=NODE_STATUS.COMMISSIONING, power_type='virsh')
        node.abort_commissioning(factory.make_user())
        expected_attrs = {
            'status': NODE_STATUS.COMMISSIONING,
        }
        self.assertAttributes(node, expected_attrs)
        self.assertEqual([], self.celery.tasks)

    def test_abort_commisssioning_errors_if_node_is_not_commissioning(self):
        unaccepted_statuses = set(map_enum(NODE_STATUS).values())
        unaccepted_statuses.remove(NODE_STATUS.COMMISSIONING)
        for status in unaccepted_statuses:
            node = factory.make_node(
                status=status, power_type='virsh')
            self.assertRaises(
                NodeStateViolation, node.abort_commissioning,
                factory.make_admin())

    def test_full_clean_checks_status_transition_and_raises_if_invalid(self):
        # RETIRED -> ALLOCATED is an invalid transition.
        node = factory.make_node(
            status=NODE_STATUS.RETIRED, owner=factory.make_user())
        node.status = NODE_STATUS.ALLOCATED
        self.assertRaisesRegexp(
            NodeStateViolation,
            "Invalid transition: Retired -> Allocated.",
            node.full_clean)

    def test_full_clean_passes_if_status_unchanged(self):
        status = factory.getRandomChoice(NODE_STATUS_CHOICES)
        node = factory.make_node(status=status)
        node.status = status
        node.full_clean()
        # The test is that this does not raise an error.
        pass

    def test_full_clean_passes_if_status_valid_transition(self):
        # NODE_STATUS.READY -> NODE_STATUS.ALLOCATED is a valid
        # transition.
        status = NODE_STATUS.READY
        node = factory.make_node(status=status)
        node.status = NODE_STATUS.ALLOCATED
        node.full_clean()
        # The test is that this does not raise an error.
        pass

    def test_save_raises_node_state_violation_on_bad_transition(self):
        # RETIRED -> ALLOCATED is an invalid transition.
        node = factory.make_node(
            status=NODE_STATUS.RETIRED, owner=factory.make_user())
        node.status = NODE_STATUS.ALLOCATED
        self.assertRaisesRegexp(
            NodeStateViolation,
            "Invalid transition: Retired -> Allocated.",
            node.save)

    def test_netboot_defaults_to_True(self):
        node = Node()
        self.assertTrue(node.netboot)

    def test_nodegroup_cannot_be_null(self):
        node = factory.make_node()
        node.nodegroup = None
        self.assertRaises(ValidationError, node.save)

    def test_fqdn_returns_hostname_if_dns_not_managed(self):
        nodegroup = factory.make_node_group(
            name=factory.getRandomString(),
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        hostname_with_domain = '%s.%s' % (
            factory.getRandomString(), factory.getRandomString())
        node = factory.make_node(
            nodegroup=nodegroup, hostname=hostname_with_domain)
        self.assertEqual(hostname_with_domain, node.fqdn)

    def test_fqdn_replaces_hostname_if_dns_is_managed(self):
        hostname_without_domain = factory.make_name('hostname')
        hostname_with_domain = '%s.%s' % (
            hostname_without_domain, factory.getRandomString())
        domain = factory.make_name('domain')
        nodegroup = factory.make_node_group(
            status=NODEGROUP_STATUS.ACCEPTED,
            name=domain,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        node = factory.make_node(
            hostname=hostname_with_domain, nodegroup=nodegroup)
        expected_hostname = '%s.%s' % (hostname_without_domain, domain)
        self.assertEqual(expected_hostname, node.fqdn)

    def test_should_use_traditional_installer_by_default(self):
        node = factory.make_node()
        self.assertTrue(node.should_use_traditional_installer())

    def test_should_not_use_fastpath_installer_by_default(self):
        node = factory.make_node()
        self.assertFalse(node.should_use_fastpath_installer())

    def test_should_use_traditional_installer_not_when_tag_applies(self):
        node = factory.make_node()
        tag = factory.make_tag(name="use-fastpath-installer")
        tag.save()
        node.tags.add(tag)
        self.assertFalse(node.should_use_traditional_installer())

    def test_should_use_fastpath_installer_when_tag_applies(self):
        node = factory.make_node()
        tag = factory.make_tag(name="use-fastpath-installer")
        tag.save()
        node.tags.add(tag)
        self.assertTrue(node.should_use_fastpath_installer())

    def test_use_xxx_installer(self):
        # use_fastpath_installer() and use_traditional_installer() can be used
        # to affect what the should_use_xxx_installer() methods return.
        node = factory.make_node()
        node.use_traditional_installer()
        self.assertFalse(node.should_use_fastpath_installer())
        self.assertTrue(node.should_use_traditional_installer())
        node.use_fastpath_installer()
        self.assertTrue(node.should_use_fastpath_installer())
        self.assertFalse(node.should_use_traditional_installer())

    def test_use_traditional_installer_dissociates_tag_from_node(self):
        # use_traditional_installer removes any association with the
        # use-fastpath-installer tag. The tag is created even if it did not
        # previously exist. If it does already exist, it is not deleted.
        find_tag = lambda: list(
            Tag.objects.filter(name="use-fastpath-installer"))
        node = factory.make_node()
        node.use_traditional_installer()
        self.assertNotEqual([], find_tag())
        node.use_fastpath_installer()
        node.use_traditional_installer()
        self.assertNotEqual([], find_tag())

    def test_use_fastpath_installer_associates_tag_with_node(self):
        # use_traditional_installer() creates the use-traditional-installer
        # tag when it is first needed, and associates it with the node.
        find_tag = lambda: list(
            Tag.objects.filter(name="use-fastpath-installer"))
        self.assertEqual([], find_tag())
        node = factory.make_node()
        node.use_fastpath_installer()
        self.assertNotEqual([], find_tag())

    def test_use_traditional_installer_complains_when_tag_has_expression(self):
        # use_traditional_installer() complains when the use-fastpath-installer
        # tag exists and is defined with an expression.
        node = factory.make_node()
        factory.make_tag(
            name="use-fastpath-installer",
            definition="//something")
        error = self.assertRaises(
            RuntimeError, node.use_traditional_installer)
        self.assertIn(
            "The use-fastpath-installer tag is defined with an expression",
            unicode(error))

    def test_use_fastpath_installer_complains_when_tag_has_expression(self):
        # use_fastpath_installer() complains when the
        # use-fastpath-installer tag exists and is defined with an
        # expression.
        node = factory.make_node()
        factory.make_tag(
            name="use-fastpath-installer",
            definition="//something")
        error = self.assertRaises(
            RuntimeError, node.use_fastpath_installer)
        self.assertIn(
            "The use-fastpath-installer tag is defined with an expression",
            unicode(error))

    def test_split_arch_returns_arch_as_tuple(self):
        main_arch = factory.make_name('arch')
        sub_arch = factory.make_name('subarch')
        full_arch = '%s/%s' % (main_arch, sub_arch)
        node = factory.make_node(architecture=full_arch)
        self.assertEqual((main_arch, sub_arch), node.split_arch())

    def test_mac_addresses_on_managed_interfaces_returns_only_managed(self):
        node = factory.make_node_with_mac_attached_to_nodegroupinterface(
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)

        mac_with_no_interface = factory.make_mac_address(node=node)
        unmanaged_interface = factory.make_node_group_interface(
            nodegroup=node.nodegroup,
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        mac_with_unmanaged_interface = factory.make_mac_address(
            node=node, cluster_interface=unmanaged_interface)
        ignore_unused(mac_with_no_interface, mac_with_unmanaged_interface)

        observed = node.mac_addresses_on_managed_interfaces()
        self.assertItemsEqual([node.get_primary_mac()], observed)

    def test_mac_addresses_on_managed_interfaces_returns_empty_if_none(self):
        node = factory.make_node(mac=True)
        observed = node.mac_addresses_on_managed_interfaces()
        self.assertItemsEqual([], observed)


class NodeRoutersTest(MAASServerTestCase):

    def test_routers_stores_mac_address(self):
        node = factory.make_node()
        macs = [MAC('aa:bb:cc:dd:ee:ff')]
        node.routers = macs
        node.save()
        self.assertEqual(macs, reload_object(node).routers)

    def test_routers_stores_multiple_mac_addresses(self):
        node = factory.make_node()
        macs = [MAC('aa:bb:cc:dd:ee:ff'), MAC('00:11:22:33:44:55')]
        node.routers = macs
        node.save()
        self.assertEqual(macs, reload_object(node).routers)

    def test_routers_can_append(self):
        node = factory.make_node()
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
        return factory.make_node(status=status, owner=user, **kwargs)

    def make_node_with_mac(self, user=None, **kwargs):
        node = self.make_node(user, **kwargs)
        mac = factory.make_mac_address(node=node)
        return node, mac

    def make_user_data(self):
        """Create a blob of arbitrary user-data."""
        return factory.getRandomString().encode('ascii')

    def test_filter_by_ids_filters_nodes_by_ids(self):
        nodes = [factory.make_node() for counter in range(5)]
        ids = [node.system_id for node in nodes]
        selection = slice(1, 3)
        self.assertItemsEqual(
            nodes[selection],
            Node.objects.filter_by_ids(Node.objects.all(), ids[selection]))

    def test_filter_by_ids_with_empty_list_returns_empty(self):
        factory.make_node()
        self.assertItemsEqual(
            [], Node.objects.filter_by_ids(Node.objects.all(), []))

    def test_filter_by_ids_without_ids_returns_full(self):
        node = factory.make_node()
        self.assertItemsEqual(
            [node], Node.objects.filter_by_ids(Node.objects.all(), None))

    def test_get_nodes_for_user_lists_visible_nodes(self):
        """get_nodes with perm=NODE_PERMISSION.VIEW lists the nodes a user
        has access to.

        When run for a regular user it returns unowned nodes, and nodes
        owned by that user.
        """
        user = factory.make_user()
        visible_nodes = [self.make_node(owner) for owner in [None, user]]
        self.make_node(factory.make_user())
        self.assertItemsEqual(
            visible_nodes, Node.objects.get_nodes(user, NODE_PERMISSION.VIEW))

    def test_get_nodes_admin_lists_all_nodes(self):
        admin = factory.make_admin()
        owners = [
            None,
            factory.make_user(),
            factory.make_admin(),
            admin,
            ]
        nodes = [self.make_node(owner) for owner in owners]
        self.assertItemsEqual(
            nodes, Node.objects.get_nodes(admin, NODE_PERMISSION.VIEW))

    def test_get_nodes_filters_by_id(self):
        user = factory.make_user()
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
        wanted_node = factory.make_node()
        # Node that we'll exclude from from_nodes:
        factory.make_node()

        self.assertItemsEqual(
            [wanted_node],
            Node.objects.get_nodes(
                admin, NODE_PERMISSION.VIEW,
                from_nodes=Node.objects.filter(id=wanted_node.id)))

    def test_get_nodes_combines_from_nodes_with_other_filter(self):
        user = factory.make_user()
        # Node that we want to see in the result:
        matching_node = factory.make_node(owner=user)
        # Node that we'll exclude from from_nodes:
        factory.make_node(owner=user)
        # Node that will be ignored on account of belonging to someone else:
        invisible_node = factory.make_node(owner=factory.make_user())

        self.assertItemsEqual(
            [matching_node],
            Node.objects.get_nodes(
                user, NODE_PERMISSION.VIEW,
                from_nodes=Node.objects.filter(id__in=(
                    matching_node.id,
                    invisible_node.id,
                    ))))

    def test_get_nodes_with_edit_perm_for_user_lists_owned_nodes(self):
        user = factory.make_user()
        visible_node = self.make_node(user)
        self.make_node(None)
        self.make_node(factory.make_user())
        self.assertItemsEqual(
            [visible_node],
            Node.objects.get_nodes(user, NODE_PERMISSION.EDIT))

    def test_get_nodes_with_edit_perm_admin_lists_all_nodes(self):
        admin = factory.make_admin()
        owners = [
            None,
            factory.make_user(),
            factory.make_admin(),
            admin,
            ]
        nodes = [self.make_node(owner) for owner in owners]
        self.assertItemsEqual(
            nodes, Node.objects.get_nodes(admin, NODE_PERMISSION.EDIT))

    def test_get_nodes_with_admin_perm_returns_empty_list_for_user(self):
        user = factory.make_user()
        [self.make_node(user) for counter in range(5)]
        self.assertItemsEqual(
            [],
            Node.objects.get_nodes(user, NODE_PERMISSION.ADMIN))

    def test_get_nodes_with_admin_perm_returns_all_nodes_for_admin(self):
        user = factory.make_user()
        nodes = [self.make_node(user) for counter in range(5)]
        self.assertItemsEqual(
            nodes,
            Node.objects.get_nodes(
                factory.make_admin(), NODE_PERMISSION.ADMIN))

    def test_get_visible_node_or_404_ok(self):
        """get_node_or_404 fetches nodes by system_id."""
        user = factory.make_user()
        node = self.make_node(user)
        self.assertEqual(
            node,
            Node.objects.get_node_or_404(
                node.system_id, user, NODE_PERMISSION.VIEW))

    def test_get_available_nodes_finds_available_nodes(self):
        user = factory.make_user()
        node1 = self.make_node(None)
        node2 = self.make_node(None)
        self.assertItemsEqual(
            [node1, node2],
            Node.objects.get_available_nodes_for_acquisition(user))

    def test_get_available_node_returns_empty_list_if_empty(self):
        user = factory.make_user()
        self.assertEqual(
            [], list(Node.objects.get_available_nodes_for_acquisition(user)))

    def test_get_available_nodes_ignores_taken_nodes(self):
        user = factory.make_user()
        available_status = NODE_STATUS.READY
        unavailable_statuses = (
            set(NODE_STATUS_CHOICES_DICT) - set([available_status]))
        for status in unavailable_statuses:
            factory.make_node(status=status)
        self.assertEqual(
            [], list(Node.objects.get_available_nodes_for_acquisition(user)))

    def test_get_available_node_ignores_invisible_nodes(self):
        user = factory.make_user()
        node = self.make_node()
        node.owner = factory.make_user()
        node.save()
        self.assertEqual(
            [], list(Node.objects.get_available_nodes_for_acquisition(user)))

    def test_stop_nodes_stops_nodes(self):
        # We don't actually want to fire off power events, but we'll go
        # through the motions right up to the point where we'd normally
        # run shell commands.
        self.patch(PowerAction, 'run_shell', lambda *args, **kwargs: ('', ''))
        user = factory.make_user()
        node, mac = self.make_node_with_mac(user, power_type='virsh')
        output = Node.objects.stop_nodes([node.system_id], user)

        self.assertItemsEqual([node], output)
        self.assertEqual(
            (1, 'provisioningserver.tasks.power_off'),
            (
                len(self.celery.tasks),
                self.celery.tasks[0]['task'].name,
            ))

    def test_stop_nodes_task_routed_to_nodegroup_worker(self):
        user = factory.make_user()
        node, mac = self.make_node_with_mac(user, power_type='virsh')
        task = self.patch(node_module, 'power_off')
        Node.objects.stop_nodes([node.system_id], user)
        args, kwargs = task.apply_async.call_args
        self.assertEqual(node.work_queue, kwargs['queue'])

    def test_stop_nodes_ignores_uneditable_nodes(self):
        nodes = [
            self.make_node_with_mac(
                factory.make_user(), power_type='ether_wake')
            for counter in range(3)]
        ids = [node.system_id for node, mac in nodes]
        stoppable_node = nodes[0][0]
        self.assertItemsEqual(
            [stoppable_node],
            Node.objects.stop_nodes(ids, stoppable_node.owner))

    def test_stop_nodes_does_not_attempt_power_task_if_no_power_type(self):
        # If the node has a power_type set to UNKNOWN_POWER_TYPE
        # NodeManager.stop_node(this_node) won't create a power event
        # for it.
        user = factory.make_user()
        node, unused = self.make_node_with_mac(
            user, power_type='')
        output = Node.objects.stop_nodes([node.system_id], user)

        self.assertItemsEqual([], output)
        self.assertEqual(0, len(self.celery.tasks))

    def test_start_nodes_starts_nodes(self):
        user = factory.make_user()
        node, mac = self.make_node_with_mac(
            user, power_type='ether_wake')
        output = Node.objects.start_nodes([node.system_id], user)

        self.assertItemsEqual([node], output)
        self.assertEqual(
            (1, 'provisioningserver.tasks.power_on', mac.mac_address),
            (
                len(self.celery.tasks),
                self.celery.tasks[0]['task'].name,
                self.celery.tasks[0]['kwargs']['mac_address'],
            ))

    def test_start_nodes_issues_dhcp_host_task(self):
        user = factory.make_user()
        node = factory.make_node_with_mac_attached_to_nodegroupinterface(
            owner=user, power_type='ether_wake')
        omshell_create = self.patch(Omshell, 'create')
        output = Node.objects.start_nodes([node.system_id], user)

        # Check that the single node was started, and that the tasks
        # issued are all there and in the right order.
        self.assertItemsEqual([node], output)
        self.assertEqual(
            [
                'provisioningserver.tasks.add_new_dhcp_host_map',
                'provisioningserver.tasks.power_on',
            ],
            [
                task['task'].name for task in self.celery.tasks
            ])

        # Also check that Omshell.create() was called with the right
        # parameters.
        mac = node.get_primary_mac()
        [ip] = mac.ip_addresses.all()
        expected_ip = ip.ip
        expected_mac = mac.mac_address
        args, kwargs = omshell_create.call_args
        self.assertEqual((expected_ip, expected_mac), args)

    def test_start_nodes_clears_existing_dynamic_maps(self):
        user = factory.make_user()
        node = factory.make_node_with_mac_attached_to_nodegroupinterface(
            owner=user, power_type='ether_wake')
        factory.make_dhcp_lease(
            nodegroup=node.nodegroup, mac=node.get_primary_mac().mac_address)
        self.patch(Omshell, 'create')
        self.patch(Omshell, 'remove')
        output = Node.objects.start_nodes([node.system_id], user)

        # Check that the single node was started, and that the tasks
        # issued are all there and in the right order.
        self.assertItemsEqual([node], output)
        self.assertEqual(
            [
                'provisioningserver.tasks.remove_dhcp_host_map',
                'provisioningserver.tasks.add_new_dhcp_host_map',
                'provisioningserver.tasks.power_on',
            ],
            [
                task['task'].name for task in self.celery.tasks
            ])

    def test_start_nodes_task_routed_to_nodegroup_worker(self):
        # Startup jobs are chained, so the normal way of inspecting a
        # task directly for routing options doesn't work here, because
        # in EAGER mode that we use in the test suite, the options are
        # not passed all the way down to the tasks.  Instead, we patch
        # some celery code to inspect the options that were passed.
        user = factory.make_user()
        node, mac = self.make_node_with_mac(
            user, power_type='ether_wake')
        option_call = self.patch(celery.canvas.Signature, 'set')
        Node.objects.start_nodes([node.system_id], user)
        args, kwargs = option_call.call_args
        self.assertEqual(node.work_queue, kwargs['queue'])

    def test_start_nodes_does_not_attempt_power_task_if_no_power_type(self):
        # If the node has a power_type set to DEFAULT_POWER_TYPE
        # NodeManager.start_node(this_node) should use the default
        # power_type.
        user = factory.make_user()
        node, unused = self.make_node_with_mac(
            user, power_type='')
        output = Node.objects.start_nodes([node.system_id], user)

        self.assertItemsEqual([], output)
        self.assertEqual(0, len(self.celery.tasks))

    def test_start_nodes_wakeonlan_prefers_power_parameters(self):
        # If power_parameters is set we should prefer it to sifting
        # through related MAC addresses.
        user = factory.make_user()
        preferred_mac = factory.getRandomMACAddress()
        node, mac = self.make_node_with_mac(
            user, power_type='ether_wake',
            power_parameters=dict(mac_address=preferred_mac))
        output = Node.objects.start_nodes([node.system_id], user)

        self.assertItemsEqual([node], output)
        self.assertEqual(
            (1, 'provisioningserver.tasks.power_on', preferred_mac),
            (
                len(self.celery.tasks),
                self.celery.tasks[0]['task'].name,
                self.celery.tasks[0]['kwargs']['mac_address'],
            ))

    def test_start_nodes_wakeonlan_falls_back_to_primary_mac(self):
        # If node.power_params is set but doesn't have "mac_address" in it,
        # then use the node's primary MAC.
        user = factory.make_user()
        node, mac = self.make_node_with_mac(
            user, power_type='ether_wake',
            power_parameters=dict(jarjar="binks"))
        output = Node.objects.start_nodes([node.system_id], user)
        self.assertItemsEqual([node], output)
        self.assertEqual(
            node.get_primary_mac().mac_address.get_raw(),
            self.celery.tasks[0]['kwargs']['mac_address'])
        self.assertIsInstance(
            self.celery.tasks[0]['kwargs']['mac_address'],
            unicode)

    def test_start_nodes_wakeonlan_ignores_empty_mac_address_parameter(self):
        user = factory.make_user()
        node, mac = self.make_node_with_mac(
            user, power_type='ether_wake',
            power_parameters=dict(mac_address=""))
        output = Node.objects.start_nodes([node.system_id], user)
        self.assertItemsEqual([], output)
        self.assertEqual([], self.celery.tasks)

    def test_start_nodes_ignores_nodes_without_mac(self):
        user = factory.make_user()
        node = self.make_node(user)
        output = Node.objects.start_nodes([node.system_id], user)

        self.assertItemsEqual([], output)

    def test_start_nodes_ignores_uneditable_nodes(self):
        nodes = [
            self.make_node_with_mac(
                factory.make_user(), power_type='ether_wake')[0]
            for counter in range(3)
        ]
        ids = [node.system_id for node in nodes]
        startable_node = nodes[0]
        self.assertItemsEqual(
            [startable_node],
            Node.objects.start_nodes(ids, startable_node.owner))

    def test_start_nodes_stores_user_data(self):
        node = factory.make_node(owner=factory.make_user())
        user_data = self.make_user_data()
        Node.objects.start_nodes(
            [node.system_id], node.owner, user_data=user_data)
        self.assertEqual(user_data, NodeUserData.objects.get_user_data(node))

    def test_start_nodes_does_not_store_user_data_for_uneditable_nodes(self):
        node = factory.make_node(owner=factory.make_user())
        original_user_data = self.make_user_data()
        NodeUserData.objects.set_user_data(node, original_user_data)
        Node.objects.start_nodes(
            [node.system_id], factory.make_user(),
            user_data=self.make_user_data())
        self.assertEqual(
            original_user_data, NodeUserData.objects.get_user_data(node))

    def test_start_nodes_without_user_data_clears_existing_data(self):
        node = factory.make_node(owner=factory.make_user())
        user_data = self.make_user_data()
        NodeUserData.objects.set_user_data(node, user_data)
        Node.objects.start_nodes([node.system_id], node.owner, user_data=None)
        self.assertRaises(
            NodeUserData.DoesNotExist,
            NodeUserData.objects.get_user_data, node)

    def test_start_nodes_with_user_data_overwrites_existing_data(self):
        node = factory.make_node(owner=factory.make_user())
        NodeUserData.objects.set_user_data(node, self.make_user_data())
        user_data = self.make_user_data()
        Node.objects.start_nodes(
            [node.system_id], node.owner, user_data=user_data)
        self.assertEqual(user_data, NodeUserData.objects.get_user_data(node))

    def test_netboot_on(self):
        node = factory.make_node(netboot=False)
        node.set_netboot(True)
        self.assertTrue(node.netboot)

    def test_netboot_off(self):
        node = factory.make_node(netboot=True)
        node.set_netboot(False)
        self.assertFalse(node.netboot)


class NodeStaticIPClaimingTest(MAASServerTestCase):

    def test_claim_static_ips_ignores_unmanaged_macs(self):
        node = factory.make_node()
        factory.make_mac_address(node=node)
        observed = node.claim_static_ips()
        self.assertItemsEqual([], observed)

    def test_claim_static_ips_creates_task_for_each_managed_mac(self):
        nodegroup = factory.make_node_group()
        node = factory.make_node(nodegroup=nodegroup)

        # Add some MACs attached to managed interfaces.
        number_of_macs = 2
        for _ in range(0, number_of_macs):
            low_ip, high_ip = factory.make_ip_range()
            ngi = factory.make_node_group_interface(
                nodegroup, static_ip_range_low=low_ip.ipv4().format(),
                static_ip_range_high=high_ip.ipv4().format(),
                management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
            factory.make_mac_address(node=node, cluster_interface=ngi)

        observed = node.claim_static_ips()
        expected = [
            'provisioningserver.tasks.add_new_dhcp_host_map'] * number_of_macs

        self.assertEqual(
            expected,
            [task.task for task in observed]
            )

    def test_claim_static_ips_creates_deletion_task(self):
        # If dhcp leases exist before creating a static IP, the code
        # should attempt to remove their host maps.
        node = factory.make_node_with_mac_attached_to_nodegroupinterface()
        factory.make_dhcp_lease(
            nodegroup=node.nodegroup, mac=node.get_primary_mac().mac_address)

        observed = node.claim_static_ips()

        self.assertEqual(
            [
                'celery.chain',
                'provisioningserver.tasks.add_new_dhcp_host_map',
            ],
            [
                task.task for task in observed
            ])

        # Probe the chain to make sure it has the deletion task.
        self.assertEqual(
            'provisioningserver.tasks.remove_dhcp_host_map',
            observed[0].tasks[0].task,
            )

    def test_claim_static_ips_ignores_interface_with_no_static_range(self):
        node = factory.make_node_with_mac_attached_to_nodegroupinterface()
        ngi = node.get_primary_mac().cluster_interface
        ngi.static_ip_range_low = None
        ngi.static_ip_range_high = None
        ngi.save()

        observed = node.claim_static_ips()
        self.assertItemsEqual([], observed)

    def test_claim_static_ips_deallocates_if_cant_complete_all_macs(self):
        node = factory.make_node_with_mac_attached_to_nodegroupinterface()
        self.patch(
            MACAddress,
            'claim_static_ip').side_effect = StaticIPAddressExhaustion
        deallocate_call = self.patch(
            StaticIPAddressManager, 'deallocate_by_node')
        self.assertRaises(StaticIPAddressExhaustion, node.claim_static_ips)
        self.assertThat(deallocate_call, MockCalledOnceWith(node))

    def test_claim_static_ips_does_not_deallocate_if_completes_all_macs(self):
        node = factory.make_node_with_mac_attached_to_nodegroupinterface()
        deallocate_call = self.patch(
            StaticIPAddressManager, 'deallocate_by_node')
        node.claim_static_ips()

        self.assertThat(deallocate_call, MockNotCalled())
