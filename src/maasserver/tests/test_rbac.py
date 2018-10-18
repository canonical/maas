from unittest import mock

from maasserver.models import Config
from maasserver.rbac import (
    ALL_RESOURCES,
    RBACClient,
    Resource,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import MockCalledOnceWith
from macaroonbakery.bakery import PrivateKey
from macaroonbakery.httpbakery.agent import (
    Agent,
    AuthInfo,
)
import requests


class TestRBACClient(MAASServerTestCase):

    def setUp(self):
        super().setUp()
        key = PrivateKey.deserialize(
            'x0NeASLPFhOFfq3Q9M0joMveI4HjGwEuJ9dtX/HTSRY=')
        agent = Agent(
            url='https://auth.example.com', username='user@candid')
        auth_info = AuthInfo(key=key, agents=[agent])
        url = 'https://rbac.example.com'

        self.mock_request = self.patch(requests, 'request')
        self.client = RBACClient(url=url, auth_info=auth_info)

    def test_default_config_from_settings(self):
        Config.objects.set_config('rbac_url', 'https://rbac.example.com')
        Config.objects.set_config(
            'external_auth_url', 'https://auth.example.com')
        Config.objects.set_config('external_auth_user', 'user@candid')
        Config.objects.set_config(
            'external_auth_key',
            'x0NeASLPFhOFfq3Q9M0joMveI4HjGwEuJ9dtX/HTSRY=')
        client = RBACClient()
        self.assertEqual(client._url, 'https://rbac.example.com')
        self.assertEqual(
            client._auth_info.key,
            PrivateKey.deserialize(
                'x0NeASLPFhOFfq3Q9M0joMveI4HjGwEuJ9dtX/HTSRY='))
        [agent] = client._auth_info.agents
        self.assertEqual(agent.url, 'https://auth.example.com')
        self.assertEqual(agent.username, 'user@candid')

    def test_get_resources(self):
        resources = [
            {
                'identifier': '1',
                'name': 'pool-1',
            },
            {
                'identifier': '2',
                'name': 'pool-2',
            },
        ]
        response = mock.MagicMock(status_code=200)
        response.json.return_value = resources
        self.mock_request.return_value = response
        self.assertItemsEqual(self.client.get_resources('resource-pool'), [
            Resource(identifier='1', name='pool-1'),
            Resource(identifier='2', name='pool-2'),
        ])
        self.assertThat(
            self.mock_request,
            MockCalledOnceWith(
                'GET',
                'https://rbac.example.com/api/'
                'service/1.0/resources/resource-pool',
                auth=mock.ANY, cookies=mock.ANY, json=None))

    def test_update_resources(self):
        updates = [
            Resource(identifier='1', name='pool-1'),
            Resource(identifier='2', name='pool-2'),
        ]
        removals = [11, 22, 33]
        json = {
            'last-sync-id': 'a-b-c',
            'updates': [
                {
                    'identifier': '1',
                    'name': 'pool-1',
                },
                {
                    'identifier': '2',
                    'name': 'pool-2',
                },
            ],
            'removals': ['11', '22', '33']
        }
        response = mock.MagicMock(status_code=200)
        response.json.return_value = {}
        self.mock_request.return_value = response
        self.client.update_resources(
            'resource-pool', updates=updates, removals=removals,
            last_sync_id='a-b-c')
        self.assertThat(
            self.mock_request,
            MockCalledOnceWith(
                'POST',
                'https://rbac.example.com/api/'
                'service/1.0/resources/resource-pool',
                auth=mock.ANY, cookies=mock.ANY, json=json))

    def test_update_resources_no_sync_id(self):
        updates = [
            Resource(identifier='1', name='pool-1'),
            Resource(identifier='2', name='pool-2'),
        ]
        removals = [11, 22, 33]
        # removals are ignored
        json = {
            'last-sync-id': None,
            'updates': [
                {
                    'identifier': '1',
                    'name': 'pool-1',
                },
                {
                    'identifier': '2',
                    'name': 'pool-2',
                },
            ],
            'removals': []
        }
        response = mock.MagicMock(status_code=200)
        response.json.return_value = {}
        self.mock_request.return_value = response
        self.client.update_resources(
            'resource-pool', updates=updates, removals=removals)
        self.assertThat(
            self.mock_request,
            MockCalledOnceWith(
                'POST',
                'https://rbac.example.com/api/'
                'service/1.0/resources/resource-pool',
                auth=mock.ANY, cookies=mock.ANY, json=json))

    def test_allowed_for_user_all_resources(self):
        response = mock.MagicMock(status_code=200)
        response.json.return_value = [""]
        self.mock_request.return_value = response

        user = factory.make_name('user')
        self.assertEqual(
            ALL_RESOURCES, self.client.allowed_for_user('maas', user, 'admin'))
        self.assertThat(
            self.mock_request,
            MockCalledOnceWith(
                'GET',
                'https://rbac.example.com/api/'
                'service/1.0/resources/maas/'
                'allowed-for-user?user={}&permission=admin'.format(user),
                auth=mock.ANY, cookies=mock.ANY, json=None))

    def test_allowed_for_user_resource_ids(self):
        response = mock.MagicMock(status_code=200)
        response.json.return_value = ["1", "2", "3"]
        self.mock_request.return_value = response

        user = factory.make_name('user')
        self.assertEqual(
            [1, 2, 3], self.client.allowed_for_user('maas', user, 'admin'))
        self.assertThat(
            self.mock_request,
            MockCalledOnceWith(
                'GET',
                'https://rbac.example.com/api/'
                'service/1.0/resources/maas/'
                'allowed-for-user?user={}&permission=admin'.format(user),
                auth=mock.ANY, cookies=mock.ANY, json=None))
