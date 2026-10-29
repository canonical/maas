#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from base64 import b64decode, b64encode

from sqlalchemy import func, LargeBinary

from maasservicelayer.db.mappers.base import (
    ColumnMapping,
    CreateOrUpdateResource,
    StorageRow,
)
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.models.base import ResourceBuilder
from maasservicelayer.models.nodeuserdata import NodeUserData


class NodeUserDataDomainDataMapper(DefaultDomainDataMapper[NodeUserData]):
    def field_mappings(self) -> dict[str, ColumnMapping]:
        column = self.table_columns["data"]
        return {
            "data": ColumnMapping(
                func.decode(column, "base64", type_=LargeBinary),
                storage_column=column,
            )
        }

    def build_resource(
        self, builder: ResourceBuilder
    ) -> CreateOrUpdateResource:
        values = builder.populated_fields()
        if "data" in values:
            values["data"] = b64encode(values["data"]).decode("ascii")
        return self._build_resource(values)

    def to_domain(self, row: StorageRow) -> NodeUserData:
        return super().to_domain({**row, "data": b64decode(row["data"])})
