from collections import defaultdict
from functools import partial
import http.client
import threading
from typing import Mapping, Sequence, Union
from urllib.parse import parse_qs, quote, urlparse

import attr
from macaroonbakery.httpbakery.agent import AuthInfo

from maasserver.macaroon_auth import APIError, MacaroonClient, UserDetails
from maasserver.models import ResourcePool
from maasserver.secrets import SecretManager
from maasserver.sqlalchemy import service_layer, ServiceLayerAdapter


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

ResourcesResultType = Union[AllResourcesType, Sequence[int]]


class RBACClient(MacaroonClient):
    """A client for RBAC API."""

    API_BASE_URL = "/api/service/v1"

    def __init__(self, url: str = None, auth_info: AuthInfo = None):
        if url is None:
            url = _get_rbac_url_from_secrets()
        if auth_info is None:
            # Do not use sqlalchemy.service_layer, we want to create/delete RBACClients multiple times within the same thread.
            with ServiceLayerAdapter() as sl:
                auth_info = sl.services.external_auth.get_auth_info()
        super().__init__(auth_info=auth_info, url=url)

    def _get_resource_type_url(self, resource_type: str):
        """Return the URL for `resource_type`."""
        return self._url + quote(
            f"{self.API_BASE_URL}/resources/{resource_type}"
        )

    def get_user_details(self, username: str) -> UserDetails:
        """Return details about a user."""
        url = self._url + quote(f"{self.API_BASE_URL}/user/{username}")
        details = self._request("GET", url)
        return UserDetails(
            username=details["username"],
            fullname=details.get("name", ""),
            email=details.get("email", ""),
        )

    def get_resources(self, resource_type: str) -> Sequence[Resource]:
        """Return list of resources with `resource_type`."""
        result = self._request(
            "GET", self._get_resource_type_url(resource_type)
        )
        return [
            Resource(identifier=res["identifier"], name=res["name"])
            for res in result
        ]

    def update_resources(
        self,
        resource_type: str,
        updates: Sequence[Resource] = None,
        removals: Sequence[int] = None,
        last_sync_id: str = None,
    ):
        """Put all the resources for `resource_type`.

        This replaces all the resources for `resource_type`.
        """
        resources_updates = []
        resources_removals = []
        if updates:
            resources_updates = [
                {"identifier": str(res.identifier), "name": res.name}
                for res in updates
            ]
        if removals and last_sync_id:
            resources_removals = [str(id) for id in removals]
        data = {
            "last-sync-id": last_sync_id,
            "updates": resources_updates,
            "removals": resources_removals,
        }
        try:
            result = self._request(
                "POST", self._get_resource_type_url(resource_type), json=data
            )
        except APIError as exc:
            if exc.status_code == int(http.client.CONFLICT) and last_sync_id:
                # Notify the caller of the conflict explicitly.
                raise SyncConflictError()  # noqa: B904
            raise
        return result["sync-id"]

    def allowed_for_user(
        self, resource_type: str, user: str, *permissions: Sequence[str]
    ) -> ResourcesResultType:
        """Return the resource identifiers that `user` can access with
        `permissions`.

        Returns a dictionary mapping the permissions to the resources of
        `resource_type` that the user can access. An object of `ALL_RESOURCES`
        means the user can access all resources of that type.
        """
        url = self._get_resource_type_url(
            resource_type
        ) + "/allowed-for-user?u={}&{}".format(
            quote(user),
            "&".join(
                ["p=%s" % quote(permission) for permission in permissions]
            ),
        )
        result = self._request("GET", url)
        for permission, res in result.items():
            if res == [""]:
                result[permission] = ALL_RESOURCES
            else:
                result[permission] = [int(idnt) for idnt in res]
        return result


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
        self.resources["resource-pool"].append(
            Resource(identifier=str(pool.id), name=pool.name)
        )

    def allow(self, username, pool, permission):
        """Add a policy for a user having a permission on a pool."""
        identifier = "" if pool is ALL_RESOURCES else str(pool.id)
        user_permissions = self.allowed[username]
        user_resources = user_permissions["resource-pool"]
        user_resources[permission].append(identifier)


class FakeRBACClient(RBACClient):
    """A fake RBACClient that can be used in tests.

    It overrides _request to talk to a fake store, so it works exactly
    like the real client, except that it doesn't talk to a real RBAC
    server.
    """

    def __init__(self, url: str = None, auth_info: AuthInfo = None):
        if url is None:
            url = _get_rbac_url_from_secrets()
        self._url = url
        self._auth_info = auth_info
        self.store = FakeResourceStore()

    def _request(self, method, url):
        parsed = urlparse(url)
        path_parts = parsed.path.split("/")
        assert path_parts[:5] == ["", "api", "service", "v1", "resources"]
        if method.upper() == "GET":
            resource_type, action = path_parts[5:7]
            query = parse_qs(parsed.query)
            [user] = query["u"]
            permissions = query["p"]
            user_resources = self.store.allowed.get(user, None)
            if user_resources is None:
                return {}
            user_permissions = user_resources.get(resource_type, {})
            result = {}
            for permission in permissions:
                pool_identifiers = user_permissions.get(permission, [])
                result[permission] = (
                    [""] if "" in pool_identifiers else pool_identifiers
                )
            return result

    def get_user_details(self, username):
        return UserDetails(
            username=username,
            fullname="User username",
            email=username + "@example.com",
        )


# Set when there is no client for the current request.
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
        return _get_rbac_url_from_secrets()

    @property
    def client(self):
        """Get thread-local client."""
        # Get the current cleared status and reset it to False for the
        # next request on this thread.
        cleared = getattr(self._store, "cleared", False)
        self._store.cleared = False

        client = getattr(self._store, "client", None)
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
                auth_info = (
                    service_layer.services.external_auth.get_auth_info()
                )
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
        cache = getattr(self._store, "cache", None)
        if cache is None:
            cache = {}
            setattr(self._store, "cache", cache)  # noqa: B010
        key = (resource, user)
        if key in cache:
            return cache[key]
        scoped = default()
        cache[key] = scoped
        return scoped

    def clear_cache(self):
        """Clears the entire cache."""
        if hasattr(self._store, "cache"):
            delattr(self._store, "cache")

    def get_resource_pool_ids(
        self, user: str, *permissions: Sequence[str]
    ) -> Mapping[str, ResourcesResultType]:
        """Get the resource pools ids that given user has the given
        permission on.

        @param user: The user name of the user.
        @param permission: A permission that the user should
            have on the resource pool.
        """
        results = self._get_resource_pool_identifiers(user, *permissions)
        for permission, result in results.items():
            if result is ALL_RESOURCES:
                results[permission] = list(
                    ResourcePool.objects.all().values_list("id", flat=True)
                )
            else:
                results[permission] = [int(idnt) for idnt in result]
        return results

    def can_admin_resource_pool(self, user: str) -> bool:
        """Return True if the `user` can create or delete a resource pool.

        A user can create or delete a resource pool if they have edit on all resource
        pools.

        @param user: The user name of the user.
        """
        pool_identifiers = self._get_resource_pool_identifiers(user, "edit")
        return pool_identifiers["edit"] is ALL_RESOURCES

    def _get_resource_pool_identifiers(
        self, user: str, *permissions: Sequence[str]
    ) -> Mapping[str, ResourcesResultType]:
        """Get the resource pool identifiers from RBAC.

        Uses the thread-local cache so only one request is made to RBAC per
        request to MAAS.

        @param user: The user name of the user.
        @param permission: A permission that the user should
            have on the resource pool.
        """
        cache = self.get_cache("resource-pool", user)
        results, missing = {}, []
        for permission in permissions:
            identifiers = cache.get(permission, None)
            if identifiers is None:
                missing.append(permission)
            else:
                results[permission] = identifiers

        if missing:
            fetched = self.client.allowed_for_user(
                "resource-pool", user, *missing
            )
            for permission in missing:
                identifiers = fetched.get(permission, {})
                cache[permission] = results[permission] = identifiers

        return results


rbac = RBACWrapper()


class RBACUserClient(MacaroonClient):
    """A client for the RBAC user API."""

    API_BASE_URL = "/api/rbac/v1"

    def __init__(self, url):
        # no auth info is passed as this is meant for interactive use
        super().__init__(url, None)
        self._maas_product = None

    def create_service(self, name):
        """Create a MAAS service with the specified name."""
        maas = self._get_maas_product()
        data = {"name": name, "product": {"$ref": maas["$uri"]}}
        return self._api_request("POST", "/service", json=data)

    def get_registerable_services(self):
        """Return MAAS services that can be registered by the user."""
        maas = self._get_maas_product()
        services = self._api_request("GET", "/service/registerable")
        return [
            service
            for service in services
            if service["product"]["$ref"] == maas["$uri"]
        ]

    def register_service(self, service_uri, public_key):
        """Register the specified service with the public key."""
        return self._request(
            "POST",
            self._url + service_uri + "/credentials",
            json={"public-key": public_key},
        )

    def _get_maas_product(self):
        """Return details for the maas product."""
        if self._maas_product is None:
            products = self._api_request("GET", "/product")
            [maas] = [
                product for product in products if product["label"] == "maas"
            ]
            self._maas_product = maas
        return self._maas_product

    def _api_request(self, method, path, json=None, status_code=200):
        return self._request(
            method,
            self._url + self.API_BASE_URL + path,
            json=json,
            status_code=status_code,
        )


class FakeRBACUserClient(RBACUserClient):
    def __init__(self):
        self.services = []
        self.products = []
        self.registered_services = []

    def create_service(self, name):
        maas = {
            "name": "maas",
            "$uri": "/api/rbac/v1/service/4",
            "pending": True,
            "product": {"$ref/api/rbac/v1/product/2"},
        }
        self.services.append(maas)
        return maas

    def get_products(self):
        return self.products

    def get_registerable_services(self):
        return self.services

    def register_service(self, service_uri, public_key):
        self.registered_services.append(service_uri)
        return {
            "url": "http://auth.example.com",
            "username": f"u-{len(self.registered_services)}",
        }


def _get_rbac_url_from_secrets() -> str:
    secret = SecretManager().get_composite_secret("external-auth", default={})
    return secret.get("rbac-url", "")
