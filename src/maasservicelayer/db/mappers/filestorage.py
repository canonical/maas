#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from base64 import b64decode, b64encode

from sqlalchemy import func, LargeBinary

from maasservicelayer.db.filters import Clause
from maasservicelayer.db.mappers.base import (
    ColumnMapping,
    CreateOrUpdateResource,
    StorageRow,
)
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.filters.base import CustomFilter
from maasservicelayer.filters.filestorage import (
    FileStorageFilenamePrefixFilter,
)
from maasservicelayer.models.base import ResourceBuilder
from maasservicelayer.models.filestorage import FileStorage


class FileStorageDomainDataMapper(DefaultDomainDataMapper[FileStorage]):
    def field_mappings(self) -> dict[str, ColumnMapping]:
        column = self.table_columns["content"]
        return {
            "content": ColumnMapping(
                func.decode(column, "base64", type_=LargeBinary),
                storage_column=column,
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
        values = builder.populated_fields()
        if "content" in values:
            values["content"] = b64encode(values["content"]).decode("utf-8")
        return self._build_resource(values)

    def to_domain(self, row: StorageRow) -> FileStorage:
        return super().to_domain({**row, "content": b64decode(row["content"])})
