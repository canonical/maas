# Copyright 2013-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the NodeGroups API."""

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
from textwrap import dedent

from apiclient.maas_client import MAASClient
import bson
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.urlresolvers import reverse
from fixtures import EnvironmentVariableFixture
from maasserver import api as api_module
from maasserver.api import update_mac_cluster_interfaces
from maasserver.enum import (
    NODEGROUP_STATUS,
    NODEGROUP_STATUS_CHOICES,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.models import (
    Config,
    DHCPLease,
    DownloadProgress,
    MACAddress,
    NodeGroup,
    nodegroup as nodegroup_module,
    )
from maasserver.refresh_worker import refresh_worker
from maasserver.testing import (
    reload_object,
    reload_objects,
    )
from maasserver.testing.api import (
    APITestCase,
    explain_unexpected_response,
    log_in_as_normal_user,
    make_worker_client,
    MultipleUsersScenarios,
    )
from maasserver.testing.factory import factory
from maasserver.testing.oauthclient import OAuthAuthenticatedClient
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.celery import CeleryFixture
from maastesting.fakemethod import FakeMethod
from maastesting.matchers import MockCalledOnceWith
from metadataserver.fields import Bin
from metadataserver.models import (
    commissioningscript,
    NodeCommissionResult,
    )
from mock import Mock
import netaddr
from provisioningserver import tasks
from provisioningserver.auth import get_recorded_nodegroup_uuid
from provisioningserver.dhcp.leases import send_leases
from provisioningserver.omshell import Omshell
from testresources import FixtureResource
from testtools.matchers import (
    AllMatch,
    Equals,
    HasLength,
    )


def get_random_ip_from_interface_range(interface):
    """Return a random IP from the pool available to an interface.

    :return: An IP address as a string."""
    ip_range = netaddr.IPRange(
        interface.ip_range_low, interface.ip_range_high)
    chosen_ip = random.choice(ip_range)
    return unicode(chosen_ip)


class TestNodeGroupsAPI(MultipleUsersScenarios,
                        MAASServerTestCase):
    scenarios = [
        ('anon', dict(userfactory=lambda: AnonymousUser())),
        ('user', dict(userfactory=factory.make_user)),
        ('admin', dict(userfactory=factory.make_admin)),
        ]

    resources = (
        ('celery', FixtureResource(CeleryFixture())),
        )

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/nodegroups/', reverse('nodegroups_handler'))

    def test_reverse_points_to_nodegroups_api(self):
        self.assertEqual(
            reverse('nodegroups_handler'), reverse('nodegroups_handler'))

    def test_nodegroups_index_lists_nodegroups(self):
        # The nodegroups index lists node groups for the MAAS.
        nodegroup = factory.make_node_group()
        response = self.client.get(
            reverse('nodegroups_handler'), {'op': 'list'})
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            [{
                'uuid': nodegroup.uuid,
                'status': nodegroup.status,
                'name': nodegroup.name,
                'cluster_name': nodegroup.cluster_name,
            }],
            json.loads(response.content))


class TestAnonNodeGroupsAPI(MAASServerTestCase):

    resources = (
        ('celery', FixtureResource(CeleryFixture())),
        )

    def test_refresh_calls_refresh_worker(self):
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED)
        response = self.client.post(
            reverse('nodegroups_handler'), {'op': 'refresh_workers'})
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(nodegroup.uuid, get_recorded_nodegroup_uuid())

    def test_refresh_does_not_return_secrets(self):
        # The response from "refresh" contains only an innocuous
        # confirmation.  Anyone can call this method, so it mustn't
        # reveal anything sensitive.
        response = self.client.post(
            reverse('nodegroups_handler'), {'op': 'refresh_workers'})
        self.assertEqual(
            (httplib.OK, "Sending worker refresh."),
            (response.status_code, response.content))


class TestNodeGroupAPI(APITestCase):

    resources = (
        ('celery', FixtureResource(CeleryFixture())),
        )

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/nodegroups/name/',
            reverse('nodegroup_handler', args=['name']))

    def test_GET_returns_node_group(self):
        nodegroup = factory.make_node_group()
        response = self.client.get(
            reverse('nodegroup_handler', args=[nodegroup.uuid]))
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            nodegroup.uuid, json.loads(response.content).get('uuid'))

    def test_GET_returns_404_for_unknown_node_group(self):
        response = self.client.get(
            reverse(
                'nodegroup_handler',
                args=[factory.make_name('nodegroup')]))
        self.assertEqual(httplib.NOT_FOUND, response.status_code)

    def test_PUT_reserved_to_admin_users(self):
        nodegroup = factory.make_node_group()
        response = self.client_put(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {'name': factory.make_name("new-name")})

        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_PUT_updates_nodegroup(self):
        # The api allows the updating of a NodeGroup.
        nodegroup = factory.make_node_group()
        self.become_admin()
        new_name = factory.make_name("new-name")
        new_cluster_name = factory.make_name("new-cluster-name")
        new_status = factory.getRandomChoice(
            NODEGROUP_STATUS_CHOICES, but_not=[nodegroup.status])
        response = self.client_put(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {
                'name': new_name,
                'cluster_name': new_cluster_name,
                'status': new_status,
            })

        self.assertEqual(httplib.OK, response.status_code, response.content)
        nodegroup = reload_object(nodegroup)
        self.assertEqual(
            (new_name, new_cluster_name, new_status),
            (nodegroup.name, nodegroup.cluster_name, nodegroup.status))

    def test_PUT_updates_nodegroup_validates_data(self):
        nodegroup, _ = factory.make_unrenamable_nodegroup_with_node()
        self.become_admin()
        new_name = factory.make_name("new-name")
        response = self.client_put(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {'name': new_name})

        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertIn(
            "Can't rename DNS zone",
            parsed_result['name'][0])

    def test_update_leases_processes_empty_leases_dict(self):
        self.patch(api_module, 'update_mac_cluster_interfaces')
        nodegroup = factory.make_node_group()
        factory.make_dhcp_lease(nodegroup=nodegroup)
        client = make_worker_client(nodegroup)
        response = client.post(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {
                'op': 'update_leases',
                'leases': json.dumps({}),
            })
        self.assertEqual(
            (httplib.OK, "Leases updated."),
            (response.status_code, response.content))
        self.assertItemsEqual(
            [], DHCPLease.objects.filter(nodegroup=nodegroup))

    def test_update_leases_stores_leases(self):
        self.patch(api_module, 'update_mac_cluster_interfaces')
        self.patch(Omshell, 'create')
        nodegroup = factory.make_node_group()
        lease = factory.make_random_leases()
        client = make_worker_client(nodegroup)
        response = client.post(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {
                'op': 'update_leases',
                'leases': json.dumps(lease),
            })
        self.assertEqual(
            (httplib.OK, "Leases updated."),
            (response.status_code, response.content))
        self.assertItemsEqual(
            lease.keys(), [
                dhcplease.ip
                for dhcplease in DHCPLease.objects.filter(nodegroup=nodegroup)
            ])

    def test_update_leases_updates_mac_interface_mappings(self):
        self.patch(
            api_module, 'update_mac_cluster_interfaces', FakeMethod())
        self.patch(Omshell, 'create')
        cluster = factory.make_node_group()
        cluster_interface = factory.make_node_group_interface(
            nodegroup=cluster)
        mac_address = factory.make_mac_address()
        leases = {
            get_random_ip_from_interface_range(cluster_interface): (
                unicode(mac_address.mac_address))
            }

        client = make_worker_client(cluster)
        response = client.post(
            reverse('nodegroup_handler', args=[cluster.uuid]),
            {
                'op': 'update_leases',
                'leases': json.dumps(leases),
            })
        self.assertEqual(
            (httplib.OK, "Leases updated."),
            (response.status_code, response.content))
        self.assertEqual(
            [(leases, cluster)],
            api_module.update_mac_cluster_interfaces.extract_args())

    def test_update_leases_does_not_add_old_leases(self):
        self.patch(api_module, 'update_mac_cluster_interfaces')
        self.patch(Omshell, 'create')
        nodegroup = factory.make_node_group()
        client = make_worker_client(nodegroup)
        self.patch(tasks, 'add_new_dhcp_host_map', FakeMethod())
        response = client.post(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {
                'op': 'update_leases',
                'leases': json.dumps(factory.make_random_leases()),
            })
        self.assertEqual(
            (httplib.OK, "Leases updated."),
            (response.status_code, response.content))
        self.assertEqual([], tasks.add_new_dhcp_host_map.calls)

    def test_worker_calls_update_leases(self):
        # In bug 1041158, the worker's upload_leases task tried to call
        # the update_leases API at the wrong URL path.  It has the right
        # path now.
        self.useFixture(
            EnvironmentVariableFixture("MAAS_URL", settings.DEFAULT_MAAS_URL))
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED)
        refresh_worker(nodegroup)
        self.patch(MAASClient, 'post', Mock())
        leases = factory.make_random_leases()
        send_leases(leases)
        nodegroup_path = reverse(
            'nodegroup_handler', args=[nodegroup.uuid])
        nodegroup_path = nodegroup_path.decode('ascii').lstrip('/')
        MAASClient.post.assert_called_once_with(
            nodegroup_path, 'update_leases', leases=json.dumps(leases))

    def test_accept_accepts_nodegroup(self):
        nodegroups = [factory.make_node_group() for i in range(3)]
        uuids = [nodegroup.uuid for nodegroup in nodegroups]
        self.become_admin()
        response = self.client.post(
            reverse('nodegroups_handler'),
            {
                'op': 'accept',
                'uuid': uuids,
            })
        self.assertEqual(
            (httplib.OK, "Nodegroup(s) accepted."),
            (response.status_code, response.content))
        self.assertThat(
            [nodegroup.status for nodegroup in
             reload_objects(NodeGroup, nodegroups)],
            AllMatch(Equals(NODEGROUP_STATUS.ACCEPTED)))

    def test_accept_reserved_to_admin(self):
        response = self.client.post(
            reverse('nodegroups_handler'),
            {
                'op': 'accept',
                'uuid': factory.getRandomString(),
            })
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_reject_rejects_nodegroup(self):
        nodegroups = [factory.make_node_group() for i in range(3)]
        uuids = [nodegroup.uuid for nodegroup in nodegroups]
        self.become_admin()
        response = self.client.post(
            reverse('nodegroups_handler'),
            {
                'op': 'reject',
                'uuid': uuids,
            })
        self.assertEqual(
            (httplib.OK, "Nodegroup(s) rejected."),
            (response.status_code, response.content))
        self.assertThat(
            [nodegroup.status for nodegroup in
             reload_objects(NodeGroup, nodegroups)],
            AllMatch(Equals(NODEGROUP_STATUS.REJECTED)))

    def test_reject_reserved_to_admin(self):
        response = self.client.post(
            reverse('nodegroups_handler'),
            {
                'op': 'reject',
                'uuid': factory.getRandomString(),
            })
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_import_boot_images_calls_script_for_all_accepted_clusters(self):
        recorder = self.patch(nodegroup_module, 'import_boot_images')
        proxy = factory.make_name('proxy')
        Config.objects.set_config('http_proxy', proxy)
        accepted_nodegroups = [
            factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED),
            factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED),
        ]
        factory.make_node_group(status=NODEGROUP_STATUS.REJECTED)
        factory.make_node_group(status=NODEGROUP_STATUS.PENDING)
        admin = factory.make_admin()
        client = OAuthAuthenticatedClient(admin)
        response = client.post(
            reverse('nodegroups_handler'), {'op': 'import_boot_images'})
        self.assertEqual(
            httplib.OK, response.status_code,
            explain_unexpected_response(httplib.OK, response))
        queues = [
            kwargs['queue']
            for args, kwargs in recorder.apply_async.call_args_list]
        self.assertItemsEqual(
            [nodegroup.work_queue for nodegroup in accepted_nodegroups],
            queues)

    def test_import_boot_images_denied_if_not_admin(self):
        user = factory.make_user()
        client = OAuthAuthenticatedClient(user)
        response = client.post(
            reverse('nodegroups_handler'), {'op': 'import_boot_images'})
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code,
            explain_unexpected_response(httplib.FORBIDDEN, response))

    def test_report_download_progress_accepts_new_download(self):
        nodegroup = factory.make_node_group()
        filename = factory.getRandomString()
        client = make_worker_client(nodegroup)

        response = client.post(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {
                'op': 'report_download_progress',
                'filename': filename,
            })
        self.assertEqual(
            httplib.OK, response.status_code,
            explain_unexpected_response(httplib.OK, response))

        progress = DownloadProgress.objects.get(nodegroup=nodegroup)
        self.assertEqual(nodegroup, progress.nodegroup)
        self.assertEqual(filename, progress.filename)
        self.assertIsNone(progress.size)
        self.assertIsNone(progress.bytes_downloaded)
        self.assertEqual('', progress.error)

    def test_report_download_progress_updates_ongoing_download(self):
        progress = factory.make_download_progress_incomplete()
        client = make_worker_client(progress.nodegroup)
        new_bytes_downloaded = progress.bytes_downloaded + 1

        response = client.post(
            reverse('nodegroup_handler', args=[progress.nodegroup.uuid]),
            {
                'op': 'report_download_progress',
                'filename': progress.filename,
                'bytes_downloaded': new_bytes_downloaded,
            })
        self.assertEqual(
            httplib.OK, response.status_code,
            explain_unexpected_response(httplib.OK, response))

        progress = reload_object(progress)
        self.assertEqual(new_bytes_downloaded, progress.bytes_downloaded)

    def test_report_download_progress_rejects_invalid_data(self):
        progress = factory.make_download_progress_incomplete()
        client = make_worker_client(progress.nodegroup)

        response = client.post(
            reverse('nodegroup_handler', args=[progress.nodegroup.uuid]),
            {
                'op': 'report_download_progress',
                'filename': progress.filename,
                'bytes_downloaded': -1,
            })
        self.assertEqual(
            httplib.BAD_REQUEST, response.status_code,
            explain_unexpected_response(httplib.BAD_REQUEST, response))

    def test_probe_and_enlist_ucsm_adds_ucsm(self):
        nodegroup = factory.make_node_group()
        url = 'http://url'
        username = factory.make_name('user')
        password = factory.make_name('password')
        self.become_admin()

        mock = self.patch(nodegroup_module, 'enlist_nodes_from_ucsm')

        response = self.client.post(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {
                'op': 'probe_and_enlist_ucsm',
                'url': url,
                'username': username,
                'password': password,
            })

        self.assertEqual(
            httplib.OK, response.status_code,
            explain_unexpected_response(httplib.OK, response))

        args = (url, username, password)
        matcher = MockCalledOnceWith(queue=nodegroup.uuid, args=args)
        self.assertThat(mock.apply_async, matcher)


class TestNodeGroupAPIAuth(MAASServerTestCase):
    """Authorization tests for nodegroup API."""

    example_lshw_details = dedent("""\
        <?xml version="1.0" standalone="yes"?>
        <list><node id="dunedin" /></list>
        """).encode("ascii")

    example_lshw_details_bin = bson.binary.Binary(example_lshw_details)

    def set_lshw_details(self, node, data):
        NodeCommissionResult.objects.store_data(
            node, commissioningscript.LSHW_OUTPUT_NAME,
            script_result=0, data=Bin(data))

    example_lldp_details = dedent("""\
        <?xml version="1.0" encoding="UTF-8"?>
        <lldp label="LLDP neighbors">%d</lldp>
        """).encode("ascii")

    example_lldp_details_bin = bson.binary.Binary(example_lldp_details)

    def set_lldp_details(self, node, data):
        NodeCommissionResult.objects.store_data(
            node, commissioningscript.LLDP_OUTPUT_NAME,
            script_result=0, data=Bin(data))

    def test_nodegroup_requires_authentication(self):
        nodegroup = factory.make_node_group()
        response = self.client.get(
            reverse('nodegroup_handler', args=[nodegroup.uuid]))
        self.assertEqual(httplib.UNAUTHORIZED, response.status_code)

    def test_update_leases_works_for_nodegroup_worker(self):
        nodegroup = factory.make_node_group()
        client = make_worker_client(nodegroup)
        response = client.post(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {'op': 'update_leases', 'leases': json.dumps({})})
        self.assertEqual(
            httplib.OK, response.status_code,
            explain_unexpected_response(httplib.OK, response))

    def test_update_leases_does_not_work_for_normal_user(self):
        nodegroup = factory.make_node_group()
        log_in_as_normal_user(self.client)
        response = self.client.post(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {'op': 'update_leases', 'leases': json.dumps({})})
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code,
            explain_unexpected_response(httplib.FORBIDDEN, response))

    def test_update_leases_does_not_let_worker_update_other_nodegroup(self):
        requesting_nodegroup = factory.make_node_group()
        about_nodegroup = factory.make_node_group()
        client = make_worker_client(requesting_nodegroup)

        response = client.post(
            reverse('nodegroup_handler', args=[about_nodegroup.uuid]),
            {'op': 'update_leases', 'leases': json.dumps({})})

        self.assertEqual(
            httplib.FORBIDDEN, response.status_code,
            explain_unexpected_response(httplib.FORBIDDEN, response))

    def test_nodegroup_list_nodes_requires_authentication(self):
        nodegroup = factory.make_node_group()
        response = self.client.get(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {'op': 'list_nodes'})
        self.assertEqual(httplib.UNAUTHORIZED, response.status_code)

    def test_nodegroup_list_nodes_does_not_work_for_normal_user(self):
        nodegroup = factory.make_node_group()
        log_in_as_normal_user(self.client)

        response = self.client.get(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {'op': 'list_nodes'})

        self.assertEqual(
            httplib.FORBIDDEN, response.status_code,
            explain_unexpected_response(httplib.FORBIDDEN, response))

    def test_nodegroup_list_nodes_works_for_nodegroup_worker(self):
        nodegroup = factory.make_node_group()
        node = factory.make_node(nodegroup=nodegroup)
        client = make_worker_client(nodegroup)

        response = client.get(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {'op': 'list_nodes'})

        self.assertEqual(
            httplib.OK, response.status_code,
            explain_unexpected_response(httplib.OK, response))
        parsed_result = json.loads(response.content)
        self.assertItemsEqual([node.system_id], parsed_result)

    def test_nodegroup_list_nodes_works_for_admin(self):
        nodegroup = factory.make_node_group()
        admin = factory.make_admin()
        client = OAuthAuthenticatedClient(admin)
        node = factory.make_node(nodegroup=nodegroup)

        response = client.get(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {'op': 'list_nodes'})

        self.assertEqual(
            httplib.OK, response.status_code,
            explain_unexpected_response(httplib.OK, response))
        parsed_result = json.loads(response.content)
        self.assertItemsEqual([node.system_id], parsed_result)

    def test_nodegroup_import_boot_images_calls_importer(self):
        recorder = self.patch(nodegroup_module, 'import_boot_images')
        self.patch(nodegroup_module, 'report_boot_images')
        proxy = factory.getRandomString()
        Config.objects.set_config('http_proxy', proxy)
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED)
        admin = factory.make_admin()
        client = OAuthAuthenticatedClient(admin)

        response = client.post(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {'op': 'import_boot_images'})

        self.assertEqual(
            httplib.OK, response.status_code,
            explain_unexpected_response(httplib.OK, response))
        self.assertThat(recorder.apply_async.mock_calls, HasLength(1))

    def test_nodegroup_import_boot_images_denied_if_not_admin(self):
        nodegroup = factory.make_node_group()
        user = factory.make_user()
        client = OAuthAuthenticatedClient(user)

        response = client.post(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {'op': 'import_boot_images'})

        self.assertEqual(
            httplib.FORBIDDEN, response.status_code,
            explain_unexpected_response(httplib.FORBIDDEN, response))

    def make_details_request(self, client, nodegroup):
        system_ids = {node.system_id for node in nodegroup.node_set.all()}
        return client.post(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {'op': 'details', 'system_ids': system_ids})

    def test_details_requires_authentication(self):
        nodegroup = factory.make_node_group()
        response = self.make_details_request(self.client, nodegroup)
        self.assertEqual(httplib.UNAUTHORIZED, response.status_code)

    def test_details_refuses_nonworker(self):
        log_in_as_normal_user(self.client)
        nodegroup = factory.make_node_group()
        response = self.make_details_request(self.client, nodegroup)
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code,
            explain_unexpected_response(httplib.FORBIDDEN, response))

    def test_details_returns_details(self):
        nodegroup = factory.make_node_group()
        node = factory.make_node(nodegroup=nodegroup)
        self.set_lshw_details(node, self.example_lshw_details)
        self.set_lldp_details(node, self.example_lldp_details)
        client = make_worker_client(nodegroup)

        response = client.post(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {'op': 'details', 'system_ids': [node.system_id]})

        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = bson.BSON(response.content).decode()
        self.assertDictEqual(
            {
                node.system_id: {
                    "lshw": self.example_lshw_details_bin,
                    "lldp": self.example_lldp_details_bin,
                },
            },
            parsed_result)

    def test_details_allows_admin(self):
        nodegroup = factory.make_node_group()
        node = factory.make_node(nodegroup=nodegroup)
        user = factory.make_admin()
        client = OAuthAuthenticatedClient(user)

        response = client.post(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {'op': 'details', 'system_ids': [node.system_id]})

        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = bson.BSON(response.content).decode()
        self.assertDictEqual(
            {
                node.system_id: {
                    "lshw": None,
                    "lldp": None,
                },
            },
            parsed_result)

    def test_empty_details(self):
        # Empty details are passed through.
        nodegroup = factory.make_node_group()
        node = factory.make_node(nodegroup=nodegroup)
        self.set_lshw_details(node, b'')
        self.set_lldp_details(node, b'')
        client = make_worker_client(nodegroup)

        response = client.post(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {'op': 'details', 'system_ids': [node.system_id]})

        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = bson.BSON(response.content).decode()
        self.assertDictEqual(
            {
                node.system_id: {
                    "lshw": bson.binary.Binary(b""),
                    "lldp": bson.binary.Binary(b""),
                },
            },
            parsed_result)

    def test_details_does_not_see_other_node_groups(self):
        nodegroup_mine = factory.make_node_group()
        nodegroup_theirs = factory.make_node_group()
        node_mine = factory.make_node(nodegroup=nodegroup_mine)
        self.set_lshw_details(node_mine, self.example_lshw_details)
        node_theirs = factory.make_node(nodegroup=nodegroup_theirs)
        self.set_lldp_details(node_theirs, self.example_lldp_details)
        client = make_worker_client(nodegroup_mine)

        response = client.post(
            reverse('nodegroup_handler', args=[nodegroup_mine.uuid]),
            {'op': 'details',
             'system_ids': [node_mine.system_id, node_theirs.system_id]})

        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = bson.BSON(response.content).decode()
        self.assertDictEqual(
            {
                node_mine.system_id: {
                    "lshw": self.example_lshw_details_bin,
                    "lldp": None,
                },
            },
            parsed_result)

    def test_details_with_no_details(self):
        # If there are no nodes, an empty map is returned.
        nodegroup = factory.make_node_group()
        client = make_worker_client(nodegroup)
        response = self.make_details_request(client, nodegroup)
        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = bson.BSON(response.content).decode()
        self.assertDictEqual({}, parsed_result)

    def test_POST_report_download_progress_works_for_nodegroup_worker(self):
        nodegroup = factory.make_node_group()
        filename = factory.getRandomString()
        client = make_worker_client(nodegroup)

        response = client.post(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {
                'op': 'report_download_progress',
                'filename': filename,
            })

        self.assertEqual(
            httplib.OK, response.status_code,
            explain_unexpected_response(httplib.OK, response))

    def test_POST_report_download_progress_does_not_work_for_normal_user(self):
        nodegroup = factory.make_node_group()
        log_in_as_normal_user(self.client)

        response = self.client.post(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {
                'op': 'report_download_progress',
                'filename': factory.getRandomString(),
            })

        self.assertEqual(
            httplib.FORBIDDEN, response.status_code,
            explain_unexpected_response(httplib.FORBIDDEN, response))

    def test_POST_report_download_progress_does_work_for_other_cluster(self):
        filename = factory.getRandomString()
        client = make_worker_client(factory.make_node_group())

        response = client.post(
            reverse(
                'nodegroup_handler', args=[factory.make_node_group().uuid]),
            {
                'op': 'report_download_progress',
                'filename': filename,
            })

        self.assertEqual(
            httplib.FORBIDDEN, response.status_code,
            explain_unexpected_response(httplib.FORBIDDEN, response))


class TestUpdateMacClusterInterfaces(MAASServerTestCase):
    """Tests for `update_mac_cluster_interfaces`()."""

    def test_updates_mac_cluster_interfaces(self):
        cluster = factory.make_node_group()
        interfaces = [
            factory.make_node_group_interface(nodegroup=cluster)
            for i in range(4)
            ]
        interfaces.append(cluster.nodegroupinterface_set.first())
        mac_addresses = {
            factory.make_mac_address(): random.choice(interfaces)
            for i in range(4)
            }
        leases = {
            get_random_ip_from_interface_range(interface): (
                mac_address.mac_address)
            for mac_address, interface in mac_addresses.items()
        }
        update_mac_cluster_interfaces(leases, cluster)
        results = {
            mac_address: mac_address.cluster_interface
            for mac_address in MACAddress.objects.filter(
                mac_address__in=leases.values())
            }
        self.assertEqual(mac_addresses, results)

    def test_ignores_mac_not_attached_to_cluster(self):
        cluster = factory.make_node_group()
        mac_address = factory.make_mac_address()
        leases = {
            factory.getRandomIPAddress(): mac_address.mac_address
            }
        update_mac_cluster_interfaces(leases, cluster)
        mac_address = MACAddress.objects.get(
            id=mac_address.id)
        self.assertIsNone(mac_address.cluster_interface)

    def test_ignores_unknown_macs(self):
        cluster = factory.make_node_group()
        mac_address = factory.getRandomMACAddress()
        leases = {
            factory.getRandomIPAddress(): mac_address
            }
        # This is a test to show that update_mac_cluster_interfaces()
        # doesn't raise an Http404 when it comes across something it
        # doesn't know, hence the lack of meaningful assertions.
        update_mac_cluster_interfaces(leases, cluster)
        self.assertFalse(
            MACAddress.objects.filter(mac_address=mac_address).exists())

    def test_ignores_unconfigured_interfaces(self):
        cluster = factory.make_node_group()
        factory.make_node_group_interface(
            nodegroup=cluster, subnet_mask='', broadcast_ip='',
            static_ip_range_low='', static_ip_range_high='',
            ip_range_low='', ip_range_high='', router_ip='',
            ip=factory.getRandomIPAddress(),
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        mac_address = factory.getRandomMACAddress()
        leases = {
            factory.getRandomIPAddress(): mac_address
            }
        self.assertIsNone(update_mac_cluster_interfaces(leases, cluster))
        # The real test is that update_mac_cluster_interfaces() doesn't
        # stacktrace because of the unconfigured interface (see bug
        # 1332596).
