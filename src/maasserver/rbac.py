from collections import defaultdict
from functools import partial
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
from maasserver.enum import NODE_PERMISSION
from maasserver.macaroon_auth import (
    AuthInfo,
    get_auth_info,
    MacaroonClient,
)
from maasserver.models import (
    Config,
    ResourcePool,
)


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

    API_BASE_URL = '/api/service/1.0/resources'

    def __init__(self, url: str=None, auth_info: AuthInfo=None):
        if url is None:
            url = Config.objects.get_config('rbac_url')
        if auth_info is None:
            auth_info = get_auth_info()
        super(RBACClient, self).__init__(auth_info=auth_info, url=url)

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
            last_sync_id: int=None):
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
        result = self._request(
            'POST', self._get_resource_type_url(resource_type),
            json=data)
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

    def allow(self, user, pool, permission):
        """Add a policy for a user having a permission on a pool."""
        identifier = '' if pool is ALL_RESOURCES else str(pool.id)
        user_permissions = self.allowed[user]
        user_resources = user_permissions['resource-pool']
        user_resources[permission].append(identifier)


class FakeRBACClient(RBACClient):
    """A fake RBACClient that can be used in tests.

    It overrides _request to talk to a fake store, so it works exactly
    like the real client, except that it doesn't talk to a real RBAC
    server.
    """

    def __init__(self):
        self._url = Config.objects.get_config('rbac_url')
        self.store = FakeResourceStore()

    def _request(self, method, url):
        parsed = urlparse(url)
        path_parts = parsed.path.split('/')
        assert path_parts[:5] == ['', 'api', 'service', '1.0', 'resources']
        if method.upper() == 'GET':
            resource_type, action = path_parts[5:7]
            query = parse_qs(parsed.query)
            [user] = query['user']
            [permission] = query['permission']
            user_resources = self.store.allowed.get(user, {})
            user_permissions = user_resources.get(resource_type, {})
            pool_identifiers = user_permissions.get(permission, [])
            return [''] if '' in pool_identifiers else pool_identifiers


NODE_PERMISSION_TO_RBAC = {
    NODE_PERMISSION.VIEW: 'view',
    NODE_PERMISSION.ADMIN: 'admin-machines',
}


class RBAC:
    """Object for querying RBAC information."""

    def __init__(self, client=None):
        url = Config.objects.get_config('rbac_url')
        if client is None and url:
            client = RBACClient(url)
        self.client = client

    def is_enabled(self):
        """Return whether MAAS has been configured to use RBAC."""
        return self.client is not None

    def get_resource_pools(self, user, node_permission):
        """Get the resource pools that given user has the given permission on.

        @param user: The user name of the user.
        @param node_permission: A NODE_PERMISSION that the user should
            have on the machines in the resource pool.
        """
        pool_identifiers = self.client.allowed_for_user(
            'resource-pool', user, NODE_PERMISSION_TO_RBAC[node_permission])
        pools = ResourcePool.objects.all()
        if pool_identifiers is not ALL_RESOURCES:
            pool_ids = [int(identifier) for identifier in pool_identifiers]
            pools = pools.filter(id__in=pool_ids)
        return pools
