#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from base64 import b64encode

from sqlalchemy import func, LargeBinary

from maasservicelayer.db.filters import Clause
from maasservicelayer.db.mappers.base import (
    BaseDomainDataMapper,
    ColumnMapping,
    CreateOrUpdateResource,
)
from maasservicelayer.filters.base import CustomFilter
from maasservicelayer.filters.filestorage import (
    FileStorageFilenamePrefixFilter,
)
from maasservicelayer.models.base import ResourceBuilder


class FileStorageDomainDataMapper(BaseDomainDataMapper):
    def field_mappings(self) -> dict[str, ColumnMapping]:
        return {
            "content": ColumnMapping(
                func.decode(
                    self.table_columns["content"], "base64", type_=LargeBinary
                )
            )
        }

    def custom_filter_clause(self, filter: CustomFilter) -> Clause:
        if isinstance(filter, FileStorageFilenamePrefixFilter):
            return Clause(
                condition=self.table_columns["filename"].ilike(
                    f"{filter.prefix}%"
                )
            )
        return super().custom_filter_clause(filter)

    def build_resource(
        self, builder: ResourceBuilder
    ) -> CreateOrUpdateResource:
        resource = CreateOrUpdateResource()
        for name, value in builder.populated_fields().items():
            match name:
                case "content":
                    value = b64encode(value).decode("utf-8")
            resource.set_value(name, value)
        return resource
