#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from collections.abc import Mapping
from typing import Any, Generic

from maasservicelayer.db.mappers.base import (
    BaseDomainDataMapper,
    CreateOrUpdateResource,
    ModelT,
)
from maasservicelayer.models.base import ResourceBuilder


class DefaultDomainDataMapper(BaseDomainDataMapper[ModelT], Generic[ModelT]):
    """Map matching fields and declared storage-column renames."""

    def build_resource(
        self, builder: ResourceBuilder
    ) -> CreateOrUpdateResource:
        return self._build_resource(builder.populated_fields())

    def _build_resource(
        self, values: Mapping[str, Any]
    ) -> CreateOrUpdateResource:
        resource = CreateOrUpdateResource()
        for name, value in values.items():
            column = self._writable_column(name)
            if column is None:
                raise ValueError(
                    f"{self.model.__name__}.{name} has no writable column."
                )
            resource.set_value(column.name, value)
        return resource
