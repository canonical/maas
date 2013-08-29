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
from maasserver import api
from maasserver.enum import (
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.forms import DEFAULT_ZONE_NAME
from maasserver.models import NodeGroup
from maasserver.testing.api import AnonAPITestCase
from maasserver.testing.factory import factory
from maasserver.tests.test_forms import make_interface_settings
from mock import ANY
from testtools.matchers import (
    Annotate,
    Contains,
    MatchesStructure,
    )


class TestRegisterAPI(AnonAPITestCase):
    """Tests for the `register` method on the API.

    This method can be called anonymously.
    """

    def create_configured_master(self):
        master = NodeGroup.objects.ensure_master()
        master.uuid = factory.getRandomUUID()
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

    def test_register_configures_master_on_first_local_call(self):
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

    def test_register_does_not_configure_master_on_nonlocal_call(self):
        name = factory.make_name('name')
        uuid = factory.getRandomUUID()
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

    def test_register_configures_master_if_unconfigured(self):
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

    def test_register_multiple_nodegroups(self):
        uuids = {factory.getRandomUUID() for counter in range(3)}
        for uuid in uuids:
            response = self.client.post(
                reverse('nodegroups_handler'),
                {
                    'op': 'register',
                    'uuid': uuid,
                })
            self.assertEqual(httplib.ACCEPTED, response.status_code, response)

        self.assertSetEqual(
            uuids,
            set(NodeGroup.objects.values_list('uuid', flat=True)))

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

    def assertSuccess(self, response):
        """Assert that `response` was successful (i.e. HTTP 2xx)."""
        self.assertThat(
            {code for code in httplib.responses if code // 100 == 2},
            Annotate(response, Contains(response.status_code)))

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
        self.assertSuccess(response)
        self.assertEqual([], update_maas_url.call_args_list)

    def test_register_accepted_nodegroup_updates_maas_url(self):
        # When registering an existing, accepted, cluster, the URL with which
        # the call was made is updated.
        self.create_configured_master()
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED)
        update_maas_url = self.patch(api, "update_nodegroup_maas_url")
        response = self.client.post(
            reverse('nodegroups_handler'),
            {'op': 'register', 'uuid': nodegroup.uuid})
        self.assertSuccess(response)
        update_maas_url.assert_called_once_with(nodegroup, ANY)

    def test_register_pending_nodegroup_does_not_update_maas_url(self):
        # When registering an existing, pending, cluster, the URL with which
        # the call was made is *not* updated.
        self.create_configured_master()
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.PENDING)
        update_maas_url = self.patch(api, "update_nodegroup_maas_url")
        response = self.client.post(
            reverse('nodegroups_handler'),
            {'op': 'register', 'uuid': nodegroup.uuid})
        self.assertSuccess(response)
        self.assertEqual([], update_maas_url.call_args_list)

    def test_register_rejected_nodegroup_does_not_update_maas_url(self):
        # When registering an existing, pending, cluster, the URL with which
        # the call was made is *not* updated.
        self.create_configured_master()
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.REJECTED)
        update_maas_url = self.patch(api, "update_nodegroup_maas_url")
        response = self.client.post(
            reverse('nodegroups_handler'),
            {'op': 'register', 'uuid': nodegroup.uuid})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)
        self.assertEqual([], update_maas_url.call_args_list)

    def test_register_master_nodegroup_does_not_update_maas_url(self):
        # When registering the master cluster, the URL with which the call was
        # made is *not* updated.
        name = factory.make_name('name')
        update_maas_url = self.patch(api, "update_nodegroup_maas_url")
        response = self.client.post(
            reverse('nodegroups_handler'),
            {'op': 'register', 'name': name, 'uuid': 'master'})
        self.assertSuccess(response)
        self.assertEqual([], update_maas_url.call_args_list)
        # The new node group's maas_url field remains empty.
        nodegroup = NodeGroup.objects.get(uuid='master')
        self.assertEqual("", nodegroup.maas_url)
