from collections import defaultdict
from functools import partial
import http.client
import threading
from typing import (
    Sequence,
    Union,
)
from urllib.parse import (
    parse_qs,
    quote,
    urlparse,
)

import attr
from maasserver.macaroon_auth import (
    APIError,
    AuthInfo,
    get_auth_info,
    MacaroonClient,
)
from maasserver.models import (
    Config,
    ResourcePool,
)


class SyncConflictError(Exception):
    """Sync conflict error occurred."""


@attr.s
class Resource:
    """Represents a resource in RBAC."""

    # Identifier of the resource.
    identifier = attr.ib(converter=int)

    # Name of the resource
    name = attr.ib(converter=str)


class AllResourcesType:
    """Class that represents all resources."""

# Represents access to all resources of the requested resource type.
ALL_RESOURCES = AllResourcesType()


class RBACClient(MacaroonClient):
    """A client for RBAC API."""

    API_BASE_URL = '/api/service/v1/resources'

    def __init__(self, url: str=None, auth_info: AuthInfo=None):
        if url is None:
            url = Config.objects.get_config('rbac_url')
        if auth_info is None:
            auth_info = get_auth_info()
        super().__init__(auth_info=auth_info, url=url)

    def _get_resource_type_url(self, resource_type: str):
        """Return the URL for `resource_type`."""
        return self._url + quote(
            '{}/{}'.format(self.API_BASE_URL, resource_type))

    def get_resources(self, resource_type: str) -> Sequence[Resource]:
        """Return list of resources with `resource_type`."""
        result = self._request(
            'GET', self._get_resource_type_url(resource_type))
        return [
            Resource(identifier=res['identifier'], name=res['name'])
            for res in result
        ]

    def update_resources(
            self, resource_type: str,
            updates: Sequence[Resource]=None,
            removals: Sequence[int]=None,
            last_sync_id: str=None):
        """Put all the resources for `resource_type`.

        This replaces all the resources for `resource_type`.
        """
        resources_updates = []
        resources_removals = []
        if updates:
            resources_updates = [
                {
                    'identifier': str(res.identifier),
                    'name': res.name,
                }
                for res in updates
            ]
        if removals and last_sync_id:
            resources_removals = [str(id) for id in removals]
        data = {
            'last-sync-id': last_sync_id,
            'updates': resources_updates,
            'removals': resources_removals}
        try:
            result = self._request(
                'POST', self._get_resource_type_url(resource_type),
                json=data)
        except APIError as exc:
            if exc.status_code == int(http.client.CONFLICT) and last_sync_id:
                # Notify the caller of the conflict explicitly.
                raise SyncConflictError()
            raise
        return result['sync-id']

    def allowed_for_user(
            self,
            resource_type: str,
            user: str,
            permission: str) -> Union[AllResourcesType, Sequence[int]]:
        """Return the list of resource identifiers that `user` can access with
        `permission`.

        A list with a single item of empty string means the user has access to
        all resources of the `resource_type`.

        >>> client.allowed_for_user('maas', 'username', 'admin')
        [""]  # User is an administrator
        >>> client.allowed_for_user('maas', 'username', 'admin')
        []  # User is not an administrator
        """
        url = (
            self._get_resource_type_url(resource_type) +
            '/allowed-for-user?user={}&permission={}'.format(
                quote(user), quote(permission)))
        result = self._request('GET', url)
        if result == ['']:
            return ALL_RESOURCES
        return [int(res) for res in result]


class FakeResourceStore:
    """A fake store for RBAC resources.

    The fake RBAC client uses this so that it doesn't have to talk to a
    real RBAC server for tests.
    """

    def __init__(self):
        self.resources = defaultdict(list)
        user_resources_dict = partial(defaultdict, list)
        user_permissions_dict = partial(defaultdict, user_resources_dict)
        self.allowed = defaultdict(user_permissions_dict)

    def add_pool(self, pool):
        """Register a pool with RBAC."""
        self.resources['resource-pool'].append(
            Resource(identifier=str(pool.id), name=pool.name))

    def allow(self, username, pool, permission):
        """Add a policy for a user having a permission on a pool."""
        identifier = '' if pool is ALL_RESOURCES else str(pool.id)
        user_permissions = self.allowed[username]
        user_resources = user_permissions['resource-pool']
        user_resources[permission].append(identifier)


class FakeRBACClient(RBACClient):
    """A fake RBACClient that can be used in tests.

    It overrides _request to talk to a fake store, so it works exactly
    like the real client, except that it doesn't talk to a real RBAC
    server.
    """

    def __init__(self, url: str=None, auth_info: AuthInfo=None):
        if url is None:
            url = Config.objects.get_config('rbac_url')
        self._url = url
        self._auth_info = auth_info
        self.store = FakeResourceStore()

    def _request(self, method, url):
        parsed = urlparse(url)
        path_parts = parsed.path.split('/')
        assert path_parts[:5] == ['', 'api', 'service', 'v1', 'resources']
        if method.upper() == 'GET':
            resource_type, action = path_parts[5:7]
            query = parse_qs(parsed.query)
            [user] = query['user']
            [permission] = query['permission']
            user_resources = self.store.allowed.get(user, {})
            user_permissions = user_resources.get(resource_type, {})
            pool_identifiers = user_permissions.get(permission, [])
            return [''] if '' in pool_identifiers else pool_identifiers


# Set when their is no client for the current request.
NO_CLIENT = object()


class RBACWrapper:
    """Object for querying RBAC information."""

    def __init__(self, client_class=None):
        # A client is created per thread.
        self._store = threading.local()
        self._client_class = client_class
        if self._client_class is None:
            self._client_class = RBACClient

    def _get_rbac_url(self):
        """Return the configured RBAC url."""
        return Config.objects.get_config('rbac_url')

    @property
    def client(self):
        """Get thread-local client."""
        # Get the current cleared status and reset it to False for the
        # next request on this thread.
        cleared = getattr(self._store, 'cleared', False)
        self._store.cleared = False

        client = getattr(self._store, 'client', None)
        if client is None:
            url = self._get_rbac_url()
            if url:
                client = self._client_class(url)
                self._store.client = client
            else:
                self._store.client = NO_CLIENT
            return client

        # Check if this is a new request, a new check of the client needs
        # to be performed.
        if cleared:
            # Check that the `rbac_url` and the credentials match.
            url = self._get_rbac_url()
            if url:
                auth_info = get_auth_info()
                if client is NO_CLIENT:
                    # Previously no client was created, create a new client
                    # now that RBAC is enabled.
                    client = self._client_class(url, auth_info)
                    self._store.client = client
                elif client._url != url or client._auth_info != auth_info:
                    # URL or creds differ, re-create the client.
                    client = self._client_class(url, auth_info)
                    self._store.client = client
            else:
                # RBAC is now disabled.
                client = None
                self._store.client = NO_CLIENT

        if client is NO_CLIENT:
            return None
        return client

    def clear(self):
        """Clear the current client.

        This marks a client as cleared that way only a new client is created
        if the `rbac_url` is changed.
        """
        self.clear_cache()
        self._store.cleared = True

    def is_enabled(self):
        """Return whether MAAS has been configured to use RBAC."""
        return self.client is not None

    def get_cache(self, resource, user, default=dict):
        """Return the cache for the `resource` and `user`."""
        cache = getattr(self._store, 'cache', None)
        if cache is None:
            cache = {}
            setattr(self._store, 'cache', cache)
        key = (resource, user)
        if key in cache:
            return cache[key]
        scoped = default()
        cache[key] = scoped
        return scoped

    def clear_cache(self):
        """Clears the entire cache."""
        if hasattr(self._store, 'cache'):
            delattr(self._store, 'cache')

    def get_resource_pool_ids(self, user, permission):
        """Get the resource pools ids that given user has the given
        permission on.

        @param user: The user name of the user.
        @param permission: A permission that the user should
            have on the resource pool.
        """
        pool_identifiers = self._get_resource_pool_identifiers(
            user, permission)
        if pool_identifiers is ALL_RESOURCES:
            pool_ids = list(
                ResourcePool.objects.all().values_list('id', flat=True))
        else:
            pool_ids = [int(identifier) for identifier in pool_identifiers]
        return pool_ids

    def can_create_resource_pool(self, user):
        """Return True if the `user` can create a resource pool.

        A user can create a resource pool if they have edit on all resource
        pools.

        @param user: The user name of the user.
        """
        pool_identifiers = self._get_resource_pool_identifiers(
            user, 'edit')
        return pool_identifiers is ALL_RESOURCES

    def _get_resource_pool_identifiers(self, user, permission):
        """Get the resource pool identifiers from RBAC.

        Uses the thread-local cache so only one request is made to RBAC per
        request to MAAS.

        @param user: The user name of the user.
        @param permission: A permission that the user should
            have on the resource pool.
        """
        cache = self.get_cache('resource-pool', user)
        pool_identifiers = cache.get(permission, None)
        if pool_identifiers is None:
            pool_identifiers = self.client.allowed_for_user(
                'resource-pool', user, permission)
            cache[permission] = pool_identifiers
        return pool_identifiers


rbac = RBACWrapper()


class RBACUserClient(MacaroonClient):
    """A client for the RBAC user API."""

    API_BASE_URL = '/api/rbac/v1'

    def __init__(self, url):
        # no auth info is passed as this is meant for interactive use
        super().__init__(url, None)

    def get_registerable_services(self):
        """Return MAAS services that can be registered by the user."""
        maas = self._get_maas_product()
        services = self._request(
            'GET', self._url + self.API_BASE_URL + '/service/registerable')
        return [
            service for service in services
            if service['product']['$ref'] == maas['$uri']]

    def register_service(self, service_uri, public_key):
        """Register the specified service with the public key."""
        return self._request(
            'POST', self._url + service_uri + '/credentials',
            json={'public-key': public_key})

    def _get_maas_product(self):
        """Return details for the maas product."""
        products = self._request(
            'GET', self._url + self.API_BASE_URL + '/product')
        [maas] = [
            product for product in products if product['label'] == 'maas']
        return maas


class FakeRBACUserClient(RBACUserClient):

    def __init__(self):
        self.services = []
        self.products = []
        self.registered_services = []

    def get_products(self):
        return self.products

    def get_registerable_services(self):
        return self.services

    def register_service(self, service_uri, public_key):
        self.registered_services.append(service_uri)
        return {
            'url': 'http://auth.example.com',
            'username': 'u-{}'.format(len(self.registered_services))}
