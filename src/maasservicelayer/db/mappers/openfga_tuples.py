# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.db.mappers.base import (
    BaseDomainDataMapper,
    ColumnMapping,
    CreateOrUpdateResource,
)
from maasservicelayer.db.tables import OpenFGATupleTable
from maasservicelayer.models.base import ResourceBuilder
from maasservicelayer.models.openfga_tuple import OpenFGATuple


class OpenFGATuplesDataMapper(BaseDomainDataMapper):
    def __init__(self):
        super().__init__(OpenFGATuple, OpenFGATupleTable)

    def field_mappings(self) -> dict[str, ColumnMapping]:
        return {"user": ColumnMapping(OpenFGATupleTable.c._user)}

    def build_resource(
        self, builder: ResourceBuilder
    ) -> CreateOrUpdateResource:
        resource = CreateOrUpdateResource()
        populated_fields = builder.populated_fields()
        if "user" in populated_fields:
            populated_fields["_user"] = populated_fields.pop("user")
        for name, value in populated_fields.items():
            resource.set_value(self.table_columns[name].name, value)
        return resource
