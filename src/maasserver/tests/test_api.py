# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver API."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from functools import partial
import httplib
from itertools import izip
import json

from apiclient.maas_client import MAASClient
from django.conf import settings
from django.core.urlresolvers import reverse
from fixtures import EnvironmentVariableFixture
from maasserver import api
from maasserver.api import (
    DISPLAYED_NODEGROUPINTERFACE_FIELDS,
    store_node_power_parameters,
    )
from maasserver.enum import (
    COMPONENT,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.exceptions import MAASAPIBadRequest
from maasserver.forms_settings import INVALID_SETTING_MSG_TEMPLATE
from maasserver.models import (
    BootImage,
    Config,
    NodeGroup,
    NodeGroupInterface,
    SSHKey,
    )
from maasserver.models.user import get_auth_tokens
from maasserver.refresh_worker import refresh_worker
from maasserver.testing import (
    get_data,
    reload_object,
    )
from maasserver.testing.api import (
    APITestCase,
    log_in_as_normal_user,
    make_worker_client,
    )
from maasserver.testing.factory import factory
from maasserver.testing.oauthclient import OAuthAuthenticatedClient
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.tests.test_forms import make_interface_settings
from maasserver.utils.orm import get_one
from maastesting.celery import CeleryFixture
from maastesting.djangotestcase import TransactionTestCase
from mock import (
    ANY,
    Mock,
    )
from provisioningserver import (
    boot_images,
    tasks,
    )
from provisioningserver.enum import (
    POWER_TYPE,
    POWER_TYPE_CHOICES,
    )
from provisioningserver.pxe import tftppath
from provisioningserver.testing.boot_images import make_boot_image_params
from testresources import FixtureResource
from testtools.matchers import (
    Contains,
    Equals,
    MatchesListwise,
    MatchesStructure,
    )


class TestAuthentication(MAASServerTestCase):
    """Tests for `maasserver.api_auth`."""

    def test_invalid_oauth_request(self):
        # An OAuth-signed request that does not validate is an error.
        user = factory.make_user()
        client = OAuthAuthenticatedClient(user)
        get_auth_tokens(user).delete()  # Delete the user's API keys.
        response = client.post(reverse('nodes_handler'), {'op': 'start'})
        observed = response.status_code, response.content
        expected = (
            Equals(httplib.UNAUTHORIZED),
            Contains("Invalid access token:"),
            )
        self.assertThat(observed, MatchesListwise(expected))


class TestStoreNodeParameters(MAASServerTestCase):
    """Tests for `store_node_power_parameters`."""

    def setUp(self):
        super(TestStoreNodeParameters, self).setUp()
        self.node = factory.make_node()
        self.save = self.patch(self.node, "save")
        self.request = Mock()

    def test_power_type_not_given(self):
        # When power_type is not specified, nothing happens.
        self.request.POST = {}
        store_node_power_parameters(self.node, self.request)
        self.assertEqual(POWER_TYPE.DEFAULT, self.node.power_type)
        self.assertEqual("", self.node.power_parameters)
        self.save.assert_has_calls([])

    def test_power_type_set_but_no_parameters(self):
        # When power_type is valid, it is set. However, if power_parameters is
        # not specified, the node's power_parameters is left alone, and the
        # node is saved.
        power_type = factory.getRandomChoice(POWER_TYPE_CHOICES)
        self.request.POST = {"power_type": power_type}
        store_node_power_parameters(self.node, self.request)
        self.assertEqual(power_type, self.node.power_type)
        self.assertEqual("", self.node.power_parameters)
        self.save.assert_called_once_with()

    def test_power_type_set_with_parameters(self):
        # When power_type is valid, and power_parameters is valid JSON, both
        # fields are set on the node, and the node is saved.
        power_type = factory.getRandomChoice(POWER_TYPE_CHOICES)
        power_parameters = {"foo": [1, 2, 3]}
        self.request.POST = {
            "power_type": power_type,
            "power_parameters": json.dumps(power_parameters),
            }
        store_node_power_parameters(self.node, self.request)
        self.assertEqual(power_type, self.node.power_type)
        self.assertEqual(power_parameters, self.node.power_parameters)
        self.save.assert_called_once_with()

    def test_power_type_set_with_invalid_parameters(self):
        # When power_type is valid, but power_parameters is invalid JSON, the
        # node is not saved, and an exception is raised.
        power_type = factory.getRandomChoice(POWER_TYPE_CHOICES)
        self.request.POST = {
            "power_type": power_type,
            "power_parameters": "Not JSON.",
            }
        self.assertRaises(
            MAASAPIBadRequest, store_node_power_parameters,
            self.node, self.request)
        self.save.assert_has_calls([])

    def test_invalid_power_type(self):
        # When power_type is invalid, the node is not saved, and an exception
        # is raised.
        self.request.POST = {"power_type": factory.make_name("bogus")}
        self.assertRaises(
            MAASAPIBadRequest, store_node_power_parameters,
            self.node, self.request)
        self.save.assert_has_calls([])


class AccountAPITest(APITestCase):

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/account/', reverse('account_handler'))

    def test_create_authorisation_token(self):
        # The api operation create_authorisation_token returns a json dict
        # with the consumer_key, the token_key and the token_secret in it.
        response = self.client.post(
            reverse('account_handler'), {'op': 'create_authorisation_token'})
        parsed_result = json.loads(response.content)

        self.assertEqual(
            ['consumer_key', 'token_key', 'token_secret'],
            sorted(parsed_result))
        self.assertIsInstance(parsed_result['consumer_key'], unicode)
        self.assertIsInstance(parsed_result['token_key'], unicode)
        self.assertIsInstance(parsed_result['token_secret'], unicode)

    def test_delete_authorisation_token_not_found(self):
        # If the provided token_key does not exist (for the currently
        # logged-in user), the api returns a 'Not Found' (404) error.
        response = self.client.post(
            reverse('account_handler'),
            {'op': 'delete_authorisation_token', 'token_key': 'no-such-token'})

        self.assertEqual(httplib.NOT_FOUND, response.status_code)

    def test_delete_authorisation_token_bad_request_no_token(self):
        # token_key is a mandatory parameter when calling
        # delete_authorisation_token. It it is not present in the request's
        # parameters, the api returns a 'Bad Request' (400) error.
        response = self.client.post(
            reverse('account_handler'), {'op': 'delete_authorisation_token'})

        self.assertEqual(httplib.BAD_REQUEST, response.status_code)


class TestSSHKeyHandlers(APITestCase):

    def test_sshkeys_handler_path(self):
        self.assertEqual(
            '/api/1.0/account/prefs/sshkeys/', reverse('sshkeys_handler'))

    def test_sshkey_handler_path(self):
        self.assertEqual(
            '/api/1.0/account/prefs/sshkeys/key/',
            reverse('sshkey_handler', args=['key']))

    def test_list_works(self):
        _, keys = factory.make_user_with_keys(user=self.logged_in_user)
        params = dict(op="list")
        response = self.client.get(
            reverse('sshkeys_handler'), params)
        self.assertEqual(httplib.OK, response.status_code, response)
        parsed_result = json.loads(response.content)
        expected_result = [
            dict(
                id=keys[0].id,
                key=keys[0].key,
                resource_uri=reverse('sshkey_handler', args=[keys[0].id]),
                ),
            dict(
                id=keys[1].id,
                key=keys[1].key,
                resource_uri=reverse('sshkey_handler', args=[keys[1].id]),
                ),
            ]
        self.assertEqual(expected_result, parsed_result)

    def test_get_by_id_works(self):
        _, keys = factory.make_user_with_keys(
            n_keys=1, user=self.logged_in_user)
        key = keys[0]
        response = self.client.get(
            reverse('sshkey_handler', args=[key.id]))
        self.assertEqual(httplib.OK, response.status_code, response)
        parsed_result = json.loads(response.content)
        expected = dict(
            id=key.id,
            key=key.key,
            resource_uri=reverse('sshkey_handler', args=[key.id]),
            )
        self.assertEqual(expected, parsed_result)

    def test_delete_by_id_works(self):
        _, keys = factory.make_user_with_keys(
            n_keys=2, user=self.logged_in_user)
        response = self.client.delete(
            reverse('sshkey_handler', args=[keys[0].id]))
        self.assertEqual(httplib.NO_CONTENT, response.status_code, response)
        keys_after = SSHKey.objects.filter(user=self.logged_in_user)
        self.assertEqual(1, len(keys_after))
        self.assertEqual(keys[1].id, keys_after[0].id)

    def test_delete_fails_if_not_your_key(self):
        user, keys = factory.make_user_with_keys(n_keys=1)
        response = self.client.delete(
            reverse('sshkey_handler', args=[keys[0].id]))
        self.assertEqual(httplib.FORBIDDEN, response.status_code, response)
        self.assertEqual(1, len(SSHKey.objects.filter(user=user)))

    def test_adding_works(self):
        key_string = get_data('data/test_rsa0.pub')
        response = self.client.post(
            reverse('sshkeys_handler'),
            data=dict(op="new", key=key_string))
        self.assertEqual(httplib.CREATED, response.status_code)
        parsed_response = json.loads(response.content)
        self.assertEqual(key_string, parsed_response["key"])
        added_key = get_one(SSHKey.objects.filter(user=self.logged_in_user))
        self.assertEqual(key_string, added_key.key)

    def test_adding_catches_key_validation_errors(self):
        key_string = factory.getRandomString()
        response = self.client.post(
            reverse('sshkeys_handler'),
            data=dict(op='new', key=key_string))
        self.assertEqual(httplib.BAD_REQUEST, response.status_code, response)
        self.assertIn("Invalid", response.content)

    def test_adding_returns_badrequest_when_key_not_in_form(self):
        response = self.client.post(
            reverse('sshkeys_handler'),
            data=dict(op='new'))
        self.assertEqual(httplib.BAD_REQUEST, response.status_code, response)
        self.assertEqual(
            dict(key=["This field is required."]),
            json.loads(response.content))


class MAASAPIAnonTest(MAASServerTestCase):
    # The MAAS' handler is not accessible to anon users.

    def test_anon_get_config_forbidden(self):
        response = self.client.get(
            reverse('maas_handler'),
            {'op': 'get_config'})

        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_anon_set_config_forbidden(self):
        response = self.client.post(
            reverse('maas_handler'),
            {'op': 'set_config'})

        self.assertEqual(httplib.FORBIDDEN, response.status_code)


class MAASAPITest(APITestCase):

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/maas/', reverse('maas_handler'))

    def test_simple_user_get_config_forbidden(self):
        response = self.client.get(
            reverse('maas_handler'),
            {'op': 'get_config'})

        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_simple_user_set_config_forbidden(self):
        response = self.client.post(
            reverse('maas_handler'),
            {'op': 'set_config'})

        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_get_config_requires_name_param(self):
        self.become_admin()
        response = self.client.get(
            reverse('maas_handler'),
            {
                'op': 'get_config',
            })

        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertEqual("No provided name!", response.content)

    def test_get_config_returns_config(self):
        self.become_admin()
        name = 'maas_name'
        value = factory.getRandomString()
        Config.objects.set_config(name, value)
        response = self.client.get(
            reverse('maas_handler'),
            {
                'op': 'get_config',
                'name': name,
            })

        self.assertEqual(httplib.OK, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertIn('application/json', response['Content-Type'])
        self.assertEqual(value, parsed_result)

    def test_get_config_rejects_unknown_config_item(self):
        self.become_admin()
        name = factory.getRandomString()
        value = factory.getRandomString()
        Config.objects.set_config(name, value)
        response = self.client.get(
            reverse('maas_handler'),
            {
                'op': 'get_config',
                'name': name,
            })

        self.assertEqual(
            (
                httplib.BAD_REQUEST,
                {name: [INVALID_SETTING_MSG_TEMPLATE % name]},
            ),
            (response.status_code, json.loads(response.content)))

    def test_set_config_requires_name_param(self):
        self.become_admin()
        response = self.client.post(
            reverse('maas_handler'),
            {
                'op': 'set_config',
                'value': factory.getRandomString(),
            })

        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertEqual("No provided name!", response.content)

    def test_set_config_requires_string_name_param(self):
        self.become_admin()
        value = factory.getRandomString()
        response = self.client.post(
            reverse('maas_handler'),
            {
                'op': 'set_config',
                'name': '',  # Invalid empty name.
                'value': value,
            })

        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertEqual(
            "Invalid name: Please enter a value", response.content)

    def test_set_config_requires_value_param(self):
        self.become_admin()
        response = self.client.post(
            reverse('maas_handler'),
            {
                'op': 'set_config',
                'name': factory.getRandomString(),
            })

        self.assertEqual(httplib.BAD_REQUEST, response.status_code)
        self.assertEqual("No provided value!", response.content)

    def test_admin_set_config(self):
        self.become_admin()
        name = 'maas_name'
        value = factory.getRandomString()
        response = self.client.post(
            reverse('maas_handler'),
            {
                'op': 'set_config',
                'name': name,
                'value': value,
            })

        self.assertEqual(
            httplib.OK, response.status_code, response.content)
        stored_value = Config.objects.get_config(name)
        self.assertEqual(stored_value, value)

    def test_admin_set_config_rejects_unknown_config_item(self):
        self.become_admin()
        name = factory.getRandomString()
        value = factory.getRandomString()
        response = self.client.post(
            reverse('maas_handler'),
            {
                'op': 'set_config',
                'name': name,
                'value': value,
            })

        self.assertEqual(
            (
                httplib.BAD_REQUEST,
                {name: [INVALID_SETTING_MSG_TEMPLATE % name]},
            ),
            (response.status_code, json.loads(response.content)))


class APIErrorsTest(TransactionTestCase):

    def test_internal_error_generates_proper_api_response(self):
        error_message = factory.getRandomString()

        # Monkey patch api.create_node to have it raise a RuntimeError.
        def raise_exception(*args, **kwargs):
            raise RuntimeError(error_message)
        self.patch(api, 'create_node', raise_exception)
        response = self.client.post(reverse('nodes_handler'), {'op': 'new'})

        self.assertEqual(
            (httplib.INTERNAL_SERVER_ERROR, error_message),
            (response.status_code, response.content))


def dict_subset(obj, fields):
    """Return a dict of a subset of the fields/values of an object."""
    undefined = object()
    values = (getattr(obj, field, undefined) for field in fields)
    return {
        field: value for field, value in izip(fields, values)
        if value is not undefined
    }


class TestNodeGroupInterfacesAPI(APITestCase):

    def test_list_lists_interfaces(self):
        self.become_admin()
        nodegroup = factory.make_node_group()
        response = self.client.get(
            reverse('nodegroupinterfaces_handler', args=[nodegroup.uuid]),
            {'op': 'list'})
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            [
                dict_subset(
                    interface, DISPLAYED_NODEGROUPINTERFACE_FIELDS)
                for interface in nodegroup.nodegroupinterface_set.all()
            ],
            json.loads(response.content))

    def test_list_does_not_work_for_normal_user(self):
        nodegroup = NodeGroup.objects.ensure_master()
        log_in_as_normal_user(self.client)
        response = self.client.get(
            reverse('nodegroupinterfaces_handler', args=[nodegroup.uuid]),
            {'op': 'list'})
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_list_works_for_master_worker(self):
        nodegroup = NodeGroup.objects.ensure_master()
        client = make_worker_client(nodegroup)
        response = client.get(
            reverse('nodegroupinterfaces_handler', args=[nodegroup.uuid]),
            {'op': 'list'})
        self.assertEqual(httplib.OK, response.status_code)

    def test_new_creates_interface(self):
        self.become_admin()
        nodegroup = factory.make_node_group(
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)

        interface_settings = make_interface_settings()
        query_data = dict(interface_settings, op="new")
        response = self.client.post(
            reverse('nodegroupinterfaces_handler', args=[nodegroup.uuid]),
            query_data)
        self.assertEqual(httplib.OK, response.status_code, response.content)
        expected_result = interface_settings
        new_interface = NodeGroupInterface.objects.get(
            nodegroup=nodegroup, interface=interface_settings['interface'])
        self.assertThat(
            new_interface,
            MatchesStructure.byEquality(**expected_result))

    def test_new_validates_data(self):
        self.become_admin()
        nodegroup = factory.make_node_group()
        response = self.client.post(
            reverse('nodegroupinterfaces_handler', args=[nodegroup.uuid]),
            {'op': 'new', 'ip': 'invalid ip'})
        self.assertEqual(
            (
                httplib.BAD_REQUEST,
                {'ip': ["Enter a valid IPv4 or IPv6 address."]},
            ),
            (response.status_code, json.loads(response.content)))

    def test_new_does_not_work_for_normal_user(self):
        nodegroup = NodeGroup.objects.ensure_master()
        log_in_as_normal_user(self.client)
        response = self.client.post(
            reverse('nodegroupinterfaces_handler', args=[nodegroup.uuid]),
            {'op': 'new'})
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_new_works_for_master_worker(self):
        nodegroup = NodeGroup.objects.ensure_master()
        client = make_worker_client(nodegroup)
        response = client.post(
            reverse('nodegroupinterfaces_handler', args=[nodegroup.uuid]),
            {'op': 'new'})
        # It's a bad request because we've not entered all the required
        # data but it's not FORBIDDEN which means we passed the test.
        self.assertEqual(
            (
                httplib.BAD_REQUEST,
                {'ip': ["This field is required."]},
            ),
            (response.status_code, json.loads(response.content)))


class TestNodeGroupInterfaceAPIAccessPermissions(APITestCase):
    # The nodegroup worker must have access because it amends the
    # foreign_dhcp_ip property. Normal users do not have access.

    def test_read_does_not_work_for_normal_user(self):
        nodegroup = NodeGroup.objects.ensure_master()
        interface = factory.make_node_group_interface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        log_in_as_normal_user(self.client)
        response = self.client.get(
            reverse(
                'nodegroupinterface_handler',
                args=[nodegroup.uuid, interface.interface]))
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_read_works_for_master_worker(self):
        nodegroup = NodeGroup.objects.ensure_master()
        interface = factory.make_node_group_interface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        client = make_worker_client(nodegroup)
        response = client.get(
            reverse(
                'nodegroupinterface_handler',
                args=[nodegroup.uuid, interface.interface]))
        self.assertEqual(httplib.OK, response.status_code)

    def test_update_does_not_work_for_normal_user(self):
        nodegroup = NodeGroup.objects.ensure_master()
        interface = factory.make_node_group_interface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        log_in_as_normal_user(self.client)
        response = self.client_put(
            reverse(
                'nodegroupinterface_handler',
                args=[nodegroup.uuid, interface.interface]),
            {'ip_range_high': factory.getRandomIPAddress()})
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_update_works_for_master_worker(self):
        nodegroup = NodeGroup.objects.ensure_master()
        interface = factory.make_node_group_interface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        self.client = make_worker_client(nodegroup)
        get_ip_in_network = partial(
            factory.getRandomIPInNetwork, interface.network)
        new_ip_range_high = next(
            ip for ip in iter(get_ip_in_network, None)
            if ip != interface.ip_range_high)
        response = self.client_put(
            reverse(
                'nodegroupinterface_handler',
                args=[nodegroup.uuid, interface.interface]),
            {'ip_range_high': new_ip_range_high})
        self.assertEqual(httplib.OK, response.status_code)

    def test_delete_does_not_work_for_normal_user(self):
        nodegroup = NodeGroup.objects.ensure_master()
        interface = factory.make_node_group_interface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        log_in_as_normal_user(self.client)
        response = self.client.delete(
            reverse(
                'nodegroupinterface_handler',
                args=[nodegroup.uuid, interface.interface]))
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_delete_works_for_master_worker(self):
        nodegroup = NodeGroup.objects.ensure_master()
        interface = factory.make_node_group_interface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        self.client = make_worker_client(nodegroup)
        response = self.client.delete(
            reverse(
                'nodegroupinterface_handler',
                args=[nodegroup.uuid, interface.interface]))
        self.assertEqual(httplib.NO_CONTENT, response.status_code)


class TestNodeGroupInterfaceAPI(APITestCase):

    def test_read_interface(self):
        self.become_admin()
        nodegroup = factory.make_node_group()
        interface = nodegroup.get_managed_interface()
        response = self.client.get(
            reverse(
                'nodegroupinterface_handler',
                args=[nodegroup.uuid, interface.interface]))
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(
            dict_subset(
                interface, DISPLAYED_NODEGROUPINTERFACE_FIELDS),
            json.loads(response.content))

    def test_update_interface(self):
        self.become_admin()
        nodegroup = factory.make_node_group()
        interface = nodegroup.get_managed_interface()
        get_ip_in_network = partial(
            factory.getRandomIPInNetwork, interface.network)
        new_ip_range_high = next(
            ip for ip in iter(get_ip_in_network, None)
            if ip != interface.ip_range_high)
        response = self.client_put(
            reverse(
                'nodegroupinterface_handler',
                args=[nodegroup.uuid, interface.interface]),
            {'ip_range_high': new_ip_range_high})
        self.assertEqual(
            (httplib.OK, new_ip_range_high),
            (response.status_code, reload_object(interface).ip_range_high))

    def test_delete_interface(self):
        self.become_admin()
        nodegroup = factory.make_node_group()
        interface = nodegroup.get_managed_interface()
        response = self.client.delete(
            reverse(
                'nodegroupinterface_handler',
                args=[nodegroup.uuid, interface.interface]))
        self.assertEqual(httplib.NO_CONTENT, response.status_code)
        self.assertFalse(
            NodeGroupInterface.objects.filter(
                interface=interface.interface, nodegroup=nodegroup).exists())

    def test_update_foreign_dhcp_ip_sets_value(self):
        self.become_admin()
        nodegroup = factory.make_node_group()
        interface = nodegroup.get_managed_interface()
        ip = factory.getRandomIPAddress()
        response = self.client_put(
            reverse(
                'nodegroupinterface_handler',
                args=[nodegroup.uuid, interface.interface]),
            {
                'foreign_dhcp_ip': ip,
            })
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(ip, reload_object(interface).foreign_dhcp_ip)

    def test_update_foreign_dhcp_ip_unsets_value(self):
        self.become_admin()
        nodegroup = factory.make_node_group()
        interface = nodegroup.get_managed_interface()
        interface.foreign_dhcp_ip = factory.getRandomIPAddress()
        interface.save()
        response = self.client_put(
            reverse(
                'nodegroupinterface_handler',
                args=[nodegroup.uuid, interface.interface]),
            {
                'foreign_dhcp_ip': '',
            })
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(None, reload_object(interface).foreign_dhcp_ip)


class TestBootImagesAPI(APITestCase):

    resources = (
        ('celery', FixtureResource(CeleryFixture())),
        )

    def report_images(self, nodegroup, images, client=None):
        if client is None:
            client = self.client
        return client.post(
            reverse('boot_images_handler'), {
                'images': json.dumps(images),
                'nodegroup': nodegroup.uuid,
                'op': 'report_boot_images',
                })

    def test_report_boot_images_does_not_work_for_normal_user(self):
        nodegroup = NodeGroup.objects.ensure_master()
        log_in_as_normal_user(self.client)
        response = self.report_images(nodegroup, [])
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_report_boot_images_works_for_master_worker(self):
        nodegroup = NodeGroup.objects.ensure_master()
        client = make_worker_client(nodegroup)
        response = self.report_images(nodegroup, [], client=client)
        self.assertEqual(httplib.OK, response.status_code)

    def test_report_boot_images_stores_images(self):
        nodegroup = NodeGroup.objects.ensure_master()
        image = make_boot_image_params()
        client = make_worker_client(nodegroup)
        response = self.report_images(nodegroup, [image], client=client)
        self.assertEqual(
            (httplib.OK, "OK"),
            (response.status_code, response.content))
        self.assertTrue(
            BootImage.objects.have_image(nodegroup=nodegroup, **image))

    def test_report_boot_images_ignores_unknown_image_properties(self):
        nodegroup = NodeGroup.objects.ensure_master()
        image = make_boot_image_params()
        image['nonesuch'] = factory.make_name('nonesuch'),
        client = make_worker_client(nodegroup)
        response = self.report_images(nodegroup, [image], client=client)
        self.assertEqual(
            (httplib.OK, "OK"),
            (response.status_code, response.content))

    def test_report_boot_images_warns_if_no_images_found(self):
        nodegroup = NodeGroup.objects.ensure_master()
        factory.make_node_group()  # Second nodegroup with no images.
        recorder = self.patch(api, 'register_persistent_error')
        client = make_worker_client(nodegroup)
        response = self.report_images(nodegroup, [], client=client)
        self.assertEqual(
            (httplib.OK, "OK"),
            (response.status_code, response.content))

        self.assertIn(
            COMPONENT.IMPORT_PXE_FILES,
            [args[0][0] for args in recorder.call_args_list])
        # Check that the persistent error message contains a link to the
        # clusters listing.
        self.assertIn(
            "/settings/#accepted-clusters", recorder.call_args_list[0][0][1])

    def test_report_boot_images_warns_if_any_nodegroup_has_no_images(self):
        nodegroup = NodeGroup.objects.ensure_master()
        # Second nodegroup with no images.
        factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED)
        recorder = self.patch(api, 'register_persistent_error')
        client = make_worker_client(nodegroup)
        image = make_boot_image_params()
        response = self.report_images(nodegroup, [image], client=client)
        self.assertEqual(
            (httplib.OK, "OK"),
            (response.status_code, response.content))

        self.assertIn(
            COMPONENT.IMPORT_PXE_FILES,
            [args[0][0] for args in recorder.call_args_list])

    def test_report_boot_images_ignores_non_accepted_groups(self):
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED)
        factory.make_node_group(status=NODEGROUP_STATUS.PENDING)
        factory.make_node_group(status=NODEGROUP_STATUS.REJECTED)
        recorder = self.patch(api, 'register_persistent_error')
        client = make_worker_client(nodegroup)
        image = make_boot_image_params()
        response = self.report_images(nodegroup, [image], client=client)
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(0, recorder.call_count)

    def test_report_boot_images_removes_warning_if_images_found(self):
        self.patch(api, 'register_persistent_error')
        self.patch(api, 'discard_persistent_error')
        nodegroup = factory.make_node_group()
        image = make_boot_image_params()
        client = make_worker_client(nodegroup)

        response = self.report_images(nodegroup, [image], client=client)
        self.assertEqual(
            (httplib.OK, "OK"),
            (response.status_code, response.content))

        self.assertItemsEqual(
            [],
            api.register_persistent_error.call_args_list)
        api.discard_persistent_error.assert_called_once_with(
            COMPONENT.IMPORT_PXE_FILES)

    def test_worker_calls_report_boot_images(self):
        # report_boot_images() uses the report_boot_images op on the nodes
        # handlers to send image information.
        self.useFixture(
            EnvironmentVariableFixture("MAAS_URL", settings.DEFAULT_MAAS_URL))
        refresh_worker(NodeGroup.objects.ensure_master())
        self.patch(MAASClient, 'post')
        self.patch(tftppath, 'list_boot_images', Mock(return_value=[]))
        self.patch(boot_images, "get_cluster_uuid")

        tasks.report_boot_images.delay()

        # We're not concerned about the payloads (images and nodegroup) here;
        # those are tested in provisioningserver.tests.test_boot_images.
        MAASClient.post.assert_called_once_with(
            reverse('boot_images_handler').lstrip('/'), 'report_boot_images',
            images=ANY, nodegroup=ANY)
