from unittest import mock

from maasserver.rbac import (
    ALL_RESOURCES,
    RBACClient,
    Resource,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASTestCase
from maastesting.matchers import MockCalledOnceWith
from macaroonbakery.bakery import PrivateKey
from macaroonbakery.httpbakery.agent import (
    Agent,
    AuthInfo,
)
import requests


class TestRBACClient(MAASTestCase):

    def setUp(self):
        super().setUp()
        key = PrivateKey.deserialize(
            'x0NeASLPFhOFfq3Q9M0joMveI4HjGwEuJ9dtX/HTSRY=')
        agent = Agent(
            url='https://auth.example.com', username='user@idm')
        auth_info = AuthInfo(key=key, agents=[agent])
        url = 'https://rbac.example.com'

        self.mock_request = self.patch(requests, 'request')
        self.client = RBACClient(url=url, auth_info=auth_info)

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

    def test_put_resources(self):
        resources = [
            Resource(identifier='1', name='pool-1'),
            Resource(identifier='2', name='pool-2'),
        ]
        json = [
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
        response.json.return_value = {}
        self.mock_request.return_value = response
        self.client.put_resources('resource-pool', resources)
        self.assertThat(
            self.mock_request,
            MockCalledOnceWith(
                'PUT',
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
