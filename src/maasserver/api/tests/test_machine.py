# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the Machine API."""

__all__ = []

from base64 import b64encode
import http.client

from django.conf import settings
from django.core.urlresolvers import reverse
from django.db import transaction
from maasserver import forms
from maasserver.api import machines as machines_module
from maasserver.enum import (
    FILESYSTEM_FORMAT_TYPE_CHOICES,
    FILESYSTEM_TYPE,
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_STATUS,
    NODE_STATUS_CHOICES,
    NODE_STATUS_CHOICES_DICT,
    NODE_TYPE,
    NODE_TYPE_CHOICES,
    POWER_STATE,
)
from maasserver.models import (
    Config,
    Domain,
    Filesystem,
    Machine,
    Node,
    node as node_module,
    StaticIPAddress,
)
from maasserver.models.node import RELEASABLE_STATUSES
from maasserver.storage_layouts import (
    MIN_BOOT_PARTITION_SIZE,
    StorageLayoutError,
)
from maasserver.testing.api import (
    APITestCase,
    APITransactionTestCase,
)
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.factory import factory
from maasserver.testing.oauthclient import OAuthAuthenticatedClient
from maasserver.testing.orm import reload_objects
from maasserver.testing.osystems import make_usable_osystem
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.converters import json_load_bytes
from maasserver.utils.orm import (
    post_commit,
    reload_object,
)
from maastesting.matchers import (
    Equals,
    HasLength,
    MockCalledOnceWith,
    MockNotCalled,
)
from metadataserver.models import (
    NodeKey,
    NodeUserData,
)
from metadataserver.nodeinituser import get_node_init_user
from mock import ANY
from netaddr import IPNetwork
from provisioningserver.rpc.exceptions import PowerActionAlreadyInProgress
from provisioningserver.utils.enum import map_enum
from testtools.matchers import (
    ContainsDict,
    MatchesListwise,
    MatchesStructure,
    StartsWith,
)
from twisted.internet import defer
import yaml


class MachineAnonAPITest(MAASServerTestCase):

    def test_machine_init_user_cannot_access(self):
        token = NodeKey.objects.get_token_for_node(factory.make_Node())
        client = OAuthAuthenticatedClient(get_node_init_user(), token)
        response = client.get(reverse('machines_handler'))
        self.assertEqual(http.client.FORBIDDEN, response.status_code)


class MachinesAPILoggedInTest(MAASServerTestCase):

    def setUp(self):
        super(MachinesAPILoggedInTest, self).setUp()
        self.patch(node_module, 'wait_for_power_command')

    def test_machines_GET_logged_in(self):
        # A (Django) logged-in user can access the API.
        self.client_log_in()
        machine = factory.make_Node()
        response = self.client.get(reverse('machines_handler'))
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            [machine.system_id],
            [parsed_machine.get('system_id')
             for parsed_machine in parsed_result])


class TestMachineAPI(APITestCase):
    """Tests for /api/2.0/machines/<machine>/."""

    def setUp(self):
        super(TestMachineAPI, self).setUp()
        self.patch(node_module.Node, '_pc_power_control_node')

    def test_handler_path(self):
        self.assertEqual(
            '/api/2.0/machines/machine-name/',
            reverse('machine_handler', args=['machine-name']))

    @staticmethod
    def get_machine_uri(machine):
        """Get the API URI for `machine`."""
        return reverse('machine_handler', args=[machine.system_id])

    def test_GET_returns_machine(self):
        # The api allows for fetching a single Machine (using system_id).
        machine = factory.make_Node()
        response = self.client.get(self.get_machine_uri(machine))

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        domain_name = Domain.objects.get_default_domain().name
        self.assertEqual(
            "%s.%s" % (machine.hostname, domain_name),
            parsed_result['fqdn'])
        self.assertEqual(machine.system_id, parsed_result['system_id'])

    def test_GET_returns_boot_interface_object(self):
        # The api allows for fetching a single Machine (using system_id).
        machine = factory.make_Node(interface=True)
        boot_interface = machine.get_boot_interface()
        response = self.client.get(self.get_machine_uri(machine))

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(
            boot_interface.id, parsed_result['boot_interface']['id'])
        self.assertEqual(
            str(boot_interface.mac_address),
            parsed_result['boot_interface']['mac_address'])

    def test_GET_returns_associated_tag(self):
        machine = factory.make_Node()
        tag = factory.make_Tag()
        machine.tags.add(tag)
        response = self.client.get(self.get_machine_uri(machine))

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual([tag.name], parsed_result['tag_names'])

    def test_GET_returns_associated_ip_addresses(self):
        machine = factory.make_Node(disable_ipv4=False)
        nic = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=machine)
        subnet = factory.make_Subnet()
        ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        lease = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip=ip,
            interface=nic, subnet=subnet)
        response = self.client.get(self.get_machine_uri(machine))

        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual([lease.ip], parsed_result['ip_addresses'])

    def test_GET_returns_interface_set(self):
        machine = factory.make_Node()
        response = self.client.get(self.get_machine_uri(machine))
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertIn('interface_set', parsed_result)

    def test_GET_returns_zone(self):
        machine = factory.make_Node()
        response = self.client.get(self.get_machine_uri(machine))
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(
            [machine.zone.name, machine.zone.description],
            [
                parsed_result['zone']['name'],
                parsed_result['zone']['description']])

    def test_GET_returns_boot_interface(self):
        machine = factory.make_Node(interface=True)
        machine.boot_interface = machine.interface_set.first()
        machine.save()
        response = self.client.get(self.get_machine_uri(machine))
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(
            machine.boot_interface.mac_address.get_raw(),
            parsed_result['boot_interface']['mac_address'])

    def test_GET_refuses_to_access_nonexistent_machine(self):
        # When fetching a Machine, the api returns a 'Not Found' (404) error
        # if no machine is found.
        url = reverse('machine_handler', args=['invalid-uuid'])

        response = self.client.get(url)

        self.assertEqual(http.client.NOT_FOUND, response.status_code)
        self.assertEqual(
            "Not Found", response.content.decode(settings.DEFAULT_CHARSET))

    def test_GET_returns_404_if_machine_name_contains_invld_characters(self):
        # When the requested name contains characters that are invalid for
        # a hostname, the result of the request is a 404 response.
        url = reverse('machine_handler', args=['invalid-uuid-#...'])

        response = self.client.get(url)

        self.assertEqual(http.client.NOT_FOUND, response.status_code)
        self.assertEqual(
            "Not Found", response.content.decode(settings.DEFAULT_CHARSET))

    def test_GET_returns_owner_name_when_allocated_to_self(self):
        machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.logged_in_user)
        response = self.client.get(self.get_machine_uri(machine))
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(machine.owner.username, parsed_result["owner"])

    def test_GET_returns_owner_name_when_allocated_to_other_user(self):
        machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())
        response = self.client.get(self.get_machine_uri(machine))
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(machine.owner.username, parsed_result["owner"])

    def test_GET_returns_empty_owner_when_not_allocated(self):
        machine = factory.make_Node(status=NODE_STATUS.READY)
        response = self.client.get(self.get_machine_uri(machine))
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(None, parsed_result["owner"])

    def test_GET_returns_physical_block_devices(self):
        machine = factory.make_Node(with_boot_disk=False)
        devices = [
            factory.make_PhysicalBlockDevice(node=machine)
            for _ in range(3)
        ]
        response = self.client.get(self.get_machine_uri(machine))
        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        parsed_devices = [
            device['name']
            for device in parsed_result['physicalblockdevice_set']
        ]
        self.assertItemsEqual(
            [device.name for device in devices], parsed_devices)

    def test_GET_rejects_other_node_types(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=self.logged_in_user,
            node_type=factory.pick_choice(
                NODE_TYPE_CHOICES, but_not=[NODE_TYPE.MACHINE]),
            )
        response = self.client.get(self.get_machine_uri(node))
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content)

    def test_GET_returns_min_hwe_kernel_and_hwe_kernel(self):
        machine = factory.make_Node()
        response = self.client.get(self.get_machine_uri(machine))

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(None, parsed_result['min_hwe_kernel'])
        self.assertEqual(None, parsed_result['hwe_kernel'])

    def test_GET_returns_min_hwe_kernel(self):
        machine = factory.make_Node(min_hwe_kernel="hwe-v")
        response = self.client.get(self.get_machine_uri(machine))

        self.assertEqual(http.client.OK, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertEqual("hwe-v", parsed_result['min_hwe_kernel'])

    def test_GET_returns_status_message_with_most_recent_event(self):
        """Makes sure the most recent event from this machine is shown in the
        status_message attribute."""
        # The first event won't be returned.
        event = factory.make_Event(description="Uninteresting event")
        machine = event.node
        # The second (and last) event will be returned.
        message = "Interesting event"
        factory.make_Event(description=message, node=machine)
        response = self.client.get(self.get_machine_uri(machine))
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(message, parsed_result['status_message'])

    def test_GET_returns_status_name(self):
        """GET should display the machine status as a user-friendly string."""
        for status in NODE_STATUS_CHOICES_DICT:
            machine = factory.make_Node(status=status)
            response = self.client.get(self.get_machine_uri(machine))
            parsed_result = json_load_bytes(response.content)
            self.assertEqual(NODE_STATUS_CHOICES_DICT[status],
                             parsed_result['status_name'])

    def test_POST_power_off_checks_permission(self):
        machine = factory.make_Node()
        machine_stop = self.patch(machine, 'stop')
        response = self.client.post(
            self.get_machine_uri(machine), {'op': 'power_off'})
        self.assertEqual(http.client.FORBIDDEN, response.status_code)
        self.assertThat(machine_stop, MockNotCalled())

    def test_POST_power_off_rejects_other_node_types(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=self.logged_in_user,
            node_type=factory.pick_choice(
                NODE_TYPE_CHOICES, but_not=[NODE_TYPE.MACHINE]),
            )
        response = self.client.post(
            self.get_machine_uri(node), {'op': 'power_off'})
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content)

    def test_POST_power_off_returns_nothing_if_machine_was_not_stopped(self):
        # The machine may not be stopped because, for example, its power type
        # does not support it. In this case the machine is not returned to the
        # caller.
        machine = factory.make_Node(owner=self.logged_in_user)
        machine_stop = self.patch(node_module.Machine, 'stop')
        machine_stop.return_value = False
        response = self.client.post(
            self.get_machine_uri(machine), {'op': 'power_off'})
        self.assertEqual(http.client.OK, response.status_code)
        self.assertIsNone(json_load_bytes(response.content))
        self.assertThat(machine_stop, MockCalledOnceWith(
            ANY, stop_mode=ANY, comment=None))

    def test_POST_power_off_returns_machine(self):
        machine = factory.make_Node(owner=self.logged_in_user)
        self.patch(node_module.Machine, 'stop').return_value = True
        response = self.client.post(
            self.get_machine_uri(machine), {'op': 'power_off'})
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            machine.system_id, json_load_bytes(response.content)['system_id'])

    def test_POST_power_off_may_be_repeated(self):
        machine = factory.make_Node(
            owner=self.logged_in_user, interface=True,
            power_type='manual')
        self.patch(machine, 'stop')
        self.client.post(self.get_machine_uri(machine), {'op': 'power_off'})
        response = self.client.post(
            self.get_machine_uri(machine), {'op': 'power_off'})
        self.assertEqual(http.client.OK, response.status_code)

    def test_POST_power_off_power_offs_machines(self):
        machine = factory.make_Node(owner=self.logged_in_user)
        machine_stop = self.patch(node_module.Machine, 'stop')
        stop_mode = factory.make_name('stop_mode')
        comment = factory.make_name('comment')
        self.client.post(
            self.get_machine_uri(machine),
            {'op': 'power_off', 'stop_mode': stop_mode, 'comment': comment})
        self.assertThat(
            machine_stop,
            MockCalledOnceWith(
                self.logged_in_user, stop_mode=stop_mode, comment=comment))

    def test_POST_power_off_handles_missing_comment(self):
        machine = factory.make_Node(owner=self.logged_in_user)
        machine_stop = self.patch(node_module.Machine, 'stop')
        stop_mode = factory.make_name('stop_mode')
        self.client.post(
            self.get_machine_uri(machine),
            {'op': 'power_off', 'stop_mode': stop_mode})
        self.assertThat(
            machine_stop,
            MockCalledOnceWith(
                self.logged_in_user, stop_mode=stop_mode, comment=None))

    def test_POST_power_off_returns_503_when_power_already_in_progress(self):
        machine = factory.make_Node(owner=self.logged_in_user)
        exc_text = factory.make_name("exc_text")
        self.patch(
            node_module.Machine,
            'stop').side_effect = PowerActionAlreadyInProgress(exc_text)
        response = self.client.post(
            self.get_machine_uri(machine), {'op': 'power_off'})
        self.assertResponseCode(http.client.SERVICE_UNAVAILABLE, response)
        self.assertIn(
            exc_text, response.content.decode(settings.DEFAULT_CHARSET))

    def test_POST_power_on_checks_permission(self):
        machine = factory.make_Node_with_Interface_on_Subnet(
            owner=factory.make_User())
        response = self.client.post(
            self.get_machine_uri(machine), {'op': 'power_on'})
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_POST_power_on_checks_ownership(self):
        self.become_admin()
        machine = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY)
        response = self.client.post(
            self.get_machine_uri(machine), {'op': 'power_on'})
        self.assertEqual(http.client.CONFLICT, response.status_code)
        self.assertEqual(
            "Can't start machine: it hasn't been allocated.",
            response.content.decode(settings.DEFAULT_CHARSET))

    def test_POST_power_on_returns_machine(self):
        self.patch(node_module.Node, "_start")
        machine = factory.make_Node(
            owner=self.logged_in_user, interface=True,
            power_type='manual',
            architecture=make_usable_architecture(self))
        osystem = make_usable_osystem(self)
        distro_series = osystem['default_release']
        response = self.client.post(
            self.get_machine_uri(machine),
            {
                'op': 'power_on',
                'distro_series': distro_series,
            })
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            machine.system_id, json_load_bytes(response.content)['system_id'])

    def test_POST_power_on_rejects_other_node_types(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=self.logged_in_user,
            node_type=factory.pick_choice(
                NODE_TYPE_CHOICES, but_not=[NODE_TYPE.MACHINE]),
            )
        response = self.client.post(
            self.get_machine_uri(node), {'op': 'power_on'})
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content)

    def test_POST_deploy_sets_osystem_and_distro_series(self):
        self.patch(node_module.Node, "_start")
        machine = factory.make_Node(
            owner=self.logged_in_user, interface=True,
            power_type='manual',
            architecture=make_usable_architecture(self))
        osystem = make_usable_osystem(self)
        distro_series = osystem['default_release']
        response = self.client.post(
            self.get_machine_uri(machine), {
                'op': 'deploy',
                'distro_series': distro_series
            })
        self.assertEqual(
            (http.client.OK, machine.system_id),
            (response.status_code,
             json_load_bytes(response.content)['system_id']))
        self.assertEqual(
            osystem['name'], reload_object(machine).osystem)
        self.assertEqual(
            distro_series, reload_object(machine).distro_series)

    def test_POST_deploy_validates_distro_series(self):
        machine = factory.make_Node_with_Interface_on_Subnet(
            owner=self.logged_in_user, interface=True,
            power_type='manual',
            architecture=make_usable_architecture(self))
        invalid_distro_series = factory.make_string()
        response = self.client.post(
            self.get_machine_uri(machine),
            {'op': 'deploy', 'distro_series': invalid_distro_series})
        self.assertEqual(
            (
                http.client.BAD_REQUEST,
                {'distro_series': [
                    "'%s' is not a valid distro_series.  "
                    "It should be one of: ''." %
                    invalid_distro_series]}
            ),
            (response.status_code, json_load_bytes(response.content)))

    def test_POST_deploy_sets_license_key(self):
        self.patch(node_module.Node, "_start")
        machine = factory.make_Node(
            owner=self.logged_in_user, interface=True,
            power_type='manual',
            architecture=make_usable_architecture(self))
        osystem = make_usable_osystem(self)
        distro_series = osystem['default_release']
        license_key = factory.make_string()
        self.patch(forms, 'validate_license_key').return_value = True
        response = self.client.post(
            self.get_machine_uri(machine), {
                'op': 'deploy',
                'osystem': osystem['name'],
                'distro_series': distro_series,
                'license_key': license_key,
            })
        self.assertEqual(
            (http.client.OK, machine.system_id),
            (response.status_code,
             json_load_bytes(response.content)['system_id']))
        self.assertEqual(
            license_key, reload_object(machine).license_key)

    def test_POST_deploy_validates_license_key(self):
        machine = factory.make_Node_with_Interface_on_Subnet(
            owner=self.logged_in_user, interface=True,
            power_type='manual',
            architecture=make_usable_architecture(self))
        osystem = make_usable_osystem(self)
        distro_series = osystem['default_release']
        license_key = factory.make_string()
        self.patch(forms, 'validate_license_key').return_value = False
        response = self.client.post(
            self.get_machine_uri(machine), {
                'op': 'deploy',
                'osystem': osystem['name'],
                'distro_series': distro_series,
                'license_key': license_key,
            })
        self.assertEqual(
            (
                http.client.BAD_REQUEST,
                {'license_key': [
                    "Invalid license key."]}
            ),
            (response.status_code, json_load_bytes(response.content)))

    def test_POST_deploy_sets_default_distro_series(self):
        self.patch(node_module.Node, "_start")
        machine = factory.make_Node(
            owner=self.logged_in_user, interface=True,
            power_type='manual',
            architecture=make_usable_architecture(self))
        osystem = Config.objects.get_config('default_osystem')
        distro_series = Config.objects.get_config('default_distro_series')
        make_usable_osystem(
            self, osystem_name=osystem, releases=[distro_series])
        response = self.client.post(
            self.get_machine_uri(machine), {'op': 'deploy'})
        response_info = json_load_bytes(response.content)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(response_info['osystem'], osystem)
        self.assertEqual(response_info['distro_series'], distro_series)

    def test_POST_deploy_fails_with_no_boot_source(self):
        machine = factory.make_Node(
            owner=self.logged_in_user, interface=True,
            power_type='manual',
            architecture=make_usable_architecture(self))
        response = self.client.post(
            self.get_machine_uri(machine), {'op': 'deploy'})
        self.assertEqual(
            (
                http.client.BAD_REQUEST,
                {'distro_series': [
                    "'%s' is not a valid distro_series.  "
                    "It should be one of: ''." %
                    Config.objects.get_config('default_distro_series')]}
            ),
            (response.status_code, json_load_bytes(response.content)))

    def test_POST_deploy_validates_hwe_kernel_with_default_distro_series(self):
        architecture = make_usable_architecture(self, subarch_name="generic")
        machine = factory.make_Node(
            owner=self.logged_in_user, interface=True,
            power_type='manual',
            architecture=architecture)
        osystem = Config.objects.get_config('default_osystem')
        distro_series = Config.objects.get_config('default_distro_series')
        make_usable_osystem(
            self, osystem_name=osystem, releases=[distro_series])
        bad_hwe_kernel = 'hwe-' + chr(ord(distro_series[0]) - 1)
        response = self.client.post(
            self.get_machine_uri(machine),
            {
                'op': 'deploy',
                'hwe_kernel': bad_hwe_kernel,
            })
        self.assertEqual(
            (
                http.client.BAD_REQUEST,
                {'hwe_kernel': [
                    "%s is not available for %s/%s on %s."
                    % (bad_hwe_kernel, osystem, distro_series, architecture)]}
            ),
            (response.status_code, json_load_bytes(response.content)))

    def test_POST_deploy_may_be_repeated(self):
        self.patch(node_module.Node, "_start")
        machine = factory.make_Node(
            owner=self.logged_in_user, interface=True,
            power_type='manual',
            architecture=make_usable_architecture(self))
        osystem = make_usable_osystem(self)
        distro_series = osystem['default_release']
        request = {
            'op': 'deploy',
            'distro_series': distro_series,
            }
        self.client.post(self.get_machine_uri(machine), request)
        response = self.client.post(self.get_machine_uri(machine), request)
        self.assertEqual(http.client.OK, response.status_code)

    def test_POST_deploy_stores_user_data(self):
        rack_controller = factory.make_RackController()
        self.patch(
            node_module.RackControllerManager, "filter_by_url_accessible"
            ).return_value = [rack_controller]
        self.patch(node_module.Node, "_power_control_node")
        machine = factory.make_Node(
            owner=self.logged_in_user, interface=True,
            power_type='virsh', architecture=make_usable_architecture(self),
            bmc_connected_to=rack_controller)
        osystem = make_usable_osystem(self)
        distro_series = osystem['default_release']
        user_data = (
            b'\xff\x00\xff\xfe\xff\xff\xfe' +
            factory.make_string().encode('ascii'))
        response = self.client.post(
            self.get_machine_uri(machine), {
                'op': 'deploy',
                'user_data': b64encode(user_data).decode('ascii'),
                'distro_series': distro_series,
            })
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            user_data, NodeUserData.objects.get_user_data(machine))

    def test_POST_deploy_passes_comment(self):
        self.patch(node_module.Node, "_start")
        rack_controller = factory.make_RackController()
        machine = factory.make_Node(
            owner=self.logged_in_user, interface=True,
            power_type='virsh',
            architecture=make_usable_architecture(self),
            bmc_connected_to=rack_controller)
        osystem = make_usable_osystem(self)
        distro_series = osystem['default_release']
        comment = factory.make_name('comment')
        machine_start = self.patch(node_module.Machine, 'start')
        machine_start.return_value = False
        self.client.post(
            self.get_machine_uri(machine), {
                'op': 'deploy',
                'user_data': None,
                'distro_series': distro_series,
                'comment': comment,
            })
        self.assertThat(machine_start, MockCalledOnceWith(
            self.logged_in_user, user_data=ANY, comment=comment))

    def test_POST_deploy_handles_missing_comment(self):
        machine = factory.make_Node(
            owner=self.logged_in_user, interface=True,
            power_type='manual',
            architecture=make_usable_architecture(self))
        osystem = make_usable_osystem(self)
        distro_series = osystem['default_release']
        machine_start = self.patch(node_module.Machine, 'start')
        machine_start.return_value = False
        self.client.post(
            self.get_machine_uri(machine), {
                'op': 'deploy',
                'user_data': None,
                'distro_series': distro_series,
            })
        self.assertThat(machine_start, MockCalledOnceWith(
            self.logged_in_user, user_data=ANY, comment=None))

    def test_POST_deploy_doesnt_reset_power_options_bug_1569102(self):
        self.become_admin()
        self.patch(node_module.Node, "_start")
        rack_controller = factory.make_RackController()
        machine = factory.make_Node(
            owner=self.logged_in_user, interface=True,
            power_type='virsh',
            architecture=make_usable_architecture(self),
            bmc_connected_to=rack_controller)
        osystem = make_usable_osystem(self)
        distro_series = osystem['default_release']
        machine_start = self.patch(node_module.Machine, 'start')
        machine_start.return_value = False
        response = self.client.post(
            self.get_machine_uri(machine), {
                'op': 'deploy',
                'distro_series': distro_series,
            })
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        response_content = json_load_bytes(response.content)
        self.assertEquals('virsh', response_content['power_type'])

    def test_POST_release_releases_owned_machine(self):
        self.patch(node_module.Node, '_stop')
        owned_statuses = [
            NODE_STATUS.RESERVED,
            NODE_STATUS.ALLOCATED,
        ]
        owned_machines = [
            factory.make_Node(
                owner=self.logged_in_user, status=status, power_type='virsh',
                power_state=POWER_STATE.ON)
            for status in owned_statuses]
        responses = [
            self.client.post(self.get_machine_uri(machine), {'op': 'release'})
            for machine in owned_machines]
        self.assertEqual(
            [http.client.OK] * len(owned_machines),
            [response.status_code for response in responses])
        self.assertItemsEqual(
            [NODE_STATUS.RELEASING] * len(owned_machines),
            [machine.status
             for machine in reload_objects(Node, owned_machines)])

    def test_POST_release_releases_failed_machine(self):
        self.patch(node_module.Node, '_stop')
        self.patch(node_module.Machine, 'start_transition_monitor')
        owned_machine = factory.make_Node(
            owner=self.logged_in_user,
            status=NODE_STATUS.FAILED_DEPLOYMENT,
            power_type='ipmi', power_state=POWER_STATE.ON)
        response = self.client.post(
            self.get_machine_uri(owned_machine), {'op': 'release'})
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        owned_machine = Machine.objects.get(id=owned_machine.id)
        self.expectThat(owned_machine.status, Equals(NODE_STATUS.RELEASING))
        self.expectThat(owned_machine.owner, Equals(self.logged_in_user))

    def test_POST_release_does_nothing_for_unowned_machine(self):
        machine = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.READY, owner=self.logged_in_user)
        response = self.client.post(
            self.get_machine_uri(machine), {'op': 'release'})
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(NODE_STATUS.READY, reload_object(machine).status)

    def test_POST_release_rejects_other_node_types(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=self.logged_in_user,
            node_type=factory.pick_choice(
                NODE_TYPE_CHOICES, but_not=[NODE_TYPE.MACHINE]),
            )
        response = self.client.post(
            self.get_machine_uri(node), {'op': 'release'})
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content)

    def test_POST_release_forbidden_if_user_cannot_edit_machine(self):
        machine = factory.make_Node(status=NODE_STATUS.READY)
        response = self.client.post(
            self.get_machine_uri(machine), {'op': 'release'})
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_POST_release_fails_for_other_machine_states(self):
        releasable_statuses = (
            RELEASABLE_STATUSES + [
                NODE_STATUS.RELEASING,
                NODE_STATUS.READY
            ])
        unreleasable_statuses = [
            status
            for status in map_enum(NODE_STATUS).values()
            if status not in releasable_statuses
        ]
        machines = [
            factory.make_Node(status=status, owner=self.logged_in_user)
            for status in unreleasable_statuses]
        responses = [
            self.client.post(self.get_machine_uri(machine), {'op': 'release'})
            for machine in machines]
        self.assertEqual(
            [http.client.CONFLICT] * len(unreleasable_statuses),
            [response.status_code for response in responses])
        self.assertItemsEqual(
            unreleasable_statuses,
            [machine.status for machine in reload_objects(Node, machines)])

    def test_POST_release_in_wrong_state_reports_current_state(self):
        machine = factory.make_Node(
            status=NODE_STATUS.RETIRED, owner=self.logged_in_user)
        response = self.client.post(
            self.get_machine_uri(machine), {'op': 'release'})
        self.assertEqual(
            (
                http.client.CONFLICT,
                "Machine cannot be released in its current state ('Retired').",
            ),
            (response.status_code,
             response.content.decode(settings.DEFAULT_CHARSET)))

    def test_POST_release_rejects_request_from_unauthorized_user(self):
        machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())
        response = self.client.post(
            self.get_machine_uri(machine), {'op': 'release'})
        self.assertEqual(http.client.FORBIDDEN, response.status_code)
        self.assertEqual(NODE_STATUS.ALLOCATED, reload_object(machine).status)

    def test_POST_release_allows_admin_to_release_anyones_machine(self):
        self.patch(node_module.Node, '_stop')
        self.patch(node_module.Machine, 'start_transition_monitor')
        machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User(),
            power_type='ipmi', power_state=POWER_STATE.ON)
        self.become_admin()
        response = self.client.post(
            self.get_machine_uri(machine), {'op': 'release'})
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        self.assertEqual(NODE_STATUS.RELEASING, reload_object(machine).status)

    def test_POST_release_combines_with_allocate(self):
        self.patch(node_module.Node, '_stop')
        self.patch(node_module.Machine, 'start_transition_monitor')
        machine = factory.make_Node(
            status=NODE_STATUS.READY, power_type='ipmi',
            power_state=POWER_STATE.ON, with_boot_disk=True)
        response = self.client.post(
            reverse('machines_handler'), {'op': 'allocate'})
        self.assertEqual(NODE_STATUS.ALLOCATED, reload_object(machine).status)
        machine_uri = json_load_bytes(response.content)['resource_uri']
        response = self.client.post(machine_uri, {'op': 'release'})
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        self.assertEqual(NODE_STATUS.RELEASING, reload_object(machine).status)

    def test_POST_allocate_passes_comment(self):
        factory.make_Node(
            status=NODE_STATUS.READY, power_type='ipmi',
            power_state=POWER_STATE.ON, with_boot_disk=True)
        machine_method = self.patch(node_module.Machine, 'acquire')
        comment = factory.make_name('comment')
        self.client.post(
            reverse('machines_handler'),
            {'op': 'allocate', 'comment': comment})
        self.assertThat(
            machine_method, MockCalledOnceWith(
                ANY, ANY, agent_name=ANY, comment=comment))

    def test_POST_allocate_handles_missing_comment(self):
        factory.make_Node(
            status=NODE_STATUS.READY, power_type='ipmi',
            power_state=POWER_STATE.ON, with_boot_disk=True)
        machine_method = self.patch(node_module.Machine, 'acquire')
        self.client.post(
            reverse('machines_handler'), {'op': 'allocate'})
        self.assertThat(
            machine_method, MockCalledOnceWith(
                ANY, ANY, agent_name=ANY, comment=None))

    def test_POST_release_frees_hwe_kernel(self):
        self.patch(node_module.Node, '_stop')
        self.patch(node_module.Machine, 'start_transition_monitor')
        machine = factory.make_Node(
            owner=self.logged_in_user, status=NODE_STATUS.ALLOCATED,
            power_type='ipmi', power_state=POWER_STATE.ON,
            hwe_kernel='hwe-v')
        self.assertEqual('hwe-v', reload_object(machine).hwe_kernel)
        response = self.client.post(
            self.get_machine_uri(machine), {'op': 'release'})
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        self.assertEqual(NODE_STATUS.RELEASING, reload_object(machine).status)
        self.assertEqual(None, reload_object(machine).hwe_kernel)

    def test_POST_release_passes_comment(self):
        machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User(),
            power_type='ipmi', power_state=POWER_STATE.OFF)
        self.become_admin()
        comment = factory.make_name('comment')
        machine_release = self.patch(node_module.Machine, 'release_or_erase')
        self.client.post(
            self.get_machine_uri(machine),
            {'op': 'release', 'comment': comment})
        self.assertThat(
            machine_release,
            MockCalledOnceWith(self.logged_in_user, comment))

    def test_POST_release_handles_missing_comment(self):
        machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User(),
            power_type='ipmi', power_state=POWER_STATE.OFF)
        self.become_admin()
        machine_release = self.patch(node_module.Machine, 'release_or_erase')
        self.client.post(
            self.get_machine_uri(machine), {'op': 'release'})
        self.assertThat(
            machine_release,
            MockCalledOnceWith(self.logged_in_user, None))

    def test_POST_commission_commissions_machine(self):
        self.patch(
            node_module.Node, "_start").return_value = defer.succeed(None)
        machine = factory.make_Node(
            status=NODE_STATUS.READY, owner=factory.make_User(),
            power_state=POWER_STATE.OFF)
        self.become_admin()
        response = self.client.post(
            self.get_machine_uri(machine), {'op': 'commission'})
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            NODE_STATUS.COMMISSIONING, reload_object(machine).status)

    def test_POST_commission_commissions_machine_with_options(self):
        self.patch(
            node_module.Node, "_start").return_value = defer.succeed(None)
        machine = factory.make_Node(
            status=NODE_STATUS.READY, owner=factory.make_User(),
            power_state=POWER_STATE.OFF)
        self.become_admin()
        response = self.client.post(self.get_machine_uri(machine), {
            'op': 'commission',
            'enable_ssh': "true",
            'skip_networking': 1,
            })
        self.assertEqual(http.client.OK, response.status_code)
        machine = reload_object(machine)
        self.assertTrue(machine.enable_ssh)
        self.assertTrue(machine.skip_networking)

    def test_PUT_updates_machine(self):
        self.become_admin()
        # The api allows the updating of a Machine.
        machine = factory.make_Node(
            hostname='diane', owner=self.logged_in_user,
            architecture=make_usable_architecture(self))
        response = self.client.put(
            self.get_machine_uri(machine), {'hostname': 'francis'})
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.OK, response.status_code)
        domain_name = Domain.objects.get_default_domain().name
        self.assertEqual(
            'francis.%s' % domain_name, parsed_result['fqdn'])
        self.assertEqual(0, Machine.objects.filter(hostname='diane').count())
        self.assertEqual(1, Machine.objects.filter(hostname='francis').count())

    def test_PUT_omitted_hostname(self):
        self.become_admin()
        hostname = factory.make_name('hostname')
        arch = make_usable_architecture(self)
        machine = factory.make_Node(
            hostname=hostname, owner=self.logged_in_user, architecture=arch)
        response = self.client.put(
            self.get_machine_uri(machine),
            {'architecture': arch})
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        self.assertTrue(Machine.objects.filter(hostname=hostname).exists())

    def test_PUT_rejects_other_node_types(self):
        self.become_admin()
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=self.logged_in_user,
            node_type=factory.pick_choice(
                NODE_TYPE_CHOICES, but_not=[NODE_TYPE.MACHINE]),
            )
        response = self.client.put(self.get_machine_uri(node))
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content)

    def test_PUT_ignores_unknown_fields(self):
        self.become_admin()
        machine = factory.make_Node(
            owner=self.logged_in_user,
            architecture=make_usable_architecture(self))
        field = factory.make_string()
        response = self.client.put(
            self.get_machine_uri(machine),
            {field: factory.make_string()}
        )

        self.assertEqual(http.client.OK, response.status_code)

    def test_PUT_admin_can_change_power_type(self):
        self.become_admin()
        original_power_type = factory.pick_power_type()
        new_power_type = factory.pick_power_type(but_not=original_power_type)
        machine = factory.make_Node(
            owner=self.logged_in_user,
            power_type=original_power_type,
            architecture=make_usable_architecture(self))
        response = self.client.put(
            self.get_machine_uri(machine), {'power_type': new_power_type})

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            new_power_type, reload_object(machine).power_type)

    def test_PUT_non_admin_cannot_change_power_type(self):
        original_power_type = factory.pick_power_type()
        new_power_type = factory.pick_power_type(but_not=original_power_type)
        machine = factory.make_Node(
            owner=self.logged_in_user, power_type=original_power_type)
        response = self.client.put(
            self.get_machine_uri(machine), {'power_type': new_power_type})

        self.assertEqual(http.client.FORBIDDEN, response.status_code)
        self.assertEqual(
            original_power_type, reload_object(machine).power_type)

    def test_resource_uri_points_back_at_machine(self):
        self.become_admin()
        # When a Machine is returned by the API, the field 'resource_uri'
        # provides the URI for this Machine.
        machine = factory.make_Node(
            hostname='diane', owner=self.logged_in_user,
            architecture=make_usable_architecture(self))
        response = self.client.put(
            self.get_machine_uri(machine), {'hostname': 'francis'})
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            reverse('machine_handler', args=[parsed_result['system_id']]),
            parsed_result['resource_uri'])

    def test_PUT_rejects_invalid_data(self):
        # If the data provided to update a machine is invalid, a 'Bad request'
        # response is returned.
        self.become_admin()
        machine = factory.make_Node(
            hostname='diane', owner=self.logged_in_user,
            architecture=make_usable_architecture(self))
        response = self.client.put(
            self.get_machine_uri(machine), {'hostname': '.'})
        parsed_result = json_load_bytes(response.content)

        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertEqual(
            {'hostname':
                ["DNS name contains an empty label.", "Nonexistant domain."]},
            parsed_result)

    def test_PUT_refuses_to_update_nonexistent_machine(self):
        # When updating a Machine, the api returns a 'Not Found' (404) error
        # if no machine is found.
        self.become_admin()
        url = reverse('machine_handler', args=['invalid-uuid'])
        response = self.client.put(url)

        self.assertEqual(http.client.NOT_FOUND, response.status_code)

    def test_PUT_updates_power_parameters_field(self):
        # The api allows the updating of a Machine's power_parameters field.
        self.become_admin()
        machine = factory.make_Node(
            owner=self.logged_in_user,
            power_type='virsh',
            architecture=make_usable_architecture(self))
        # Create a power_parameter valid for the selected power_type.
        new_power_id = factory.make_name('power_id')
        new_power_pass = factory.make_name('power_pass')
        new_power_address = factory.make_ipv4_address()
        response = self.client.put(
            self.get_machine_uri(machine),
            {
                'power_parameters_power_id': new_power_id,
                'power_parameters_power_pass': new_power_pass,
                'power_parameters_power_address': new_power_address,
            }
        )

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            {
                'power_id': new_power_id,
                'power_pass': new_power_pass,
                'power_address': new_power_address,
            },
            reload_object(machine).power_parameters)

    def test_PUT_updates_cpu_memory(self):
        self.become_admin()
        machine = factory.make_Node(
            owner=self.logged_in_user,
            power_type=factory.pick_power_type(),
            architecture=make_usable_architecture(self))
        response = self.client.put(
            self.get_machine_uri(machine),
            {'cpu_count': 1, 'memory': 1024})
        self.assertEqual(http.client.OK, response.status_code)
        machine = reload_object(machine)
        self.assertEqual(1, machine.cpu_count)
        self.assertEqual(1024, machine.memory)

    def test_PUT_updates_power_parameters_rejects_unknown_param(self):
        self.become_admin()
        power_parameters = {factory.make_string(): factory.make_string()}
        machine = factory.make_Node(
            owner=self.logged_in_user,
            power_type='manual',
            power_parameters=power_parameters,
            architecture=make_usable_architecture(self))
        response = self.client.put(
            self.get_machine_uri(machine),
            {'power_parameters_unknown_param': factory.make_string()})

        self.assertEqual(
            (
                http.client.BAD_REQUEST,
                {'power_parameters': ["Unknown parameter(s): unknown_param."]}
            ),
            (response.status_code, json_load_bytes(response.content)))
        self.assertEqual(
            power_parameters, reload_object(machine).power_parameters)

    def test_PUT_updates_power_type_default_resets_params(self):
        # If one sets power_type to empty, power_parameter gets
        # reset by default (if skip_check is not set).
        self.become_admin()
        power_parameters = {factory.make_string(): factory.make_string()}
        machine = factory.make_Node(
            owner=self.logged_in_user,
            power_type='manual',
            power_parameters=power_parameters,
            architecture=make_usable_architecture(self))
        response = self.client.put(
            self.get_machine_uri(machine),
            {'power_type': ''})

        machine = reload_object(machine)
        self.assertEqual(
            (http.client.OK, machine.power_type, machine.power_parameters),
            (response.status_code, '', {}))

    def test_PUT_updates_power_type_empty_rejects_params(self):
        # If one sets power_type to empty, one cannot set power_parameters.
        self.become_admin()
        power_parameters = {factory.make_string(): factory.make_string()}
        machine = factory.make_Node(
            owner=self.logged_in_user,
            power_type='manual',
            power_parameters=power_parameters,
            architecture=make_usable_architecture(self))
        new_param = factory.make_string()
        response = self.client.put(
            self.get_machine_uri(machine),
            {
                'power_type': '',
                'power_parameters_address': new_param,
            })

        machine = reload_object(machine)
        self.assertEqual(
            (
                http.client.BAD_REQUEST,
                {'power_parameters': ["Unknown parameter(s): address."]}
            ),
            (response.status_code, json_load_bytes(response.content)))
        self.assertEqual(
            power_parameters, reload_object(machine).power_parameters)

    def test_PUT_updates_power_type_empty_skip_check_to_force_params(self):
        # If one sets power_type to empty, it is possible to pass
        # power_parameter_skip_check='true' to force power_parameters.
        # XXX bigjools 2014-01-21 Why is this necessary?
        self.become_admin()
        power_parameters = {factory.make_string(): factory.make_string()}
        machine = factory.make_Node(
            owner=self.logged_in_user,
            power_type='manual',
            power_parameters=power_parameters,
            architecture=make_usable_architecture(self))
        new_param = factory.make_string()
        response = self.client.put(
            self.get_machine_uri(machine),
            {
                'power_type': '',
                'power_parameters_param': new_param,
                'power_parameters_skip_check': 'true',
            })

        machine = reload_object(machine)
        self.assertEqual(
            (http.client.OK, machine.power_type, machine.power_parameters),
            (response.status_code, '', {'param': new_param}))

    def test_PUT_updates_power_parameters_skip_ckeck(self):
        # With power_parameters_skip_check, arbitrary data
        # can be put in a Machine's power_parameter field.
        self.become_admin()
        machine = factory.make_Node(
            owner=self.logged_in_user,
            architecture=make_usable_architecture(self))
        new_param = factory.make_string()
        new_value = factory.make_string()
        response = self.client.put(
            self.get_machine_uri(machine),
            {
                'power_parameters_%s' % new_param: new_value,
                'power_parameters_skip_check': 'true',
            })

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            {new_param: new_value}, reload_object(machine).power_parameters)

    def test_PUT_updates_power_parameters_empty_string(self):
        self.become_admin()
        power_parameters = {factory.make_string(): factory.make_string()}
        machine = factory.make_Node(
            owner=self.logged_in_user,
            power_type='virsh',
            power_parameters=power_parameters,
            architecture=make_usable_architecture(self))
        response = self.client.put(
            self.get_machine_uri(machine),
            {'power_parameters_power_id': ''})

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            {
                'power_id': '',
                'power_pass': '',
                'power_address': '',
            },
            reload_object(machine).power_parameters)

    def test_PUT_sets_zone(self):
        self.become_admin()
        new_zone = factory.make_Zone()
        machine = factory.make_Node(
            architecture=make_usable_architecture(self))

        response = self.client.put(
            self.get_machine_uri(machine), {'zone': new_zone.name})

        self.assertEqual(http.client.OK, response.status_code)
        machine = reload_object(machine)
        self.assertEqual(new_zone, machine.zone)

    def test_PUT_does_not_set_zone_if_not_present(self):
        self.become_admin()
        new_name = factory.make_name()
        machine = factory.make_Node(
            architecture=make_usable_architecture(self))
        old_zone = machine.zone

        response = self.client.put(
            self.get_machine_uri(machine), {'hostname': new_name})

        self.assertEqual(http.client.OK, response.status_code)
        machine = reload_object(machine)
        self.assertEqual(
            (old_zone, new_name), (machine.zone, machine.hostname))

    def test_PUT_clears_zone(self):
        self.skip(
            "XXX: JeroenVermeulen 2013-12-11 bug=1259872: Clearing the "
            "zone field does not work...")

        self.become_admin()
        machine = factory.make_Node(zone=factory.make_Zone())

        response = self.client.put(self.get_machine_uri(machine), {'zone': ''})

        self.assertEqual(http.client.OK, response.status_code)
        machine = reload_object(machine)
        self.assertEqual(None, machine.zone)

    def test_PUT_without_zone_leaves_zone_unchanged(self):
        self.become_admin()
        zone = factory.make_Zone()
        machine = factory.make_Node(
            zone=zone, architecture=make_usable_architecture(self))

        response = self.client.put(self.get_machine_uri(machine), {})

        self.assertEqual(http.client.OK, response.status_code)
        machine = reload_object(machine)
        self.assertEqual(zone, machine.zone)

    def test_PUT_requires_admin(self):
        machine = factory.make_Node(
            owner=self.logged_in_user,
            architecture=make_usable_architecture(self))
        # PUT the machine with no arguments - should get FORBIDDEN
        response = self.client.put(self.get_machine_uri(machine), {})
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_PUT_zone_change_requires_admin(self):
        new_zone = factory.make_Zone()
        machine = factory.make_Node(
            owner=self.logged_in_user,
            architecture=make_usable_architecture(self))
        old_zone = machine.zone

        response = self.client.put(
            self.get_machine_uri(machine),
            {'zone': new_zone.name})

        self.assertEqual(http.client.FORBIDDEN, response.status_code)
        # Confirm the machine's physical zone has not been updated.
        machine = reload_object(machine)
        self.assertEqual(old_zone, machine.zone)

    def test_PUT_sets_disable_ipv4(self):
        self.become_admin()
        original_setting = factory.pick_bool()
        machine = factory.make_Node(
            owner=self.logged_in_user,
            architecture=make_usable_architecture(self),
            disable_ipv4=original_setting)
        new_setting = not original_setting

        response = self.client.put(
            self.get_machine_uri(machine), {'disable_ipv4': new_setting})
        self.assertEqual(http.client.OK, response.status_code)

        machine = reload_object(machine)
        self.assertEqual(new_setting, machine.disable_ipv4)

    def test_PUT_leaves_disable_ipv4_unchanged_by_default(self):
        self.become_admin()
        original_setting = factory.pick_bool()
        machine = factory.make_Node(
            owner=self.logged_in_user,
            architecture=make_usable_architecture(self),
            disable_ipv4=original_setting)
        self.assertEqual(original_setting, machine.disable_ipv4)

        response = self.client.put(
            self.get_machine_uri(machine), {'zone': factory.make_Zone()})
        self.assertEqual(http.client.OK, response.status_code)

        machine = reload_object(machine)
        self.assertEqual(original_setting, machine.disable_ipv4)

    def test_PUT_updates_swap_size(self):
        self.become_admin()
        machine = factory.make_Node(
            owner=self.logged_in_user,
            architecture=make_usable_architecture(self))
        response = self.client.put(
            reverse('machine_handler', args=[machine.system_id]),
            {'swap_size': 5 * 1000 ** 3})  # Making sure we overflow 32 bits
        parsed_result = json_load_bytes(response.content)
        machine = reload_object(machine)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(machine.swap_size, parsed_result['swap_size'])

    def test_PUT_updates_swap_size_suffixes(self):
        self.become_admin()
        machine = factory.make_Node(
            owner=self.logged_in_user,
            architecture=make_usable_architecture(self))

        response = self.client.put(
            reverse('machine_handler', args=[machine.system_id]),
            {'swap_size': '5K'})
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(5000, parsed_result['swap_size'])

        response = self.client.put(
            reverse('machine_handler', args=[machine.system_id]),
            {'swap_size': '5M'})
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(5000000, parsed_result['swap_size'])

        response = self.client.put(
            reverse('machine_handler', args=[machine.system_id]),
            {'swap_size': '5G'})
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(5000000000, parsed_result['swap_size'])

        response = self.client.put(
            reverse('machine_handler', args=[machine.system_id]),
            {'swap_size': '5T'})
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(5000000000000, parsed_result['swap_size'])

    def test_PUT_updates_swap_size_invalid_suffix(self):
        self.become_admin()
        machine = factory.make_Node(
            owner=self.logged_in_user,
            architecture=make_usable_architecture(self))
        response = self.client.put(
            reverse('machine_handler', args=[machine.system_id]),
            {'swap_size': '5E'})  # We won't support exabytes yet
        parsed_result = json_load_bytes(response.content)
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertEqual('Invalid size for swap: 5E',
                         parsed_result['swap_size'][0])

    def test_DELETE_deletes_machine(self):
        # The api allows to delete a Machine.
        self.become_admin()
        machine = factory.make_Node(owner=self.logged_in_user)
        system_id = machine.system_id
        response = self.client.delete(self.get_machine_uri(machine))

        self.assertEqual(204, response.status_code)
        self.assertItemsEqual([], Machine.objects.filter(system_id=system_id))

    def test_DELETE_rejects_other_node_types(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=self.logged_in_user,
            node_type=factory.pick_choice(
                NODE_TYPE_CHOICES, but_not=[NODE_TYPE.MACHINE]),
            )
        response = self.client.delete(self.get_machine_uri(node))
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content)

    def test_DELETE_deletes_machine_fails_if_not_admin(self):
        # Only superusers can delete machines.
        machine = factory.make_Node(owner=self.logged_in_user)
        response = self.client.delete(self.get_machine_uri(machine))

        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_DELETE_forbidden_without_edit_permission(self):
        # A user without the edit permission cannot delete a Machine.
        machine = factory.make_Node()
        response = self.client.delete(self.get_machine_uri(machine))

        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_DELETE_refuses_to_delete_invisible_machine(self):
        # The request to delete a single machine is denied if the machine isn't
        # visible by the user.
        other_machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())

        response = self.client.delete(self.get_machine_uri(other_machine))

        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_DELETE_refuses_to_delete_nonexistent_machine(self):
        # When deleting a Machine, the api returns a 'Not Found' (404) error
        # if no machine is found.
        url = reverse('machine_handler', args=['invalid-uuid'])
        response = self.client.delete(url)

        self.assertEqual(http.client.NOT_FOUND, response.status_code)


class TestMachineAPITransactional(APITransactionTestCase):
    '''The following TestMachineAPI tests require APITransactionTestCase,
        and thus, have been separated from the TestMachineAPI above.
    '''

    def test_POST_start_returns_error_when_static_ips_exhausted(self):
        self.patch(node_module, 'power_driver_check')
        network = IPNetwork("10.0.0.0/30")
        rack_controller = factory.make_RackController()
        subnet = factory.make_Subnet(cidr=str(network.cidr))
        subnet.vlan.dhcp_on = True
        subnet.vlan.primary_rack = rack_controller
        subnet.vlan.save()
        architecture = make_usable_architecture(self)
        machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, architecture=architecture,
            power_type='virsh', owner=self.logged_in_user,
            power_state=POWER_STATE.OFF,
            bmc_connected_to=rack_controller)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=machine, vlan=subnet.vlan)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="", subnet=subnet,
            interface=interface)

        # Pre-claim the only addresses.
        with transaction.atomic():
            StaticIPAddress.objects.allocate_new(
                requested_address="10.0.0.1")
            StaticIPAddress.objects.allocate_new(
                requested_address="10.0.0.2")
            StaticIPAddress.objects.allocate_new(
                requested_address="10.0.0.3")

        osystem = make_usable_osystem(self)
        distro_series = osystem['default_release']
        response = self.client.post(
            TestMachineAPI.get_machine_uri(machine),
            {
                'op': 'power_on',
                'distro_series': distro_series,
            })
        self.assertEqual(
            http.client.SERVICE_UNAVAILABLE, response.status_code,
            response.content)


class TestAbort(APITransactionTestCase):
    """Tests for /api/2.0/machines/<machine>/?op=abort"""

    def get_machine_uri(self, machine):
        """Get the API URI for `machine`."""
        return reverse('machine_handler', args=[machine.system_id])

    def test_abort_changes_state(self):
        machine = factory.make_Node(
            status=NODE_STATUS.DISK_ERASING, owner=self.logged_in_user)
        machine_stop = self.patch(node_module.Node, "_stop")
        machine_stop.side_effect = lambda user: post_commit()

        response = self.client.post(
            self.get_machine_uri(machine), {'op': 'abort'})

        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            NODE_STATUS.FAILED_DISK_ERASING, reload_object(machine).status)

    def test_abort_fails_for_unsupported_operation(self):
        machine = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        response = self.client.post(
            self.get_machine_uri(machine), {'op': 'abort'})
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_abort_passes_comment(self):
        self.become_admin()
        machine = factory.make_Node(
            status=NODE_STATUS.DISK_ERASING, owner=self.logged_in_user)
        machine_method = self.patch(node_module.Machine, 'abort_operation')
        comment = factory.make_name('comment')
        self.client.post(
            self.get_machine_uri(machine),
            {'op': 'abort', 'comment': comment})
        self.assertThat(
            machine_method,
            MockCalledOnceWith(self.logged_in_user, comment))

    def test_abort_handles_missing_comment(self):
        self.become_admin()
        machine = factory.make_Node(
            status=NODE_STATUS.DISK_ERASING, owner=self.logged_in_user)
        machine_method = self.patch(node_module.Machine, 'abort_operation')
        self.client.post(
            self.get_machine_uri(machine), {'op': 'abort'})
        self.assertThat(
            machine_method,
            MockCalledOnceWith(self.logged_in_user, None))


class TestSetStorageLayout(APITestCase):

    def get_machine_uri(self, machine):
        """Get the API URI for `machine`."""
        return reverse('machine_handler', args=[machine.system_id])

    def test__403_when_not_admin(self):
        machine = factory.make_Node(status=NODE_STATUS.READY)
        response = self.client.post(
            self.get_machine_uri(machine), {'op': 'set_storage_layout'})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content)

    def test__409_when_machine_not_ready(self):
        self.become_admin()
        machine = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        response = self.client.post(
            self.get_machine_uri(machine), {'op': 'set_storage_layout'})
        self.assertEqual(
            http.client.CONFLICT, response.status_code, response.content)

    def test__400_when_storage_layout_missing(self):
        self.become_admin()
        machine = factory.make_Node(status=NODE_STATUS.READY)
        response = self.client.post(
            self.get_machine_uri(machine), {'op': 'set_storage_layout'})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content)
        self.assertEqual({
            "storage_layout": [
                "This field is required."],
            }, json_load_bytes(response.content))

    def test__400_when_invalid_optional_param(self):
        self.become_admin()
        machine = factory.make_Node(status=NODE_STATUS.READY)
        factory.make_PhysicalBlockDevice(node=machine)
        response = self.client.post(
            self.get_machine_uri(machine), {
                'op': 'set_storage_layout',
                'storage_layout': 'flat',
                'boot_size': MIN_BOOT_PARTITION_SIZE - 1,
                })
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content)
        self.assertEqual({
            "boot_size": [
                "Size is too small. Minimum size is %s." % (
                    MIN_BOOT_PARTITION_SIZE)],
            }, json_load_bytes(response.content))

    def test__400_when_no_boot_disk(self):
        self.become_admin()
        machine = factory.make_Node(
            status=NODE_STATUS.READY, with_boot_disk=False)
        response = self.client.post(
            self.get_machine_uri(machine), {
                'op': 'set_storage_layout',
                'storage_layout': 'flat',
                })
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content)
        self.assertEqual(
            "Machine is missing a boot disk; no storage layout can be "
            "applied.", response.content.decode(settings.DEFAULT_CHARSET))

    def test__400_when_layout_error(self):
        self.become_admin()
        machine = factory.make_Node(status=NODE_STATUS.READY)
        mock_set_storage_layout = self.patch(Machine, "set_storage_layout")
        error_msg = factory.make_name("error")
        mock_set_storage_layout.side_effect = StorageLayoutError(error_msg)

        response = self.client.post(
            self.get_machine_uri(machine), {
                'op': 'set_storage_layout',
                'storage_layout': 'flat',
                })
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content)
        self.assertEqual(
            "Failed to configure storage layout 'flat': %s" % error_msg,
            response.content.decode(settings.DEFAULT_CHARSET))

    def test__400_when_layout_not_supported(self):
        self.become_admin()
        machine = factory.make_Node(status=NODE_STATUS.READY)
        factory.make_PhysicalBlockDevice(node=machine)
        response = self.client.post(
            self.get_machine_uri(machine), {
                'op': 'set_storage_layout',
                'storage_layout': 'bcache',
                })
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content)
        self.assertEqual(
            "Failed to configure storage layout 'bcache': Node doesn't "
            "have an available cache device to setup bcache.",
            response.content.decode(settings.DEFAULT_CHARSET))

    def test__calls_set_storage_layout_on_machine(self):
        self.become_admin()
        machine = factory.make_Node(status=NODE_STATUS.READY)
        mock_set_storage_layout = self.patch(Machine, "set_storage_layout")
        response = self.client.post(
            self.get_machine_uri(machine), {
                'op': 'set_storage_layout',
                'storage_layout': 'flat',
                })
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        self.assertThat(
            mock_set_storage_layout,
            MockCalledOnceWith('flat', params=ANY, allow_fallback=False))


class TestMountSpecial(APITestCase):
    """Tests for op=mount_special."""

    def get_machine_uri(self, machine):
        """Get the API URI for `machine`."""
        return reverse('machine_handler', args=[machine.system_id])

    def test__fstype_and_mount_point_is_required_but_options_is_not(self):
        machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.logged_in_user)
        response = self.client.post(
            self.get_machine_uri(machine), {'op': 'mount_special'})
        self.assertThat(response.status_code, Equals(http.client.BAD_REQUEST))
        self.assertThat(
            json_load_bytes(response.content), Equals({
                'fstype': ['This field is required.'],
                'mount_point': ['This field is required.'],
            }))

    def test__fstype_must_be_a_non_storage_type(self):
        machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.logged_in_user)
        for fstype in Filesystem.TYPES_REQUIRING_STORAGE:
            response = self.client.post(
                self.get_machine_uri(machine), {
                    'op': 'mount_special', 'fstype': fstype,
                    'mount_point': factory.make_absolute_path(),
                })
            self.assertThat(
                response.status_code, Equals(http.client.BAD_REQUEST))
            self.expectThat(
                json_load_bytes(response.content),
                ContainsDict({
                    'fstype': MatchesListwise([
                        StartsWith("Select a valid choice."),
                    ]),
                }),
                "using fstype " + fstype)

    def test__mount_point_must_be_absolute(self):
        machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.logged_in_user)
        response = self.client.post(
            self.get_machine_uri(machine), {
                'op': 'mount_special', 'fstype': FILESYSTEM_TYPE.RAMFS,
                'mount_point': factory.make_name("path"),
            })
        self.assertThat(
            response.status_code, Equals(http.client.BAD_REQUEST))
        self.assertThat(
            json_load_bytes(response.content), ContainsDict({
                # XXX: Wow, what a lame error from AbsolutePathField!
                'mount_point': Equals(["Enter a valid value."]),
            }))


class TestMountSpecialScenarios(APITestCase):
    """Scenario tests for op=mount_special."""

    scenarios = [
        (displayname, {"fstype": name})
        for name, displayname in FILESYSTEM_FORMAT_TYPE_CHOICES
        if name not in Filesystem.TYPES_REQUIRING_STORAGE
    ]

    def get_machine_uri(self, machine):
        """Get the API URI for `machine`."""
        return reverse('machine_handler', args=[machine.system_id])

    def test__machine_representation_includes_non_storage_filesystem(self):
        self.become_admin()
        machine = factory.make_Node(status=NODE_STATUS.READY)
        filesystem = factory.make_Filesystem(node=machine, fstype=self.fstype)
        response = self.client.get(self.get_machine_uri(machine))
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        self.assertThat(
            json_load_bytes(response.content),
            ContainsDict({
                "special_filesystems": MatchesListwise([
                    ContainsDict({
                        "fstype": Equals(filesystem.fstype),
                        "label": Equals(filesystem.label),
                        "mount_options": Equals(filesystem.mount_options),
                        "mount_point": Equals(filesystem.mount_point),
                        "uuid": Equals(filesystem.uuid),
                    }),
                ]),
            }))

    def assertCanMountFilesystem(self, machine):
        mount_point = factory.make_absolute_path()
        mount_options = factory.make_name("options")
        response = self.client.post(
            self.get_machine_uri(machine), {
                'op': 'mount_special', 'fstype': self.fstype,
                'mount_point': mount_point,
                'mount_options': mount_options,
            })
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        self.assertThat(
            list(Filesystem.objects.filter(node=machine)),
            MatchesListwise([
                MatchesStructure.byEquality(
                    fstype=self.fstype, mount_point=mount_point,
                    mount_options=mount_options, node=machine),
            ]))

    def test__user_mounts_non_storage_filesystem_on_allocated_machine(self):
        self.assertCanMountFilesystem(factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.logged_in_user))

    def test__user_forbidden_to_mount_on_non_allocated_machine(self):
        statuses = {name for name, _ in NODE_STATUS_CHOICES}
        statuses -= {NODE_STATUS.ALLOCATED}
        for status in statuses:
            machine = factory.make_Node(status=status)
            response = self.client.post(
                self.get_machine_uri(machine), {
                    'op': 'mount_special', 'fstype': self.fstype,
                    'mount_point': factory.make_absolute_path(),
                    'mount_options': factory.make_name("options"),
                })
            self.expectThat(
                response.status_code, Equals(http.client.FORBIDDEN),
                "using status %d" % status)

    def test__admin_mounts_non_storage_filesystem_on_allocated_machine(self):
        self.become_admin()
        self.assertCanMountFilesystem(factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.logged_in_user))

    def test__admin_mounts_non_storage_filesystem_on_ready_machine(self):
        self.become_admin()
        self.assertCanMountFilesystem(
            factory.make_Node(status=NODE_STATUS.READY))

    def test__admin_cannot_mount_on_non_ready_or_allocated_machine(self):
        self.become_admin()
        statuses = {name for name, _ in NODE_STATUS_CHOICES}
        statuses -= {NODE_STATUS.READY, NODE_STATUS.ALLOCATED}
        for status in statuses:
            machine = factory.make_Node(status=status)
            response = self.client.post(
                self.get_machine_uri(machine), {
                    'op': 'mount_special', 'fstype': self.fstype,
                    'mount_point': factory.make_absolute_path(),
                    'mount_options': factory.make_name("options"),
                })
            self.expectThat(
                response.status_code, Equals(http.client.CONFLICT),
                "using status %d" % status)


class TestUnmountSpecial(APITestCase):
    """Tests for op=unmount_special."""

    def get_machine_uri(self, machine):
        """Get the API URI for `machine`."""
        return reverse('machine_handler', args=[machine.system_id])

    def test__mount_point_is_required(self):
        machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.logged_in_user)
        response = self.client.post(
            self.get_machine_uri(machine), {'op': 'unmount_special'})
        self.assertThat(response.status_code, Equals(http.client.BAD_REQUEST))
        self.assertThat(
            json_load_bytes(response.content), Equals({
                'mount_point': ['This field is required.'],
            }))

    def test__mount_point_must_be_absolute(self):
        machine = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.logged_in_user)
        response = self.client.post(
            self.get_machine_uri(machine), {
                'op': 'unmount_special',
                'mount_point': factory.make_name("path"),
            })
        self.assertThat(
            response.status_code, Equals(http.client.BAD_REQUEST))
        self.assertThat(
            json_load_bytes(response.content), ContainsDict({
                # XXX: Wow, what a lame error from AbsolutePathField!
                'mount_point': Equals(["Enter a valid value."]),
            }))


class TestUnmountSpecialScenarios(APITestCase):
    """Scenario tests for op=unmount_special."""

    scenarios = [
        (displayname, {"fstype": name})
        for name, displayname in FILESYSTEM_FORMAT_TYPE_CHOICES
        if name not in Filesystem.TYPES_REQUIRING_STORAGE
    ]

    def get_machine_uri(self, machine):
        """Get the API URI for `machine`."""
        return reverse('machine_handler', args=[machine.system_id])

    def assertCanUnmountFilesystem(self, machine):
        filesystem = factory.make_Filesystem(
            node=machine, fstype=self.fstype,
            mount_point=factory.make_absolute_path())
        response = self.client.post(
            self.get_machine_uri(machine), {
                'op': 'unmount_special', 'mount_point': filesystem.mount_point,
            })
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        self.assertThat(
            Filesystem.objects.filter(node=machine),
            HasLength(0))

    def test__user_unmounts_non_storage_filesystem_on_allocated_machine(self):
        self.assertCanUnmountFilesystem(factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.logged_in_user))

    def test__user_forbidden_to_unmount_on_non_allocated_machine(self):
        statuses = {name for name, _ in NODE_STATUS_CHOICES}
        statuses -= {NODE_STATUS.ALLOCATED}
        for status in statuses:
            machine = factory.make_Node(status=status)
            filesystem = factory.make_Filesystem(
                node=machine, fstype=self.fstype,
                mount_point=factory.make_absolute_path())
            response = self.client.post(
                self.get_machine_uri(machine), {
                    'op': 'unmount_special',
                    'mount_point': filesystem.mount_point,
                })
            self.expectThat(
                response.status_code, Equals(http.client.FORBIDDEN),
                "using status %d" % status)

    def test__admin_unmounts_non_storage_filesystem_on_allocated_machine(self):
        self.become_admin()
        self.assertCanUnmountFilesystem(factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=self.logged_in_user))

    def test__admin_unmounts_non_storage_filesystem_on_ready_machine(self):
        self.become_admin()
        self.assertCanUnmountFilesystem(
            factory.make_Node(status=NODE_STATUS.READY))

    def test__admin_cannot_unmount_on_non_ready_or_allocated_machine(self):
        self.become_admin()
        statuses = {name for name, _ in NODE_STATUS_CHOICES}
        statuses -= {NODE_STATUS.READY, NODE_STATUS.ALLOCATED}
        for status in statuses:
            machine = factory.make_Node(status=status)
            filesystem = factory.make_Filesystem(
                node=machine, fstype=self.fstype,
                mount_point=factory.make_absolute_path())
            response = self.client.post(
                self.get_machine_uri(machine), {
                    'op': 'unmount_special',
                    'mount_point': filesystem.mount_point,
                })
            self.expectThat(
                response.status_code, Equals(http.client.CONFLICT),
                "using status %d" % status)


class TestClearDefaultGateways(APITestCase):

    def get_machine_uri(self, machine):
        """Get the API URI for `machine`."""
        return reverse('machine_handler', args=[machine.system_id])

    def test__403_when_not_admin(self):
        machine = factory.make_Node(
            owner=self.logged_in_user, status=NODE_STATUS.ALLOCATED)
        response = self.client.post(
            self.get_machine_uri(machine), {'op': 'clear_default_gateways'})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content)

    def test__clears_default_gateways(self):
        self.become_admin()
        machine = factory.make_Node(
            owner=self.logged_in_user, status=NODE_STATUS.ALLOCATED)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=machine)
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(
            cidr=str(network_v4.cidr), vlan=interface.vlan)
        link_v4 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="",
            subnet=subnet_v4, interface=interface)
        machine.gateway_link_ipv4 = link_v4
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(
            cidr=str(network_v6.cidr), vlan=interface.vlan)
        link_v6 = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="",
            subnet=subnet_v6, interface=interface)
        machine.gateway_link_ipv6 = link_v6
        machine.save()
        response = self.client.post(
            self.get_machine_uri(machine), {'op': 'clear_default_gateways'})
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        machine = reload_object(machine)
        self.assertIsNone(machine.gateway_link_ipv4)
        self.assertIsNone(machine.gateway_link_ipv6)


class TestGetCurtinConfig(APITestCase):

    def get_machine_uri(self, machine):
        """Get the API URI for `machine`."""
        return reverse('machine_handler', args=[machine.system_id])

    def test__500_when_machine_not_in_deployment_state(self):
        machine = factory.make_Node(
            owner=self.logged_in_user,
            status=factory.pick_enum(
                NODE_STATUS, but_not=[
                    NODE_STATUS.DEPLOYING,
                    NODE_STATUS.DEPLOYED,
                    NODE_STATUS.FAILED_DEPLOYMENT,
                ]))
        response = self.client.get(
            self.get_machine_uri(machine), {'op': 'get_curtin_config'})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content)

    def test__returns_curtin_config_in_yaml(self):
        machine = factory.make_Node(
            owner=self.logged_in_user, status=NODE_STATUS.DEPLOYING)
        fake_config = {
            "config": factory.make_name("config")
        }
        mock_get_curtin_merged_config = self.patch(
            machines_module, "get_curtin_merged_config")
        mock_get_curtin_merged_config.return_value = fake_config
        response = self.client.get(
            self.get_machine_uri(machine), {'op': 'get_curtin_config'})
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        self.assertEqual(
            yaml.safe_dump(fake_config, default_flow_style=False),
            response.content.decode(settings.DEFAULT_CHARSET))
        self.assertThat(
            mock_get_curtin_merged_config, MockCalledOnceWith(machine))


class TestMarkBroken(APITestCase):
    """Tests for /api/2.0/machines/<node>/?op=mark_broken"""

    def get_node_uri(self, node):
        """Get the API URI for `node`."""
        return reverse('machine_handler', args=[node.system_id])

    def test_mark_broken_changes_status(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, owner=self.logged_in_user)
        response = self.client.post(
            self.get_node_uri(node), {'op': 'mark_broken'})
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(NODE_STATUS.BROKEN, reload_object(node).status)

    def test_mark_broken_updates_error_description(self):
        # 'error_description' parameter was renamed 'comment' for consistency
        # make sure this comment updates the node's error_description
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, owner=self.logged_in_user)
        comment = factory.make_name('comment')
        response = self.client.post(
            self.get_node_uri(node),
            {'op': 'mark_broken', 'comment': comment})
        self.assertEqual(http.client.OK, response.status_code)
        node = reload_object(node)
        self.assertEqual(
            (NODE_STATUS.BROKEN, comment),
            (node.status, node.error_description)
        )

    def test_mark_broken_updates_error_description_compatibility(self):
        # test old 'error_description' parameter is honored for compatibility
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, owner=self.logged_in_user)
        error_description = factory.make_name('error_description')
        response = self.client.post(
            self.get_node_uri(node),
            {'op': 'mark_broken', 'error_description': error_description})
        self.assertEqual(http.client.OK, response.status_code)
        node = reload_object(node)
        self.assertEqual(
            (NODE_STATUS.BROKEN, error_description),
            (node.status, node.error_description)
        )

    def test_mark_broken_passes_comment(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, owner=self.logged_in_user)
        node_mark_broken = self.patch(node_module.Node, 'mark_broken')
        comment = factory.make_name('comment')
        self.client.post(
            self.get_node_uri(node),
            {'op': 'mark_broken', 'comment': comment})
        self.assertThat(
            node_mark_broken,
            MockCalledOnceWith(self.logged_in_user, comment))

    def test_mark_broken_handles_missing_comment(self):
        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, owner=self.logged_in_user)
        node_mark_broken = self.patch(node_module.Node, 'mark_broken')
        self.client.post(
            self.get_node_uri(node), {'op': 'mark_broken'})
        self.assertThat(
            node_mark_broken,
            MockCalledOnceWith(self.logged_in_user, None))

    def test_mark_broken_requires_ownership(self):
        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        response = self.client.post(
            self.get_node_uri(node), {'op': 'mark_broken'})
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_mark_broken_allowed_from_any_other_state(self):
        self.patch(node_module.Node, "_stop")
        for status, _ in NODE_STATUS_CHOICES:
            if status == NODE_STATUS.BROKEN:
                continue

            node = factory.make_Node(status=status, owner=self.logged_in_user)
            response = self.client.post(
                self.get_node_uri(node), {'op': 'mark_broken'})
            self.expectThat(
                response.status_code, Equals(http.client.OK), response)
            node = reload_object(node)
            self.expectThat(node.status, Equals(NODE_STATUS.BROKEN))


class TestMarkFixed(APITestCase):
    """Tests for /api/2.0/machines/<node>/?op=mark_fixed"""

    def get_node_uri(self, node):
        """Get the API URI for `node`."""
        return reverse('machine_handler', args=[node.system_id])

    def test_mark_fixed_changes_status(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.BROKEN)
        response = self.client.post(
            self.get_node_uri(node), {'op': 'mark_fixed'})
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(NODE_STATUS.READY, reload_object(node).status)

    def test_mark_fixed_requires_admin(self):
        node = factory.make_Node(status=NODE_STATUS.BROKEN)
        response = self.client.post(
            self.get_node_uri(node), {'op': 'mark_fixed'})
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_mark_fixed_passes_comment(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.BROKEN)
        node_mark_fixed = self.patch(node_module.Node, 'mark_fixed')
        comment = factory.make_name('comment')
        self.client.post(
            self.get_node_uri(node),
            {'op': 'mark_fixed', 'comment': comment})
        self.assertThat(
            node_mark_fixed,
            MockCalledOnceWith(self.logged_in_user, comment))

    def test_mark_fixed_handles_missing_comment(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.BROKEN)
        node_mark_fixed = self.patch(node_module.Node, 'mark_fixed')
        self.client.post(
            self.get_node_uri(node), {'op': 'mark_fixed'})
        self.assertThat(
            node_mark_fixed,
            MockCalledOnceWith(self.logged_in_user, None))
