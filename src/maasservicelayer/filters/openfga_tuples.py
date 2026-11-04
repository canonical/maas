# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.filters.base import Filter, FilterFactory
from maasservicelayer.models.openfga_tuple import (
    EntitlementDeleteSpec,
    OpenFGATuple,
)


class OpenFGATuplesFilters(FilterFactory):
    model = OpenFGATuple

    @classmethod
    def with_object_type(cls, object_type: str) -> Filter:
        return cls._equals("object_type", object_type)

    @classmethod
    def with_object_id(cls, object_id: str) -> Filter:
        return cls._equals("object_id", object_id)

    @classmethod
    def with_relation(cls, relation: str) -> Filter:
        return cls._equals("relation", relation)

    @classmethod
    def with_user(cls, user: str) -> Filter:
        return cls._equals("user", user)

    @classmethod
    def with_users(cls, users: list[str]) -> Filter:
        return cls._is_in("user", users)

    @classmethod
    def with_entitlement_tuples(
        cls, specs: list[EntitlementDeleteSpec]
    ) -> Filter:
        return cls.or_filters(
            cls.and_filters(
                [
                    cls.with_relation(spec.entitlement),
                    cls.with_object_type(spec.resource_type),
                    cls.with_object_id(str(spec.resource_id)),
                ]
            )
            for spec in specs
        )
