import http.client
from queue import Queue
from threading import Thread
from unittest import mock

from django.db import transaction
from macaroonbakery.bakery import PrivateKey
from macaroonbakery.httpbakery.agent import Agent, AuthInfo
import requests

from maasserver.models import ResourcePool
from maasserver.rbac import (
    ALL_RESOURCES,
    FakeRBACClient,
    rbac,
    RBACClient,
    RBACUserClient,
    RBACWrapper,
    Resource,
    SyncConflictError,
)
from maasserver.secrets import SecretManager
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maastesting.djangotestcase import count_queries


class TestRBACClient(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        key = PrivateKey.deserialize(
            "x0NeASLPFhOFfq3Q9M0joMveI4HjGwEuJ9dtX/HTSRY="
        )
        agent = Agent(url="https://auth.example.com", username="user@candid")
        auth_info = AuthInfo(key=key, agents=[agent])
        url = "https://rbac.example.com/"

        self.mock_request = self.patch(requests, "request")
        self.client = RBACClient(url=url, auth_info=auth_info)

    def test_default_config_from_secrets(self):
        SecretManager().set_composite_secret(
            "external-auth",
            {
                "url": "https://auth.example.com",
                "rbac-url": "https://rbac.example.com",
                "user": "user@candid",
                "key": "x0NeASLPFhOFfq3Q9M0joMveI4HjGwEuJ9dtX/HTSRY=",
            },
        )
        client = RBACClient()
        self.assertEqual(client._url, "https://rbac.example.com")
        self.assertEqual(
            client._auth_info.key,
            PrivateKey.deserialize(
                "x0NeASLPFhOFfq3Q9M0joMveI4HjGwEuJ9dtX/HTSRY="
            ),
        )
        [agent] = client._auth_info.agents
        self.assertEqual(agent.url, "https://auth.example.com")
        self.assertEqual(agent.username, "user@candid")

    def test_get_user(self):
        response = mock.MagicMock(status_code=200)
        response.json.return_value = {
            "username": "user",
            "name": "A user",
            "email": "user@example.com",
        }
        self.mock_request.return_value = response
        details = self.client.get_user_details("user")
        self.assertEqual(details.username, "user")
        self.assertEqual(details.fullname, "A user")
        self.assertEqual(details.email, "user@example.com")
        self.mock_request.assert_called_once_with(
            "GET",
            "https://rbac.example.com/api/service/v1/user/user",
            auth=mock.ANY,
            cookies=mock.ANY,
            json=None,
        )

    def test_get_resources(self):
        resources = [
            {"identifier": "1", "name": "pool-1"},
            {"identifier": "2", "name": "pool-2"},
        ]
        response = mock.MagicMock(status_code=200)
        response.json.return_value = resources
        self.mock_request.return_value = response
        self.assertCountEqual(
            self.client.get_resources("resource-pool"),
            [
                Resource(identifier="1", name="pool-1"),
                Resource(identifier="2", name="pool-2"),
            ],
        )
        self.mock_request.assert_called_once_with(
            "GET",
            "https://rbac.example.com/api/"
            "service/v1/resources/resource-pool",
            auth=mock.ANY,
            cookies=mock.ANY,
            json=None,
        )

    def test_update_resources(self):
        updates = [
            Resource(identifier="1", name="pool-1"),
            Resource(identifier="2", name="pool-2"),
        ]
        removals = [11, 22, 33]
        json = {
            "last-sync-id": "a-b-c",
            "updates": [
                {"identifier": "1", "name": "pool-1"},
                {"identifier": "2", "name": "pool-2"},
            ],
            "removals": ["11", "22", "33"],
        }
        response = mock.MagicMock(status_code=200)
        response.json.return_value = {"sync-id": "x-y-z"}
        self.mock_request.return_value = response
        sync_id = self.client.update_resources(
            "resource-pool",
            updates=updates,
            removals=removals,
            last_sync_id="a-b-c",
        )
        self.assertEqual(sync_id, "x-y-z")
        self.mock_request.assert_called_once_with(
            "POST",
            "https://rbac.example.com/api/"
            "service/v1/resources/resource-pool",
            auth=mock.ANY,
            cookies=mock.ANY,
            json=json,
        )

    def test_update_resources_no_sync_id(self):
        updates = [
            Resource(identifier="1", name="pool-1"),
            Resource(identifier="2", name="pool-2"),
        ]
        removals = [11, 22, 33]
        # removals are ignored
        json = {
            "last-sync-id": None,
            "updates": [
                {"identifier": "1", "name": "pool-1"},
                {"identifier": "2", "name": "pool-2"},
            ],
            "removals": [],
        }
        response = mock.MagicMock(status_code=200)
        response.json.return_value = {"sync-id": "x-y-z"}
        self.mock_request.return_value = response
        sync_id = self.client.update_resources(
            "resource-pool", updates=updates, removals=removals
        )
        self.assertEqual(sync_id, "x-y-z")
        self.mock_request.assert_called_once_with(
            "POST",
            "https://rbac.example.com/api/"
            "service/v1/resources/resource-pool",
            auth=mock.ANY,
            cookies=mock.ANY,
            json=json,
        )

    def test_update_resources_sync_conflict(self):
        updates = [
            Resource(identifier="1", name="pool-1"),
            Resource(identifier="2", name="pool-2"),
        ]
        removals = [11, 22, 33]
        response = mock.MagicMock(status_code=int(http.client.CONFLICT))
        response.json.return_value = {"sync-id": "x-y-z"}
        self.mock_request.return_value = response
        self.assertRaises(
            SyncConflictError,
            self.client.update_resources,
            "resource-pool",
            updates=updates,
            removals=removals,
            last_sync_id="a-b-c",
        )

    def test_allowed_for_user_all_resources(self):
        response = mock.MagicMock(status_code=200)
        response.json.return_value = {"admin": [""]}
        self.mock_request.return_value = response

        user = factory.make_name("user")
        self.assertEqual(
            {"admin": ALL_RESOURCES},
            self.client.allowed_for_user("maas", user, "admin"),
        )
        self.mock_request.assert_called_once_with(
            "GET",
            "https://rbac.example.com/api/"
            "service/v1/resources/maas/"
            "allowed-for-user?u={}&p=admin".format(user),
            auth=mock.ANY,
            cookies=mock.ANY,
            json=None,
        )

    def test_allowed_for_user_resource_ids(self):
        response = mock.MagicMock(status_code=200)
        response.json.return_value = {"admin": ["1", "2", "3"]}
        self.mock_request.return_value = response

        user = factory.make_name("user")
        self.assertEqual(
            {"admin": [1, 2, 3]},
            self.client.allowed_for_user("maas", user, "admin"),
        )
        self.mock_request.assert_called_once_with(
            "GET",
            "https://rbac.example.com/api/"
            "service/v1/resources/maas/"
            "allowed-for-user?u={}&p=admin".format(user),
            auth=mock.ANY,
            cookies=mock.ANY,
            json=None,
        )


class TestRBACWrapperIsEnabled(MAASServerTestCase):
    def test_local_disabled(self):
        SecretManager().set_composite_secret(
            "external-auth",
            {
                "url": "",
                "rbac-url": "",
                "user": "user@candid",
                "key": "x0NeASLPFhOFfq3Q9M0joMveI4HjGwEuJ9dtX/HTSRY=",
            },
        )
        rbac = RBACWrapper()
        self.assertFalse(rbac.is_enabled())

    def test_rbac_disabled(self):
        SecretManager().set_composite_secret(
            "external-auth",
            {
                "url": "https://candid.example.com",
                "rbac-url": "",
                "user": "user@candid",
                "key": "x0NeASLPFhOFfq3Q9M0joMveI4HjGwEuJ9dtX/HTSRY=",
            },
        )
        rbac = RBACWrapper()
        self.assertFalse(rbac.is_enabled())

    def test_rbac_enabled(self):
        SecretManager().set_composite_secret(
            "external-auth",
            {
                "url": "",
                "rbac-url": "https://rbac.example.com",
                "user": "user@candid",
                "key": "x0NeASLPFhOFfq3Q9M0joMveI4HjGwEuJ9dtX/HTSRY=",
            },
        )
        rbac = RBACWrapper()
        self.assertTrue(rbac.is_enabled())


class TestRBACWrapperGetResourcePools(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        SecretManager().set_composite_secret(
            "external-auth",
            {
                "rbac-url": "https://rbac.example.com",
            },
        )
        self.rbac = RBACWrapper(client_class=FakeRBACClient)
        self.client = self.rbac.client
        self.store = self.client.store
        self.default_pool = ResourcePool.objects.get_default_resource_pool()
        self.store.add_pool(self.default_pool)

    def test_get_resource_pool_ids_unknown_user(self):
        self.store.add_pool(factory.make_ResourcePool())
        self.assertNotIn("user", self.store.allowed)
        self.assertEqual(
            [], list(self.rbac.get_resource_pool_ids("user", "view")["view"])
        )

    def test_get_resource_pools_ids_user_allowed_all(self):
        pool1 = factory.make_ResourcePool()
        pool2 = factory.make_ResourcePool()
        self.store.add_pool(pool1)
        self.store.add_pool(pool2)
        self.store.allow("user", ALL_RESOURCES, "view")
        self.assertCountEqual(
            {"view": [self.default_pool.id, pool1.id, pool2.id]},
            self.rbac.get_resource_pool_ids("user", "view"),
        )

    def test_get_resource_pools_ids_user_allowed_other_permission(self):
        pool1 = factory.make_ResourcePool()
        pool2 = factory.make_ResourcePool()
        self.store.add_pool(pool1)
        self.store.add_pool(pool2)
        self.store.allow("user", pool1, "view")
        self.store.allow("user", pool2, "edit")
        self.assertCountEqual(
            {"view": [pool1.id]},
            self.rbac.get_resource_pool_ids("user", "view"),
        )
        self.assertCountEqual(
            {"admin-machines": []},
            self.rbac.get_resource_pool_ids("user", "admin-machines"),
        )

    def test_get_resource_pool_ids_user_allowed_some(self):
        pool1 = factory.make_ResourcePool()
        pool2 = factory.make_ResourcePool()
        self.store.add_pool(pool1)
        self.store.add_pool(pool2)
        self.store.allow("user", pool1, "view")
        self.assertCountEqual(
            [pool1.id],
            self.rbac.get_resource_pool_ids("user", "view")["view"],
        )

    def test_get_resource_pool_ids_one_request_per_clear_cache(self):
        self.store.allow("user", self.default_pool, "view")
        pools_one = self.rbac.get_resource_pool_ids("user", "view")["view"]
        new_pool = factory.make_ResourcePool()
        self.store.allow("user", new_pool, "view")
        pools_two = self.rbac.get_resource_pool_ids("user", "view")["view"]
        self.rbac.clear_cache()
        pools_three = self.rbac.get_resource_pool_ids("user", "view")["view"]
        self.assertEqual([self.default_pool.id], pools_one)
        self.assertEqual([self.default_pool.id], pools_two)
        self.assertEqual([self.default_pool.id, new_pool.id], pools_three)

    def test_get_resource_pool_ids_ALL_RESOURCES_always_returns_all(self):
        self.store.allow("user", ALL_RESOURCES, "view")
        pools_one = self.rbac.get_resource_pool_ids("user", "view")["view"]
        new_pool = factory.make_ResourcePool()
        pools_two = self.rbac.get_resource_pool_ids("user", "view")["view"]
        self.rbac.clear_cache()
        pools_three = self.rbac.get_resource_pool_ids("user", "view")["view"]
        self.assertEqual([self.default_pool.id], pools_one)
        self.assertEqual([self.default_pool.id, new_pool.id], pools_two)
        self.assertEqual([self.default_pool.id, new_pool.id], pools_three)

    def test_can_admin_resource_pool_returns_True(self):
        self.store.allow("user", ALL_RESOURCES, "edit")
        self.assertTrue(self.rbac.can_admin_resource_pool("user"))

    def test_can_admin_resource_pool_returns_False(self):
        pool = factory.make_ResourcePool()
        self.store.add_pool(pool)
        self.store.allow("user", pool, "edit")
        self.assertFalse(self.rbac.can_admin_resource_pool("user"))


class TestRBACWrapperClient(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        SecretManager().set_composite_secret(
            "external-auth",
            {
                "url": "https://candid.example.com",
                "rbac-url": "https://rbac.example.com",
                "user": "user@candid",
                "key": "x0NeASLPFhOFfq3Q9M0joMveI4HjGwEuJ9dtX/HTSRY=",
            },
        )

    def test_same_client(self):
        self.assertIs(rbac.client, rbac.client)

    def test_clear_same_url_same_client(self):
        rbac1 = rbac.client
        rbac.clear()
        self.assertIs(rbac1, rbac.client)

    def test_clear_new_url_creates_new_client(self):
        rbac1 = rbac.client
        rbac.clear()
        SecretManager().set_composite_secret(
            "external-auth",
            {
                "url": "https://candid.example.com",
                "rbac-url": "http://rbac-other.example.com",
                "user": "user@candid",
                "key": "x0NeASLPFhOFfq3Q9M0joMveI4HjGwEuJ9dtX/HTSRY=",
            },
        )
        self.assertIsNot(rbac1, rbac.client)

    def test_clear_new_auth_url_creates_new_client(self):
        rbac1 = rbac.client
        rbac.clear()
        SecretManager().set_composite_secret(
            "external-auth",
            {
                "url": "https://candid-other.example.com",
                "rbac-url": "https://rbac.example.com",
                "user": "user@candid",
                "key": "x0NeASLPFhOFfq3Q9M0joMveI4HjGwEuJ9dtX/HTSRY=",
            },
        )
        self.assertIsNot(rbac1, rbac.client)


class TestRBACWrapperNoClient(MAASServerTestCase):
    def test_client_twice_no_query(self):
        first, client1 = count_queries(lambda: rbac.client)
        second, client2 = count_queries(lambda: rbac.client)
        self.assertIsNone(client1)
        self.assertIsNone(client2)
        self.assertEqual((1, 0), (first, second))


class TestRBACWrapperClientThreads(MAASTransactionServerTestCase):
    def test_different_clients_per_threads(self):
        # Commit the settings to the database so the created threads have
        # access to the same data. Each thread will start its own transaction
        # so the settings must be committed.
        #
        # Since actually data is committed into the database the
        # `MAASTransactionServerTestCase` is used to reset the database to
        # a clean state after this test.
        with transaction.atomic():
            SecretManager().set_composite_secret(
                "external-auth",
                {
                    "url": "https://candid.example.com",
                    "rbac-url": "https://rbac.example.com",
                    "user": "user@candid",
                    "key": "x0NeASLPFhOFfq3Q9M0joMveI4HjGwEuJ9dtX/HTSRY=",
                },
            )

        queue = Queue()

        def target():
            queue.put(rbac.client)

        thread1 = Thread(target=target)
        thread1.start()
        thread2 = Thread(target=target)
        thread2.start()

        rbac1 = queue.get()
        queue.task_done()
        rbac2 = queue.get()
        queue.task_done()
        thread1.join()
        thread2.join()
        self.assertIsNot(rbac1, rbac2)


class TestRBACUserClient(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        self.url = "https://rbac.example.com"
        self.client = RBACUserClient(self.url)
        self.mock_request = self.patch(requests, "request")

    def mock_responses(self, *responses):
        response = mock.MagicMock(status_code=200)
        response.json.side_effect = responses
        self.mock_request.return_value = response

    def test_get_maas_product(self):
        maas = {
            "$uri": "/api/rbac/v1/product/2",
            "label": "maas",
            "name": "MAAS",
        }
        products = [
            {
                "$uri": "/api/rbac/v1/product/1",
                "label": "product-1",
                "name": "Product 1",
            },
            maas,
        ]
        self.mock_responses(products)
        self.assertEqual(self.client._get_maas_product(), maas)
        self.mock_request.assert_called_once_with(
            "GET",
            "https://rbac.example.com/api/" "rbac/v1/product",
            auth=mock.ANY,
            cookies=mock.ANY,
            json=None,
        )

    def test_get_registerable_services(self):
        products = [
            {
                "$uri": "/api/rbac/v1/product/1",
                "label": "product-1",
                "name": "Product 1",
            },
            {
                "$uri": "/api/rbac/v1/product/2",
                "label": "maas",
                "name": "MAAS",
            },
        ]
        maas1 = {
            "$uri": "/api/rbac/v1/service/3",
            "name": "maas-1",
            "description": "MAAS 1",
            "pending": True,
            "product": {"$ref": "/api/rbac/v1/product/2"},
        }
        maas2 = {
            "$uri": "/api/rbac/v1/service/4",
            "name": "maas-2",
            "description": "MAAS 2",
            "pending": True,
            "product": {"$ref": "/api/rbac/v1/product/2"},
        }
        services = [
            {
                "$uri": "/api/rbac/v1/service/1",
                "name": "service-1",
                "description": "Service 1",
                "pending": True,
                "product": {"$ref": "/api/rbac/v1/product/1"},
            },
            {
                "$uri": "/api/rbac/v1/service/2",
                "name": "service-2",
                "description": "Service 2",
                "pending": True,
                "product": {"$ref": "/api/rbac/v1/product/1"},
            },
            maas1,
            maas2,
        ]
        self.mock_responses(products, services)
        self.assertEqual(
            self.client.get_registerable_services(), [maas1, maas2]
        )
        self.mock_request.assert_any_call(
            "GET",
            "https://rbac.example.com/api/rbac/v1/product",
            auth=mock.ANY,
            cookies=mock.ANY,
            json=None,
        )

        self.mock_request.assert_any_call(
            "GET",
            "https://rbac.example.com/api/" "rbac/v1/service/registerable",
            auth=mock.ANY,
            cookies=mock.ANY,
            json=None,
        )

    def test_register_service(self):
        response = {"url": self.url, "username": "a-123"}
        self.mock_responses(response)
        self.assertEqual(
            self.client.register_service(
                "/api/rbac/v1/service/3", "dead-beef"
            ),
            response,
        )
        json = {"public-key": "dead-beef"}
        self.mock_request.assert_called_once_with(
            "POST",
            "https://rbac.example.com/api/" "rbac/v1/service/3/credentials",
            auth=mock.ANY,
            cookies=mock.ANY,
            json=json,
        )

    def test_create_service(self):
        products = [
            {"$uri": "/api/rbac/v1/product/1", "label": "maas", "name": "MAAS"}
        ]
        maas = {
            "$uri": "/api/rbac/v1/service/2",
            "name": "maas",
            "description": "",
            "pending": True,
            "product": {"$ref": "/api/rbac/v1/product/1"},
        }
        self.mock_responses(products, maas)
        self.assertEqual(self.client.create_service("maas"), maas)
        json = {"name": "maas", "product": {"$ref": "/api/rbac/v1/product/1"}}
        self.mock_request.assert_any_call(
            "GET",
            "https://rbac.example.com/api/rbac/v1/product",
            auth=mock.ANY,
            cookies=mock.ANY,
            json=None,
        )
        self.mock_request.assert_any_call(
            "POST",
            "https://rbac.example.com/api/rbac/v1/service",
            auth=mock.ANY,
            cookies=mock.ANY,
            json=json,
        )
