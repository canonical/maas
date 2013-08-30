# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the API's `register` method."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []


import httplib
import json
from textwrap import dedent

from celery.app import app_or_default
from django.conf import settings
from django.core.urlresolvers import reverse
from django.test.client import RequestFactory
from maasserver import api
from maasserver.enum import (
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.forms import DEFAULT_ZONE_NAME
from maasserver.models import NodeGroup
from maasserver.testing.api import AnonAPITestCase
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
from maasserver.tests.test_forms import make_interface_settings
from mock import ANY
from testtools.matchers import MatchesStructure


class TestUpdateNodeGroupMAASURL(TestCase):
    """Tests for `update_nodegroup_maas_url`."""

    def make_request(self, host, script="/script", path="/script/path"):
        """Fake a GET request."""
        request_factory = RequestFactory(SCRIPT_NAME=script)
        return request_factory.get(path, SERVER_NAME=host)

    def test_update_from_request(self):
        request = self.make_request(
            "example.com", script="/script", path="/script/path")
        nodegroup = factory.make_node_group()

        api.update_nodegroup_maas_url(nodegroup, request)

        self.assertEqual("http://example.com/script", nodegroup.maas_url)

    def test_update_from_request_discarded_if_localhost(self):
        request = self.make_request("localhost")
        maas_url = factory.make_name('maas_url')
        nodegroup = factory.make_node_group(maas_url=maas_url)

        api.update_nodegroup_maas_url(nodegroup, request)

        # nodegroup.maas_url was not updated.
        self.assertEqual(maas_url, nodegroup.maas_url)


class TestRegisterAPI(AnonAPITestCase):
    """Tests for the `register` method on the API.

    This method can be called anonymously.
    """

    def create_configured_master(self):
        """Set up a master, already configured."""
        master = NodeGroup.objects.ensure_master()
        master.uuid = factory.getRandomUUID()
        master.save()

    def reset_master(self):
        """Reset to a situation where no master has been accepted."""
        master = NodeGroup.objects.ensure_master()
        master.status = NODEGROUP_STATUS.PENDING
        master.save()

    def create_local_cluster_config(self, uuid):
        """Set up a local cluster config with the given UUID.

        This patches settings.LOCAL_CLUSTER_CONFIG to point to a valid
        cluster config file.
        """
        contents = dedent("""
            MAAS_URL=http://localhost/MAAS
            CLUSTER_UUID="%s"
            """ % uuid)
        file_name = self.make_file(contents=contents)
        self.patch(settings, 'LOCAL_CLUSTER_CONFIG', file_name)

    def patch_broker_url(self):
        """Patch `BROKER_URL` with a fake.  Returns the fake value."""
        fake = factory.make_name('fake_broker_url')
        celery_conf = app_or_default().conf
        self.patch(celery_conf, 'BROKER_URL', fake)
        return fake

    def test_register_creates_nodegroup_and_interfaces(self):
        self.create_configured_master()
        name = factory.make_name('name')
        uuid = factory.getRandomUUID()
        interface = make_interface_settings()
        response = self.client.post(
            reverse('nodegroups_handler'),
            {
                'op': 'register',
                'name': name,
                'uuid': uuid,
                'interfaces': json.dumps([interface]),
            })
        nodegroup = NodeGroup.objects.get(uuid=uuid)
        # The nodegroup was created with its interface.  Its status is
        # 'PENDING'.
        self.assertEqual(
            (name, NODEGROUP_STATUS.PENDING),
            (nodegroup.name, nodegroup.status))
        self.assertThat(
            nodegroup.nodegroupinterface_set.all()[0],
            MatchesStructure.byEquality(**interface))
        # The response code is 'ACCEPTED': the nodegroup now needs to be
        # validated by an admin.
        self.assertEqual(httplib.ACCEPTED, response.status_code)

    def test_register_auto_accepts_local_master(self):
        self.reset_master()
        name = factory.make_name('nodegroup')
        uuid = factory.getRandomUUID()
        self.create_local_cluster_config(uuid)
        fake_broker_url = self.patch_broker_url()

        response = self.client.post(
            reverse('nodegroups_handler'),
            {
                'op': 'register',
                'name': name,
                'uuid': uuid,
            })
        self.assertEqual(httplib.OK, response.status_code, response)

        parsed_result = json.loads(response.content)
        self.assertEqual(
            ({'BROKER_URL': fake_broker_url}, uuid),
            (parsed_result, NodeGroup.objects.ensure_master().uuid))

        master = NodeGroup.objects.ensure_master()
        # The cluster controller that made the request is registered as the
        # master, since there was none.
        self.assertEqual((uuid, name), (master.uuid, master.name))

    def test_register_makes_first_cluster_controller_master(self):
        self.reset_master()
        name = factory.make_name('nodegroup')
        uuid = factory.getRandomUUID()
        self.create_local_cluster_config(factory.getRandomUUID())
        self.patch_broker_url()

        response = self.client.post(
            reverse('nodegroups_handler'),
            {
                'op': 'register',
                'name': name,
                'uuid': uuid,
            })
        self.assertEqual(httplib.ACCEPTED, response.status_code, response)

        self.assertEqual(
            response.content, "Cluster registered.  Awaiting admin approval.")

        master = NodeGroup.objects.ensure_master()
        # The cluster controller that made the request is registered as the
        # master, since there was none.
        self.assertEqual((uuid, name), (master.uuid, master.name))
        # However, since this cluster controller wasn't running locally, we
        # can't be sure it's not an impostor.  It's still pending approval by
        # an administrator.
        self.assertEqual(NODEGROUP_STATUS.PENDING, master.status)

    def test_register_configures_master_if_unconfigured(self):
        self.reset_master()
        name = factory.make_name('nodegroup')
        uuid = factory.getRandomUUID()
        self.create_local_cluster_config(uuid)
        interface = make_interface_settings()

        response = self.client.post(
            reverse('nodegroups_handler'),
            {
                'op': 'register',
                'name': name,
                'uuid': uuid,
                'interfaces': json.dumps([interface]),
            })
        self.assertEqual(httplib.OK, response.status_code, response)

        master = NodeGroup.objects.ensure_master()
        self.assertEqual(NODEGROUP_STATUS.ACCEPTED, master.status)
        self.assertThat(
            master.nodegroupinterface_set.get(
                interface=interface['interface']),
            MatchesStructure.byEquality(**interface))

    def test_register_nodegroup_uses_default_zone_name(self):
        uuid = factory.getRandomUUID()
        self.create_local_cluster_config(uuid)

        response = self.client.post(
            reverse('nodegroups_handler'),
            {
                'op': 'register',
                'uuid': uuid,
            })
        self.assertEqual(httplib.OK, response.status_code, response)

        master = NodeGroup.objects.ensure_master()
        self.assertEqual(
            (NODEGROUP_STATUS.ACCEPTED, DEFAULT_ZONE_NAME),
            (master.status, master.name))

    def test_register_accepts_only_one_managed_interface(self):
        self.create_configured_master()
        name = factory.make_name('name')
        uuid = factory.getRandomUUID()
        # This will try to create 2 "managed" interfaces.
        interface1 = make_interface_settings()
        interface1['management'] = NODEGROUPINTERFACE_MANAGEMENT.DHCP
        interface2 = interface1.copy()
        response = self.client.post(
            reverse('nodegroups_handler'),
            {
                'op': 'register',
                'name': name,
                'uuid': uuid,
                'interfaces': json.dumps([interface1, interface2]),
            })
        self.assertEqual(
            (
                httplib.BAD_REQUEST,
                {'interfaces':
                    [
                        "Only one managed interface can be configured for "
                        "this cluster"
                    ]},
            ),
            (response.status_code, json.loads(response.content)))

    def test_register_nodegroup_validates_data(self):
        self.create_configured_master()
        response = self.client.post(
            reverse('nodegroups_handler'),
            {
                'op': 'register',
                'name': factory.make_name('name'),
                'uuid': factory.getRandomUUID(),
                'interfaces': 'invalid data',
            })
        self.assertEqual(
            (
                httplib.BAD_REQUEST,
                {'interfaces': ['Invalid json value.']},
            ),
            (response.status_code, json.loads(response.content)))

    def test_register_nodegroup_twice_does_not_update_nodegroup(self):
        self.create_configured_master()
        nodegroup = factory.make_node_group()
        nodegroup.status = NODEGROUP_STATUS.PENDING
        nodegroup.save()
        name = factory.make_name('name')
        uuid = nodegroup.uuid
        response = self.client.post(
            reverse('nodegroups_handler'),
            {
                'op': 'register',
                'name': name,
                'uuid': uuid,
            })
        new_nodegroup = NodeGroup.objects.get(uuid=uuid)
        self.assertEqual(
            (nodegroup.name, NODEGROUP_STATUS.PENDING),
            (new_nodegroup.name, new_nodegroup.status))
        # The response code is 'ACCEPTED': the nodegroup still needs to be
        # validated by an admin.
        self.assertEqual(httplib.ACCEPTED, response.status_code)

    def test_register_rejected_nodegroup_fails(self):
        self.create_configured_master()
        nodegroup = factory.make_node_group()
        nodegroup.status = NODEGROUP_STATUS.REJECTED
        nodegroup.save()
        response = self.client.post(
            reverse('nodegroups_handler'),
            {
                'op': 'register',
                'name': factory.make_name('name'),
                'uuid': nodegroup.uuid,
                'interfaces': json.dumps([]),
            })
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_register_accepted_cluster_returns_credentials(self):
        self.create_configured_master()
        fake_broker_url = self.patch_broker_url()
        nodegroup = factory.make_node_group()
        nodegroup.status = NODEGROUP_STATUS.ACCEPTED
        nodegroup.save()
        response = self.client.post(
            reverse('nodegroups_handler'),
            {
                'op': 'register',
                'name': factory.make_name('name'),
                'uuid': nodegroup.uuid,
            })
        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertIn('application/json', response['Content-Type'])
        self.assertEqual({'BROKER_URL': fake_broker_url}, parsed_result)

    def test_register_new_nodegroup_does_not_record_maas_url(self):
        # When registering a cluster, the URL with which the call was made
        # (i.e. from the perspective of the cluster) is *not* recorded.
        self.create_configured_master()
        name = factory.make_name('name')
        uuid = factory.getRandomUUID()
        update_maas_url = self.patch(api, "update_nodegroup_maas_url")
        response = self.client.post(
            reverse('nodegroups_handler'),
            {'op': 'register', 'name': name, 'uuid': uuid})
        self.assertEqual(httplib.ACCEPTED, response.status_code, response)
        self.assertEqual([], update_maas_url.call_args_list)

    def test_register_accepted_nodegroup_updates_maas_url(self):
        # When registering an existing, accepted, cluster, the MAAS URL we give
        # it in the future is updated to the one on which the call was made.
        self.create_configured_master()
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED)
        update_maas_url = self.patch(api, "update_nodegroup_maas_url")
        response = self.client.post(
            reverse('nodegroups_handler'),
            {'op': 'register', 'uuid': nodegroup.uuid})
        self.assertEqual(httplib.OK, response.status_code, response)
        update_maas_url.assert_called_once_with(nodegroup, ANY)

    def test_register_pending_nodegroup_does_not_update_maas_url(self):
        # When registering an existing, pending cluster, the MAAS URL we give
        # it in the future is *not* updated to the one on which the call was
        # made.
        self.create_configured_master()
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.PENDING)
        update_maas_url = self.patch(api, "update_nodegroup_maas_url")
        response = self.client.post(
            reverse('nodegroups_handler'),
            {'op': 'register', 'uuid': nodegroup.uuid})
        self.assertEqual(httplib.ACCEPTED, response.status_code, response)
        self.assertEqual([], update_maas_url.call_args_list)

    def test_register_rejected_nodegroup_does_not_update_maas_url(self):
        # When registering an existing, rejected cluster, the MAAS URL we give
        # it in the future is *not* updated to the one on which the call was
        # made.
        self.create_configured_master()
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.REJECTED)
        update_maas_url = self.patch(api, "update_nodegroup_maas_url")
        response = self.client.post(
            reverse('nodegroups_handler'),
            {'op': 'register', 'uuid': nodegroup.uuid})
        self.assertEqual(httplib.FORBIDDEN, response.status_code, response)
        self.assertEqual([], update_maas_url.call_args_list)

    def test_register_master_nodegroup_does_not_update_maas_url(self):
        # When registering the master cluster, the MAAS URL we give it in
        # the future is *not* updated to the one on which the call was made.
        self.reset_master()
        name = factory.make_name('name')
        uuid = factory.getRandomUUID()
        self.create_local_cluster_config(uuid)
        update_maas_url = self.patch(api, "update_nodegroup_maas_url")
        response = self.client.post(
            reverse('nodegroups_handler'),
            {'op': 'register', 'name': name, 'uuid': uuid})
        self.assertEqual(httplib.OK, response.status_code, response)
        # This really did configure the master.
        master = NodeGroup.objects.ensure_master()
        self.assertEqual(uuid, master.uuid)
        self.assertEqual([], update_maas_url.call_args_list)
        # The master's maas_url field remains empty.
        self.assertEqual("", master.maas_url)
