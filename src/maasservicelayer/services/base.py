#  Copyright 2023-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from abc import ABC
from dataclasses import dataclass
from typing import Generic, List, TypeVar

from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    NotFoundException,
    PreconditionFailedException,
)
from maasservicelayer.exceptions.constants import (
    ETAG_PRECONDITION_VIOLATION_TYPE,
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
)
from maasservicelayer.models.base import (
    ListResult,
    MaasBaseModel,
    ResourceBuilder,
)


@dataclass(slots=True)
class ServiceCache(ABC):  # noqa: B024
    """Base cache for a service."""

    def clear(self):
        for field in list(self.__slots__):
            self.__setattr__(field, None)

    async def close(self):  # noqa: B027
        """Shutdown operations to be performed when destroying the cache."""


class Service(ABC):  # noqa: B024
    """Base class for services."""

    def __init__(self, context: Context, cache: ServiceCache | None = None):
        self.context = context
        self.cache = cache

    @staticmethod
    def build_cache_object() -> ServiceCache:
        """Return the cache specific to the service."""
        raise NotImplementedError(
            "build_cache_object must be overridden in the service."
        )

    @staticmethod
    def from_cache_or_execute(attr: str):
        """Decorator to search `attr` through the cache before executing the method.

        The logic is as follows:
            - you have a Service and a related ServiceCache
            - in the ServiceCache you must define all the values that you want
                to cache as an attribute with a type and that defaults to None.
            - wrap the method in the Service that is responsible to retrieve that value
            - now the ServiceCache will be checked before executing the Service method
                and if there is a value, it will return it otherwise it will execute
                the method, populate the ServiceCache and return that value.

        Note: This decorator doesn't take into account *args and **kwargs, so don't
            expect it to cache different values for different function calls.
        """

        def inner_decorator(fn):
            async def wrapped(self, *args, **kwargs):
                if self.cache is None:
                    return await fn(self, *args, **kwargs)
                if self.cache.__getattribute__(attr) is None:  # Cache miss
                    value = await fn(self, *args, **kwargs)
                    self.cache.__setattr__(attr, value)
                return self.cache.__getattribute__(attr)

            return wrapped

        return inner_decorator


# M Model
M = TypeVar("M", bound=MaasBaseModel)

# R Repository
R = TypeVar("R", bound=BaseRepository)

# B Builder
B = TypeVar("B", bound=ResourceBuilder)


class BaseService(Service, ABC, Generic[M, R, B]):
    """
    The base class for all the services that have a BaseRepository.
    The `get`, `get_one`, `get_by_id` and all the other methods of the BaseRepository are just pass-through methods in the Service
    most of the time. In case the service needs to put additional business logic in these methods, it needs to override them.
    """

    def __init__(
        self,
        context: Context,
        repository: R,
        cache: ServiceCache | None = None,
    ):
        super().__init__(context, cache)
        self.repository = repository

    def etag_check(self, model: M, etag_if_match: str | None = None):
        """
        Raises a PreconditionFailedException if the etag does not match.
        """
        if etag_if_match is not None and model.etag() != etag_if_match:
            raise PreconditionFailedException(
                details=[
                    BaseExceptionDetail(
                        type=ETAG_PRECONDITION_VIOLATION_TYPE,
                        message=f"The resource etag '{model.etag()}' did not match '{etag_if_match}'.",
                    )
                ]
            )

    async def exists(self, query: QuerySpec):
        return await self.repository.exists(query=query)

    async def get_many(self, query: QuerySpec) -> List[M]:
        return await self.repository.get_many(query=query)

    async def get_one(self, query: QuerySpec) -> M | None:
        return await self.repository.get_one(query=query)

    async def get_by_id(self, id: int) -> M | None:
        return await self.repository.get_by_id(id=id)

    async def pre_create_hook(self, builder: B) -> None:
        return None

    async def post_create_hook(self, resource: M) -> None:
        return None

    async def create(self, builder: B) -> M:
        await self.pre_create_hook(builder)
        created_resource = await self.repository.create(builder=builder)
        await self.post_create_hook(created_resource)
        return created_resource

    async def list(
        self, page: int, size: int, query: QuerySpec | None = None
    ) -> ListResult[M]:
        return await self.repository.list(page=page, size=size, query=query)

    async def post_update_many_hook(self, resources: List[M]) -> None:
        """
        Override this function in your Service to perform post-hooks with the updated objects
        """
        return None

    async def update_many(self, query: QuerySpec, builder: B) -> List[M]:
        updated_resources = await self.repository.update_many(
            query=query, builder=builder
        )
        await self.post_update_many_hook(updated_resources)
        return updated_resources

    async def post_update_hook(
        self, old_resource: M, updated_resource: M
    ) -> None:
        """
        Override this function in your Service to perform post-hooks with the updated object
        """
        return None

    async def update_one(
        self,
        query: QuerySpec,
        builder: B,
        etag_if_match: str | None = None,
    ) -> M:
        existing_resource = await self.get_one(query=query)
        return await self._update_resource(
            existing_resource, builder, etag_if_match
        )

    async def update_by_id(
        self,
        id: int,
        builder: B,
        etag_if_match: str | None = None,
    ) -> M:
        existing_resource = await self.get_by_id(id=id)
        return await self._update_resource(
            existing_resource, builder, etag_if_match
        )

    async def _update_resource(
        self,
        existing_resource: M | None,
        builder: B,
        etag_if_match: str | None = None,
    ) -> M:
        if not existing_resource:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                        message="Resource with such identifiers does not exist.",
                    )
                ]
            )

        self.etag_check(existing_resource, etag_if_match)
        updated_resource = await self.repository.update_by_id(
            id=existing_resource.id, builder=builder
        )
        await self.post_update_hook(existing_resource, updated_resource)
        return updated_resource

    async def post_delete_many_hook(self, resources: List[M]) -> None:
        """
        Override this function in your Service to perform post-hooks with the deleted objects
        """
        return None

    async def delete_many(self, query: QuerySpec) -> List[M]:
        resources = await self.repository.delete_many(query=query)
        await self.post_delete_many_hook(resources)
        return resources

    async def pre_delete_hook(self, resource_to_be_deleted: M) -> None:
        """
        Override this function in your Service to perform pre-hooks with the object to be deleted.
        This can be used for example to implement extra checks on the objects to be deleted.

        This function is NOT executed when the deletion of objects is forced with the `force` parameter.
        """
        return None

    async def post_delete_hook(self, resource: M) -> None:
        """
        Override this function in your Service to perform post-hooks with the deleted object.
        This is called only if the delete query matched a target, so you are sure the `resource` is not None.
        """
        return None

    async def delete_one(
        self,
        query: QuerySpec,
        etag_if_match: str | None = None,
        force: bool = False,
    ) -> M | None:
        """
        Deletes a single resource matching the specified query.

        If `force` is `True`, then the `pre_delete_hook` is bypassed. This mechanism is used for example when cascading the
        deletion of resources

        Raises NotFoundException if no resource matching the query exists.
        """
        resource = await self.get_one(query=query)
        if not resource:
            raise NotFoundException()
        return await self._delete_resource(resource, etag_if_match, force)

    async def delete_by_id(
        self, id: int, etag_if_match: str | None = None, force: bool = False
    ) -> M | None:
        """
        Deletes a resource identified by its ID.

        If `force` is `True`, then the `pre_delete_hook` is bypassed. This mechanism is used for example when cascading the
        deletion of resources

        Raises NotFoundException if no resource with that `id` exists.
        """
        resource = await self.get_by_id(id=id)
        if not resource:
            raise NotFoundException()
        return await self._delete_resource(resource, etag_if_match, force)

    async def _delete_resource(
        self,
        resource: M,
        etag_if_match: str | None = None,
        force: bool = False,
    ) -> M | None:
        self.etag_check(resource, etag_if_match)
        if not force:
            await self.pre_delete_hook(resource)

        deleted_resource = await self.repository.delete_by_id(id=resource.id)
        await self.post_delete_hook(deleted_resource)
        return deleted_resource
