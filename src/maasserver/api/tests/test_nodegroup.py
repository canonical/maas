# Copyright 2013-2015 Canonical Ltd.  This software is licensed under the
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
from urlparse import urlparse

import bson
from django.contrib.auth.models import AnonymousUser
from django.core.urlresolvers import reverse
from maasserver.bootresources import get_simplestream_endpoint
from maasserver.enum import (
    NODEGROUP_STATUS,
    NODEGROUP_STATUS_CHOICES,
)
from maasserver.models import (
    Config,
    DownloadProgress,
    NodeGroup,
    nodegroup as nodegroup_module,
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
from maasserver.testing.orm import (
    reload_object,
    reload_objects,
)
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import MockCalledOnceWith
from metadataserver.enum import RESULT_TYPE
from metadataserver.fields import Bin
from metadataserver.models import (
    commissioningscript,
    NodeResult,
)
from mock import Mock
from provisioningserver.rpc.cluster import (
    AddSeaMicro15k,
    AddVirsh,
    AddVMware,
    EnlistNodesFromMicrosoftOCS,
    EnlistNodesFromMSCM,
    EnlistNodesFromUCSM,
    ImportBootImages,
)
from testtools.matchers import (
    AllMatch,
    Equals,
)


class TestNodeGroupsAPI(MultipleUsersScenarios,
                        MAASServerTestCase):
    scenarios = [
        ('anon', dict(userfactory=lambda: AnonymousUser())),
        ('user', dict(userfactory=factory.make_User)),
        ('admin', dict(userfactory=factory.make_admin)),
        ]

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/nodegroups/', reverse('nodegroups_handler'))

    def test_reverse_points_to_nodegroups_api(self):
        self.assertEqual(
            reverse('nodegroups_handler'), reverse('nodegroups_handler'))

    def test_nodegroups_index_lists_nodegroups(self):
        # The nodegroups index lists node groups for the MAAS.
        nodegroup = factory.make_NodeGroup()
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


class TestNodeGroupAPI(APITestCase):

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/nodegroups/name/',
            reverse('nodegroup_handler', args=['name']))

    def test_GET_returns_node_group(self):
        nodegroup = factory.make_NodeGroup()
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
        nodegroup = factory.make_NodeGroup()
        response = self.client.put(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {'name': factory.make_name("new-name")})

        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_PUT_updates_nodegroup(self):
        # The api allows the updating of a NodeGroup.
        old_disable_ipv4 = factory.pick_bool()
        nodegroup = factory.make_NodeGroup(
            default_disable_ipv4=old_disable_ipv4)
        self.become_admin()
        new_name = factory.make_name("new-name")
        new_cluster_name = factory.make_name("new-cluster-name")
        new_status = factory.pick_choice(
            NODEGROUP_STATUS_CHOICES, but_not=[nodegroup.status])
        response = self.client.put(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {
                'name': new_name,
                'cluster_name': new_cluster_name,
                'status': new_status,
                'default_disable_ipv4': not old_disable_ipv4,
            })

        self.assertEqual(httplib.OK, response.status_code, response.content)
        nodegroup = reload_object(nodegroup)
        self.assertEqual(
            (new_name, new_cluster_name, new_status),
            (nodegroup.name, nodegroup.cluster_name, nodegroup.status))
        self.assertEqual(not old_disable_ipv4, nodegroup.default_disable_ipv4)

    def test_PUT_updates_nodegroup_validates_data(self):
        nodegroup, _ = factory.make_unrenamable_NodeGroup_with_Node()
        self.become_admin()
        new_name = factory.make_name("new-name")
        response = self.client.put(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {'name': new_name})

        parsed_result = json.loads(response.content)

        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertIn(
            "Can't rename DNS zone",
            parsed_result['name'][0])

    def test_PUT_without_default_disable_ipv4_leaves_field_unchanged(self):
        old_value = factory.pick_bool()
        nodegroup = factory.make_NodeGroup(default_disable_ipv4=old_value)
        self.become_admin()
        response = self.client.put(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {'name': nodegroup.name})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        self.assertEqual(
            old_value,
            reload_object(nodegroup).default_disable_ipv4)

    def test_accept_accepts_nodegroup(self):
        nodegroups = [factory.make_NodeGroup() for _ in range(3)]
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
            AllMatch(Equals(NODEGROUP_STATUS.ENABLED)))

    def test_accept_reserved_to_admin(self):
        response = self.client.post(
            reverse('nodegroups_handler'),
            {
                'op': 'accept',
                'uuid': factory.make_string(),
            })
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_reject_rejects_nodegroup(self):
        nodegroups = [factory.make_NodeGroup() for _ in range(3)]
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
            AllMatch(Equals(NODEGROUP_STATUS.DISABLED)))

    def test_reject_reserved_to_admin(self):
        response = self.client.post(
            reverse('nodegroups_handler'),
            {
                'op': 'reject',
                'uuid': factory.make_string(),
            })
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_import_boot_images_for_all_accepted_clusters(self):
        # Patch out the is_connected method of NodeGroup so as to avoid
        # extra calls to getClient()
        self.patch(nodegroup_module.NodeGroup, 'is_connected')
        self.become_admin()
        mock_getClientFor = self.patch(nodegroup_module, 'getClientFor')
        accepted_nodegroups = [
            factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED),
            factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED),
        ]
        factory.make_NodeGroup(status=NODEGROUP_STATUS.DISABLED)
        factory.make_NodeGroup(status=NODEGROUP_STATUS.DISABLED)
        response = self.client.post(
            reverse('nodegroups_handler'), {'op': 'import_boot_images'})
        self.assertEqual(
            httplib.OK, response.status_code,
            explain_unexpected_response(httplib.OK, response))
        expected_uuids = [
            nodegroup.uuid
            for nodegroup in accepted_nodegroups
            ]
        called_uuids = [
            client_call[0][0]
            for client_call in mock_getClientFor.call_args_list
            ]
        self.assertItemsEqual(expected_uuids, called_uuids)

    def test_import_boot_images_denied_if_not_admin(self):
        user = factory.make_User()
        client = OAuthAuthenticatedClient(user)
        response = client.post(
            reverse('nodegroups_handler'), {'op': 'import_boot_images'})
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code,
            explain_unexpected_response(httplib.FORBIDDEN, response))

    def test_report_download_progress_accepts_new_download(self):
        nodegroup = factory.make_NodeGroup()
        filename = factory.make_string()
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
        progress = factory.make_DownloadProgress_incomplete()
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
        progress = factory.make_DownloadProgress_incomplete()
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

    def test_probe_and_enlist_hardware_adds_seamicro(self):
        self.become_admin()
        user = self.logged_in_user
        nodegroup = factory.make_NodeGroup()
        model = 'seamicro15k'
        mac = factory.make_mac_address()
        username = factory.make_name('username')
        password = factory.make_name('password')
        power_control = random.choice(
            ['ipmi', 'restapi', 'restapi2'])
        accept_all = 'True'

        getClientFor = self.patch(nodegroup_module, 'getClientFor')
        client = getClientFor.return_value
        nodegroup = factory.make_NodeGroup()

        response = self.client.post(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {
                'op': 'probe_and_enlist_hardware',
                'model': model,
                'mac': mac,
                'username': username,
                'password': password,
                'power_control': power_control,
                'accept_all': accept_all,
            })

        self.assertEqual(
            httplib.OK, response.status_code,
            explain_unexpected_response(httplib.OK, response))

        self.expectThat(
            client,
            MockCalledOnceWith(
                AddSeaMicro15k, user=user.username, mac=mac,
                username=username, password=password,
                power_control=power_control, accept_all=True))

    def test_probe_and_enlist_hardware_adds_virsh(self):
        self.become_admin()
        user = self.logged_in_user
        nodegroup = factory.make_NodeGroup()
        model = 'virsh'
        poweraddr = factory.make_ipv4_address()
        password = factory.make_name('password')
        prefix_filter = factory.make_name('filter')
        accept_all = 'True'

        getClientFor = self.patch(nodegroup_module, 'getClientFor')
        client = getClientFor.return_value
        nodegroup = factory.make_NodeGroup()

        response = self.client.post(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {
                'op': 'probe_and_enlist_hardware',
                'model': model,
                'power_address': poweraddr,
                'power_pass': password,
                'prefix_filter': prefix_filter,
                'accept_all': accept_all,
            })

        self.assertEqual(
            httplib.OK, response.status_code,
            explain_unexpected_response(httplib.OK, response))

        self.expectThat(
            client,
            MockCalledOnceWith(
                AddVirsh, user=user.username, poweraddr=poweraddr,
                password=password, prefix_filter=prefix_filter,
                accept_all=True))

    def test_probe_and_enlist_hardware_adds_vmware(self):
        self.become_admin()
        user = self.logged_in_user
        nodegroup = factory.make_NodeGroup()
        model = 'vmware'
        host = factory.make_ipv4_address()
        username = factory.make_username()
        password = factory.make_name('password')
        prefix_filter = factory.make_name('filter')
        accept_all = 'True'

        getClientFor = self.patch(nodegroup_module, 'getClientFor')
        client = getClientFor.return_value
        nodegroup = factory.make_NodeGroup()

        response = self.client.post(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {
                'op': 'probe_and_enlist_hardware',
                'model': model,
                'host': host,
                'username': username,
                'password': password,
                'prefix_filter': prefix_filter,
                'accept_all': accept_all,
            })

        self.assertEqual(
            httplib.OK, response.status_code,
            explain_unexpected_response(httplib.OK, response))

        self.expectThat(
            client,
            MockCalledOnceWith(
                AddVMware, user=user.username, host=host,
                username=username, password=password, protocol=None,
                port=None, prefix_filter=prefix_filter,
                accept_all=True))

    def test_probe_and_enlist_hardware_adds_msftocs(self):
        self.become_admin()
        user = self.logged_in_user
        nodegroup = factory.make_NodeGroup()
        model = 'msftocs'
        ip = factory.make_ipv4_address()
        port = '%d ' % random.randint(2000, 4000)
        username = factory.make_name('username')
        password = factory.make_name('password')
        accept_all = 'True'

        getClientFor = self.patch(nodegroup_module, 'getClientFor')
        rpc_client = getClientFor.return_value
        nodegroup = factory.make_NodeGroup()

        response = self.client.post(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {
                'op': 'probe_and_enlist_hardware',
                'model': model,
                'ip': ip,
                'port': port,
                'username': username,
                'password': password,
                'accept_all': accept_all,
            })

        self.assertEqual(
            httplib.OK, response.status_code,
            explain_unexpected_response(httplib.OK, response))

        self.expectThat(
            rpc_client,
            MockCalledOnceWith(
                EnlistNodesFromMicrosoftOCS, user=user.username, ip=ip,
                port=port, username=username, password=password,
                accept_all=True))


class TestNodeGroupAPIForUCSM(APITestCase):

    scenarios = [
        ('deprecated', {'endpoint': 'probe_and_enlist_ucsm'}),
        ('unified', {'endpoint': 'probe_and_enlist_hardware'}),
    ]

    def test_probe_and_enlist_ucsm_adds_ucsm(self):
        self.become_admin()
        user = self.logged_in_user
        url = 'http://url'
        username = factory.make_name('user')
        password = factory.make_name('password')
        accept_all = 'True'

        getClientFor = self.patch(nodegroup_module, 'getClientFor')
        client = getClientFor.return_value
        nodegroup = factory.make_NodeGroup()

        response = self.client.post(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {
                'op': self.endpoint,
                # The deprecated version of the API doesn't need the
                # 'model' key, but it will simply be ignored.
                'model': 'ucsm',
                'url': url,
                'username': username,
                'password': password,
                'accept_all': accept_all,
            })

        self.assertEqual(
            httplib.OK, response.status_code,
            explain_unexpected_response(httplib.OK, response))

        self.expectThat(
            client,
            MockCalledOnceWith(
                EnlistNodesFromUCSM, user=user.username, url=url,
                username=username, password=password, accept_all=True))


class TestNodeGroupAPIForMSCM(APITestCase):

    scenarios = [
        ('deprecated', {'endpoint': 'probe_and_enlist_mscm'}),
        ('unified', {'endpoint': 'probe_and_enlist_hardware'}),
    ]

    def test_probe_and_enlist_mscm_adds_mscm(self):
        self.become_admin()
        user = self.logged_in_user
        nodegroup = factory.make_NodeGroup()
        host = 'http://host'
        username = factory.make_name('user')
        password = factory.make_name('password')
        accept_all = 'True'

        getClientFor = self.patch(nodegroup_module, 'getClientFor')
        client = getClientFor.return_value

        response = self.client.post(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {
                'op': self.endpoint,
                # The deprecated version of the API doesn't need the
                # 'model' key, but it will simply be ignored.
                'model': 'mcsm',
                'host': host,
                'username': username,
                'password': password,
                'accept_all': accept_all,
            })

        self.assertEqual(
            httplib.OK, response.status_code,
            explain_unexpected_response(httplib.OK, response))

        self.expectThat(
            client,
            MockCalledOnceWith(
                EnlistNodesFromMSCM, user=user.username, host=host,
                username=username, password=password, accept_all=True))


class TestNodeGroupAPIAuth(MAASServerTestCase):
    """Authorization tests for nodegroup API."""

    example_lshw_details = dedent("""\
        <?xml version="1.0" standalone="yes"?>
        <list><node id="dunedin" /></list>
        """).encode("ascii")

    example_lshw_details_bin = bson.binary.Binary(example_lshw_details)

    def set_lshw_details(self, node, data):
        NodeResult.objects.store_data(
            node, commissioningscript.LSHW_OUTPUT_NAME,
            script_result=0, result_type=RESULT_TYPE.COMMISSIONING,
            data=Bin(data))

    example_lldp_details = dedent("""\
        <?xml version="1.0" encoding="UTF-8"?>
        <lldp label="LLDP neighbors">%d</lldp>
        """).encode("ascii")

    example_lldp_details_bin = bson.binary.Binary(example_lldp_details)

    def set_lldp_details(self, node, data):
        NodeResult.objects.store_data(
            node, commissioningscript.LLDP_OUTPUT_NAME,
            script_result=0, result_type=RESULT_TYPE.COMMISSIONING,
            data=Bin(data))

    def test_nodegroup_requires_authentication(self):
        nodegroup = factory.make_NodeGroup()
        response = self.client.get(
            reverse('nodegroup_handler', args=[nodegroup.uuid]))
        self.assertEqual(httplib.UNAUTHORIZED, response.status_code)

    def test_nodegroup_list_nodes_requires_authentication(self):
        nodegroup = factory.make_NodeGroup()
        response = self.client.get(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {'op': 'list_nodes'})
        self.assertEqual(httplib.UNAUTHORIZED, response.status_code)

    def test_nodegroup_list_nodes_does_not_work_for_normal_user(self):
        nodegroup = factory.make_NodeGroup()
        log_in_as_normal_user(self.client)

        response = self.client.get(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {'op': 'list_nodes'})

        self.assertEqual(
            httplib.FORBIDDEN, response.status_code,
            explain_unexpected_response(httplib.FORBIDDEN, response))

    def test_nodegroup_list_nodes_works_for_nodegroup_worker(self):
        nodegroup = factory.make_NodeGroup()
        node = factory.make_Node(nodegroup=nodegroup)
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
        nodegroup = factory.make_NodeGroup()
        admin = factory.make_admin()
        client = OAuthAuthenticatedClient(admin)
        node = factory.make_Node(nodegroup=nodegroup)

        response = client.get(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {'op': 'list_nodes'})

        self.assertEqual(
            httplib.OK, response.status_code,
            explain_unexpected_response(httplib.OK, response))
        parsed_result = json.loads(response.content)
        self.assertItemsEqual([node.system_id], parsed_result)

    def test_nodegroup_import_boot_images_calls_ImportBootImages(self):
        proxy = 'http://%s.example.com' % factory.make_name('proxy')
        Config.objects.set_config('http_proxy', proxy)
        sources = [get_simplestream_endpoint()]
        fake_client = Mock()
        mock_getClientFor = self.patch(nodegroup_module, 'getClientFor')
        mock_getClientFor.return_value = fake_client
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)

        admin = factory.make_admin()
        client = OAuthAuthenticatedClient(admin)
        response = client.post(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {'op': 'import_boot_images'})
        self.assertEqual(
            httplib.OK, response.status_code,
            explain_unexpected_response(httplib.OK, response))
        self.assertThat(
            fake_client,
            MockCalledOnceWith(
                ImportBootImages, sources=sources,
                http_proxy=urlparse(proxy), https_proxy=urlparse(proxy)))

    def test_nodegroup_import_boot_images_denied_if_not_admin(self):
        nodegroup = factory.make_NodeGroup()
        user = factory.make_User()
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
        nodegroup = factory.make_NodeGroup()
        response = self.make_details_request(self.client, nodegroup)
        self.assertEqual(httplib.UNAUTHORIZED, response.status_code)

    def test_details_refuses_nonworker(self):
        log_in_as_normal_user(self.client)
        nodegroup = factory.make_NodeGroup()
        response = self.make_details_request(self.client, nodegroup)
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code,
            explain_unexpected_response(httplib.FORBIDDEN, response))

    def test_details_returns_details(self):
        nodegroup = factory.make_NodeGroup()
        node = factory.make_Node(nodegroup=nodegroup)
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
        nodegroup = factory.make_NodeGroup()
        node = factory.make_Node(nodegroup=nodegroup)
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
        nodegroup = factory.make_NodeGroup()
        node = factory.make_Node(nodegroup=nodegroup)
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
        nodegroup_mine = factory.make_NodeGroup()
        nodegroup_theirs = factory.make_NodeGroup()
        node_mine = factory.make_Node(nodegroup=nodegroup_mine)
        self.set_lshw_details(node_mine, self.example_lshw_details)
        node_theirs = factory.make_Node(nodegroup=nodegroup_theirs)
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
        nodegroup = factory.make_NodeGroup()
        client = make_worker_client(nodegroup)
        response = self.make_details_request(client, nodegroup)
        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = bson.BSON(response.content).decode()
        self.assertDictEqual({}, parsed_result)

    def test_POST_report_download_progress_works_for_nodegroup_worker(self):
        nodegroup = factory.make_NodeGroup()
        filename = factory.make_string()
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
        nodegroup = factory.make_NodeGroup()
        log_in_as_normal_user(self.client)

        response = self.client.post(
            reverse('nodegroup_handler', args=[nodegroup.uuid]),
            {
                'op': 'report_download_progress',
                'filename': factory.make_string(),
            })

        self.assertEqual(
            httplib.FORBIDDEN, response.status_code,
            explain_unexpected_response(httplib.FORBIDDEN, response))

    def test_POST_report_download_progress_does_work_for_other_cluster(self):
        filename = factory.make_string()
        client = make_worker_client(factory.make_NodeGroup())

        response = client.post(
            reverse(
                'nodegroup_handler', args=[factory.make_NodeGroup().uuid]),
            {
                'op': 'report_download_progress',
                'filename': filename,
            })

        self.assertEqual(
            httplib.FORBIDDEN, response.status_code,
            explain_unexpected_response(httplib.FORBIDDEN, response))
