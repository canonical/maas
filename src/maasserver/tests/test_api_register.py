# Copyright 2013-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the API's `register` method."""

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
from textwrap import dedent

from celery.app import app_or_default
from django.conf import settings
from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
    )
from django.core.urlresolvers import reverse
from django.test.client import RequestFactory
from maasserver import api
from maasserver.enum import NODEGROUP_STATUS
from maasserver.forms import DEFAULT_DNS_ZONE_NAME
from maasserver.models import NodeGroup
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import MockCalledOnceWith
from mock import (
    ANY,
    Mock,
    )
from testtools.matchers import MatchesStructure
from testtools.testcase import ExpectedException


class TestUpdateNodeGroupMAASURL(MAASServerTestCase):
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


def create_configured_master():
    """Set up a master, already configured."""
    master = NodeGroup.objects.ensure_master()
    master.uuid = factory.make_UUID()
    master.save()


def reset_master():
    """Reset to a situation where no master has been accepted."""
    master = NodeGroup.objects.ensure_master()
    master.status = NODEGROUP_STATUS.PENDING
    master.save()


def create_local_cluster_config(test_case, uuid):
    """Set up a local cluster config with the given UUID.

    This patches settings.LOCAL_CLUSTER_CONFIG to point to a valid
    cluster config file.
    """
    contents = dedent("""
        MAAS_URL=http://localhost/MAAS
        CLUSTER_UUID="%s"
        """ % uuid)
    file_name = test_case.make_file(contents=contents)
    test_case.patch(settings, 'LOCAL_CLUSTER_CONFIG', file_name)


def patch_broker_url(test_case):
    """Patch `BROKER_URL` with a fake.  Returns the fake value."""
    fake = factory.make_name('fake_broker_url')
    celery_conf = app_or_default().conf
    test_case.patch(celery_conf, 'BROKER_URL', fake)
    return fake


def make_register_request(uuid):
    """Create a fake register() request."""
    request = RequestFactory().post(
        reverse('nodegroups_handler'),
        {'op': 'register', 'uuid': uuid})
    # Piston sets request.data like this.  Our API code needs it.
    request.data = request.POST
    return request


class TestRegisterNodegroup(MAASServerTestCase):
    """Tests for `register_nodegroup`."""

    def test_creates_pending_nodegroup_by_default(self):
        create_configured_master()
        uuid = factory.make_UUID()
        request = make_register_request(uuid)

        nodegroup = api.register_nodegroup(request, uuid)

        self.assertEqual(uuid, nodegroup.uuid)
        self.assertEqual(NODEGROUP_STATUS.PENDING, nodegroup.status)
        self.assertNotEqual(NodeGroup.objects.ensure_master().id, nodegroup.id)

    def test_registers_as_master_if_master_not_configured(self):
        reset_master()
        uuid = factory.make_UUID()
        request = make_register_request(uuid)

        nodegroup = api.register_nodegroup(request, uuid)

        self.assertEqual(uuid, nodegroup.uuid)
        self.assertEqual(NODEGROUP_STATUS.PENDING, nodegroup.status)
        self.assertEqual(NodeGroup.objects.ensure_master().id, nodegroup.id)

    def test_updates_and_accepts_local_master_if_master_not_configured(self):
        reset_master()
        uuid = factory.make_UUID()
        create_local_cluster_config(self, uuid)
        request = make_register_request(uuid)

        nodegroup = api.register_nodegroup(request, uuid)

        self.assertEqual(uuid, nodegroup.uuid)
        self.assertEqual(NODEGROUP_STATUS.ACCEPTED, nodegroup.status)
        self.assertEqual(NodeGroup.objects.ensure_master().id, nodegroup.id)

    def test_keeps_local_cluster_controller_pending_if_master_configured(self):
        create_configured_master()
        uuid = factory.make_UUID()
        create_local_cluster_config(self, uuid)
        request = make_register_request(uuid)

        nodegroup = api.register_nodegroup(request, uuid)

        self.assertEqual(uuid, nodegroup.uuid)
        self.assertEqual(NODEGROUP_STATUS.PENDING, nodegroup.status)
        self.assertNotEqual(NodeGroup.objects.ensure_master().id, nodegroup.id)

    def test_rejects_duplicate_uuid(self):
        nodegroup = factory.make_node_group()
        request = make_register_request(nodegroup.uuid)

        self.assertRaises(
            ValidationError, api.register_nodegroup, request, nodegroup.uuid)


class TestComposeNodegroupRegisterResponse(MAASServerTestCase):
    """Tests for `compose_nodegroup_register_response`."""

    def test_returns_credentials_if_accepted(self):
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED)
        existed = factory.pick_bool()
        self.assertEqual(
            api.get_celery_credentials(),
            api.compose_nodegroup_register_response(nodegroup, existed))

    def test_credentials_contain_broker_url(self):
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED)
        broker_url = patch_broker_url(self)
        existed = factory.pick_bool()

        response = api.compose_nodegroup_register_response(nodegroup, existed)

        self.assertEqual({'BROKER_URL': broker_url}, response)

    def test_returns_forbidden_if_rejected(self):
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.REJECTED)
        already_existed = factory.pick_bool()

        with ExpectedException(PermissionDenied, "Rejected cluster."):
            api.compose_nodegroup_register_response(nodegroup, already_existed)

    def test_returns_accepted_for_new_pending_nodegroup(self):
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.PENDING)
        response = api.compose_nodegroup_register_response(
            nodegroup, already_existed=False)
        self.assertEqual(
            (httplib.ACCEPTED,
             "Cluster registered.  Awaiting admin approval."),
            (response.status_code, response.content))

    def test_returns_accepted_for_existing_pending_nodegroup(self):
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.PENDING)
        response = api.compose_nodegroup_register_response(
            nodegroup, already_existed=True)
        self.assertEqual(
            (httplib.ACCEPTED, "Awaiting admin approval."),
            (response.status_code, response.content))


class TestRegisterAPI(MAASServerTestCase):
    """Tests for the `register` method on the API.

    This method can be called anonymously.
    """

    def test_register_creates_nodegroup_and_interfaces(self):
        create_configured_master()
        name = factory.make_name('cluster')
        uuid = factory.make_UUID()
        interface = factory.get_interface_fields()
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
        # Replace empty strings with None as empty strings are converted into
        # None for fields with null=True.
        expected_result = {
            key: (value if value != '' else None)
            for key, value in interface.items()
        }
        self.assertThat(
            nodegroup.nodegroupinterface_set.all()[0],
            MatchesStructure.byEquality(**expected_result))
        # The response code is 'ACCEPTED': the nodegroup now needs to be
        # validated by an admin.
        self.assertEqual(httplib.ACCEPTED, response.status_code)

    def test_register_auto_accepts_local_master(self):
        reset_master()
        name = factory.make_name('cluster')
        uuid = factory.make_UUID()
        create_local_cluster_config(self, uuid)
        patch_broker_url(self)

        response = self.client.post(
            reverse('nodegroups_handler'),
            {
                'op': 'register',
                'name': name,
                'uuid': uuid,
            })
        self.assertEqual(httplib.OK, response.status_code, response)

        master = NodeGroup.objects.ensure_master()
        # The cluster controller that made the request is registered as the
        # master, since there was none.
        self.assertEqual((uuid, name), (master.uuid, master.name))
        # It is also auto-accepted.
        self.assertEqual(NODEGROUP_STATUS.ACCEPTED, master.status)

    def test_register_configures_master_if_unconfigured(self):
        reset_master()
        name = factory.make_name('cluster')
        uuid = factory.make_UUID()
        create_local_cluster_config(self, uuid)
        interface = factory.get_interface_fields()

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
        # Replace empty strings with None as empty strings are converted into
        # None for fields with null=True.
        expected_result = {
            key: (value if value != '' else None)
            for key, value in interface.items()
        }
        self.assertThat(
            master.nodegroupinterface_set.get(
                interface=interface['interface']),
            MatchesStructure.byEquality(**expected_result))

    def test_register_nodegroup_uses_default_zone_name(self):
        uuid = factory.make_UUID()
        create_local_cluster_config(self, uuid)

        response = self.client.post(
            reverse('nodegroups_handler'),
            {
                'op': 'register',
                'uuid': uuid,
            })
        self.assertEqual(httplib.OK, response.status_code, response)

        master = NodeGroup.objects.ensure_master()
        self.assertEqual(
            (NODEGROUP_STATUS.ACCEPTED, DEFAULT_DNS_ZONE_NAME),
            (master.status, master.name))

    def test_register_nodegroup_validates_data(self):
        create_configured_master()
        response = self.client.post(
            reverse('nodegroups_handler'),
            {
                'op': 'register',
                'name': factory.make_name('cluster'),
                'uuid': factory.make_UUID(),
                'interfaces': 'invalid data',
            })
        self.assertEqual(
            (
                httplib.BAD_REQUEST,
                {'interfaces': ['Invalid json value.']},
            ),
            (response.status_code, json.loads(response.content)))

    def test_register_nodegroup_twice_does_not_update_nodegroup(self):
        create_configured_master()
        nodegroup = factory.make_node_group()
        nodegroup.status = NODEGROUP_STATUS.PENDING
        nodegroup.save()
        name = factory.make_name('cluster')
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

    def test_register_returns_compose_nodegroup_register_response(self):
        # register() returns whatever compose_nodegroup_register_response()
        # tells it to return.
        expected_response = factory.getRandomString()
        self.patch(
            api, 'compose_nodegroup_register_response',
            Mock(return_value=expected_response))

        response = self.client.post(
            reverse('nodegroups_handler'),
            {
                'op': 'register',
                'name': factory.make_name('cluster'),
                'uuid': factory.make_UUID(),
            })

        self.assertIn('application/json', response['Content-Type'])
        self.assertEqual(expected_response, json.loads(response.content))

    def test_register_new_nodegroup_does_not_record_maas_url(self):
        # When registering a cluster, the URL with which the call was made
        # (i.e. from the perspective of the cluster) is *not* recorded.
        create_configured_master()
        name = factory.make_name('cluster')
        uuid = factory.make_UUID()
        update_maas_url = self.patch(api, "update_nodegroup_maas_url")
        response = self.client.post(
            reverse('nodegroups_handler'),
            {'op': 'register', 'name': name, 'uuid': uuid})
        self.assertEqual(httplib.ACCEPTED, response.status_code, response)
        self.assertEqual([], update_maas_url.call_args_list)

    def test_register_accepted_nodegroup_updates_maas_url(self):
        # When registering an existing, accepted, cluster, the MAAS URL we give
        # it in the future is updated to the one on which the call was made.
        create_configured_master()
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED)
        update_maas_url = self.patch(api, "update_nodegroup_maas_url")
        response = self.client.post(
            reverse('nodegroups_handler'),
            {'op': 'register', 'uuid': nodegroup.uuid})
        self.assertEqual(httplib.OK, response.status_code, response)
        self.assertThat(update_maas_url, MockCalledOnceWith(nodegroup, ANY))

    def test_register_pending_nodegroup_does_not_update_maas_url(self):
        # When registering an existing, pending cluster, the MAAS URL we give
        # it in the future is *not* updated to the one on which the call was
        # made.
        create_configured_master()
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
        create_configured_master()
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
        reset_master()
        name = factory.make_name('cluster')
        uuid = factory.make_UUID()
        create_local_cluster_config(self, uuid)
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
