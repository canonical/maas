from typing import (
    Sequence,
    Union,
)
from urllib.parse import quote

import attr
from maasserver.macaroon_auth import (
    AuthInfo,
    MacaroonClient,
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

    def __init__(self, url: str, auth_info: AuthInfo):
        super(RBACClient, self).__init__(auth_info=auth_info, url=url)

    def _get_resource_type_url(self, resource_type: str):
        """Return the URL for `resource_type`."""
        return self._url + quote(
            '/api/service/1.0/resources/{}'.format(resource_type))

    def get_resources(self, resource_type: str) -> Sequence[Resource]:
        """Return list of resources with `resource_type`."""
        result = self._request(
            'GET', self._get_resource_type_url(resource_type))
        return [
            Resource(identifier=res['identifier'], name=res['name'])
            for res in result
        ]

    def put_resources(
            self, resource_type: str, resources: Sequence[Resource]=None):
        """Put all the resources for `resource_type`.

        This replaces all the resources for `resource_type`.
        """
        if resources is None:
            resources = []
        resources = [
            {
                'identifier': str(res.identifier),
                'name': res.name,
            }
            for res in resources
        ]
        self._request(
            'PUT', self._get_resource_type_url(resource_type),
            json=resources)

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
