# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass

from maascommon.openfga.async_client import OpenFGAClient
from maascommon.openfga.base import OpenFGAEntitlementResourceType
from maasservicelayer.builders.openfga_tuple import OpenFGATupleBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.openfga_tuples import (
    OpenFGATuplesClauseFactory,
    OpenFGATuplesRepository,
)
from maasservicelayer.models.openfga_tuple import OpenFGATuple
from maasservicelayer.services.base import Service, ServiceCache


class UndefinedEntitlementError(Exception):
    """Raised when an entitlement name is not defined in the factory."""


class BaseEntitlementResourceBuilderFactory:
    ENTITLEMENTS = {}

    def __init__(self, entitlement: str):
        is_valid, error_message = self.validate_entitlement(entitlement)
        if not is_valid:
            raise UndefinedEntitlementError(error_message)

        self.builder = self.ENTITLEMENTS[entitlement]

    def build_tuple(
        self, group_id: int, resource_id: int
    ) -> OpenFGATupleBuilder:
        return self.builder(group_id, str(resource_id))

    @classmethod
    def validate_entitlement(
        cls, entitlement_name: str
    ) -> tuple[bool, str | None]:
        if entitlement_name not in cls.ENTITLEMENTS:
            return (
                False,
                f"Entitlement {entitlement_name} is not defined the requested resource type. Valid entitlements are: {list(cls.ENTITLEMENTS.keys())}",
            )
        return True, None


class MAASTupleBuilderFactory(BaseEntitlementResourceBuilderFactory):
    ENTITLEMENTS = {
        "can_edit_machines": OpenFGATupleBuilder.build_group_can_edit_machines,
        "can_deploy_machines": OpenFGATupleBuilder.build_group_can_deploy_machines,
        "can_view_machines": OpenFGATupleBuilder.build_group_can_view_machines,
        "can_view_available_machines": OpenFGATupleBuilder.build_group_can_view_available_machines,
        "can_edit_global_entities": OpenFGATupleBuilder.build_group_can_edit_global_entities,
        "can_view_global_entities": OpenFGATupleBuilder.build_group_can_view_global_entities,
        "can_edit_controllers": OpenFGATupleBuilder.build_group_can_edit_controllers,
        "can_view_controllers": OpenFGATupleBuilder.build_group_can_view_controllers,
        "can_edit_identities": OpenFGATupleBuilder.build_group_can_edit_identities,
        "can_view_identities": OpenFGATupleBuilder.build_group_can_view_identities,
        "can_edit_configurations": OpenFGATupleBuilder.build_group_can_edit_configurations,
        "can_view_configurations": OpenFGATupleBuilder.build_group_can_view_configurations,
        "can_edit_notifications": OpenFGATupleBuilder.build_group_can_edit_notifications,
        "can_view_notifications": OpenFGATupleBuilder.build_group_can_view_notifications,
        "can_edit_boot_entities": OpenFGATupleBuilder.build_group_can_edit_boot_entities,
        "can_view_boot_entities": OpenFGATupleBuilder.build_group_can_view_boot_entities,
        "can_edit_license_keys": OpenFGATupleBuilder.build_group_can_edit_license_keys,
        "can_view_license_keys": OpenFGATupleBuilder.build_group_can_view_license_keys,
        "can_view_devices": OpenFGATupleBuilder.build_group_can_view_devices,
        "can_view_ipaddresses": OpenFGATupleBuilder.build_group_can_view_ipaddresses,
        "can_view_dnsrecords": OpenFGATupleBuilder.build_group_can_view_dnsrecords,
    }

    def build_tuple(
        self, group_id: int, resource_id: int
    ) -> OpenFGATupleBuilder:
        if resource_id != 0:
            raise UndefinedEntitlementError(
                "Resource ID must be 0 for maas entitlements."
            )
        return self.builder(group_id)


class PoolTupleBuilderFactory(BaseEntitlementResourceBuilderFactory):
    ENTITLEMENTS = {
        "can_edit_machines": OpenFGATupleBuilder.build_group_can_edit_machines_in_pool,
        "can_deploy_machines": OpenFGATupleBuilder.build_group_can_deploy_machines_in_pool,
        "can_view_machines": OpenFGATupleBuilder.build_group_can_view_machines_in_pool,
        "can_view_available_machines": OpenFGATupleBuilder.build_group_can_view_available_machines_in_pool,
    }


class EntitlementsBuilderFactory:
    FACTORIES = {
        OpenFGAEntitlementResourceType.MAAS: MAASTupleBuilderFactory,
        OpenFGAEntitlementResourceType.POOL: PoolTupleBuilderFactory,
    }

    @classmethod
    def _get_factory_class(
        cls, resource_type: OpenFGAEntitlementResourceType
    ) -> type[BaseEntitlementResourceBuilderFactory] | None:
        return cls.FACTORIES.get(resource_type, None)

    @classmethod
    def get_factory(
        cls,
        entitlement_name: str,
        resource_type: OpenFGAEntitlementResourceType,
    ) -> BaseEntitlementResourceBuilderFactory:
        factory = cls._get_factory_class(resource_type)
        if factory is None:
            raise UndefinedEntitlementError(
                f"Resource type {resource_type} is not defined. Valid resource types are: {list(cls.FACTORIES.keys())}"
            )

        return cls._get_factory_class(resource_type)(entitlement_name)  # type: ignore[reportOptionalCall]

    @classmethod
    def validate_entitlement(
        cls,
        entitlement_name: str,
        resource_type: OpenFGAEntitlementResourceType,
    ) -> tuple[bool, str | None]:
        factory = cls._get_factory_class(resource_type)
        if factory is None:
            return (
                False,
                f"Resource type {resource_type} is not defined. Valid resource types are: {list(cls.FACTORIES.keys())}",
            )
        return factory.validate_entitlement(entitlement_name)


@dataclass(slots=True)
class OpenFGAServiceCache(ServiceCache):
    client: OpenFGAClient | None = None

    async def close(self) -> None:
        if self.client:
            await self.client.close()


class OpenFGATupleService(Service):
    def __init__(
        self,
        context: Context,
        openfga_tuple_repository: OpenFGATuplesRepository,
        cache: ServiceCache,
    ):
        super().__init__(context, cache)
        self.openfga_tuple_repository = openfga_tuple_repository

    @staticmethod
    def build_cache_object() -> OpenFGAServiceCache:
        return OpenFGAServiceCache()

    @Service.from_cache_or_execute(attr="client")
    def get_client(self) -> OpenFGAClient:
        return OpenFGAClient()

    async def get_many(self, query: QuerySpec) -> list[OpenFGATuple]:
        return await self.openfga_tuple_repository.get_many(query)

    async def upsert(self, builder: OpenFGATupleBuilder) -> OpenFGATuple:
        return await self.openfga_tuple_repository.upsert(builder)

    async def delete_many(self, query: QuerySpec) -> None:
        return await self.openfga_tuple_repository.delete_many(query)

    async def delete_pool(self, pool_id: int) -> None:
        query = QuerySpec(
            where=OpenFGATuplesClauseFactory.and_clauses(
                [
                    OpenFGATuplesClauseFactory.with_object_id(str(pool_id)),
                    OpenFGATuplesClauseFactory.with_object_type("pool"),
                    OpenFGATuplesClauseFactory.with_relation("parent"),
                ]
            )
        )
        await self.delete_many(query)

    async def delete_user(self, user_id: int) -> None:
        query = QuerySpec(
            where=OpenFGATuplesClauseFactory.and_clauses(
                [
                    OpenFGATuplesClauseFactory.with_user(f"user:{user_id}"),
                    OpenFGATuplesClauseFactory.with_relation("member"),
                ]
            )
        )
        await self.delete_many(query)

    async def delete_group(self, group_id: int) -> None:
        # Delete users who are members of this group AND entitlement tuples associated with this group
        membership_query = QuerySpec(
            where=OpenFGATuplesClauseFactory.or_clauses(
                [
                    OpenFGATuplesClauseFactory.and_clauses(
                        [
                            OpenFGATuplesClauseFactory.with_object_type(
                                "group"
                            ),
                            OpenFGATuplesClauseFactory.with_object_id(
                                str(group_id)
                            ),
                        ]
                    ),
                    OpenFGATuplesClauseFactory.with_user(
                        f"group:{group_id}#member"
                    ),
                ]
            )
        )
        await self.delete_many(membership_query)

    async def remove_user_from_group(
        self, group_id: int, user_id: int
    ) -> None:
        query = QuerySpec(
            where=OpenFGATuplesClauseFactory.and_clauses(
                [
                    OpenFGATuplesClauseFactory.with_user(f"user:{user_id}"),
                    OpenFGATuplesClauseFactory.with_relation("member"),
                    OpenFGATuplesClauseFactory.with_object_type("group"),
                    OpenFGATuplesClauseFactory.with_object_id(str(group_id)),
                ]
            )
        )
        await self.delete_many(query)

    async def list_entitlements(
        self,
        group_id: int,
    ) -> list[OpenFGATuple]:
        query = QuerySpec(
            where=OpenFGATuplesClauseFactory.and_clauses(
                [
                    OpenFGATuplesClauseFactory.with_user(
                        f"group:{group_id}#member"
                    )
                ]
            )
        )
        return await self.get_many(query)

    async def delete_entitlement(
        self,
        group_id: int,
        entitlement_name: str,
        resource_type: str,
        resource_id: int,
    ) -> None:
        query = QuerySpec(
            where=OpenFGATuplesClauseFactory.and_clauses(
                [
                    OpenFGATuplesClauseFactory.with_user(
                        f"group:{group_id}#member"
                    ),
                    OpenFGATuplesClauseFactory.with_relation(entitlement_name),
                    OpenFGATuplesClauseFactory.with_object_type(resource_type),
                    OpenFGATuplesClauseFactory.with_object_id(
                        str(resource_id)
                    ),
                ]
            )
        )
        await self.delete_many(query)
